from camera_tools import XimeaCamera, Camera
import sys
import numpy as np
import json
import psutil
from ipc_tools import RingBuffer, ModifiableRingBuffer, Logger
import multiprocessing
from multiprocessing import Process, Pipe, Queue, connection, Event
import threading
from threading import Thread
from functools import partial
from typing import Callable
import time
from queue import Empty
import cv2
from arrayqueues import ArrayQueue
import ctypes
from video_tools import FFMPEG_VideoWriter_CPU_Grayscale

# TODO test different codecs

class CameraProcess(Process):
    def __init__(self, 
                 back_pipe: connection.Connection, 
                 buffer: ModifiableRingBuffer,
                 camera_constructor: Callable[[int], Camera],
                 start_time,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.back_pipe = back_pipe
        self.buffer = buffer
        self.camera_constructor = camera_constructor
        self.active = True
        self.save_worker = None
        self.start_time = start_time


    # add some init method and cleanup method for before and after while poop 
    def init_cam(self):
        self.camera = self.camera_constructor()
        self.camera.set_exposure(4800)
        self.camera.set_framerate(200)
        self.camera.set_gain(7.4)
        print(f'Exposure: {self.camera.get_exposure()}') #exposure time in microseconds
        print(f'Frame rate: {self.camera.get_framerate()}')

        empty_img = np.zeros((self.camera.get_height(), self.camera.get_width()), dtype=np.uint8)
        self.empty = np.array((0, 0, empty_img),
                              dtype = np.dtype([
                                  ('index', int), 
                                  ('timestamp', np.float32),
                                  ('image', empty_img.dtype, empty_img.shape)
                              ]))

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_cam()
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)

        while self.active: 
            msg = self.back_pipe.recv()
            if msg == 'start':
                print(f'CameraProcess received {msg} message')
                if self.save_worker is None:
                    self.save_worker = BufferRelay(buffer=self.buffer,
                                                   camera=self.camera)
                    self.thread = Thread(target=self.save_worker.run)
                    self.thread.start()
                self.save_worker.start_acquisition()
        
            elif msg == 'stop':
                print(f'CameraProcess received {msg} message')
                self.save_worker.stop_acquisition()
                self.buffer.put(self.empty)
                # self.save_worker.terminate()
                self.thread.join()
                self.save_worker = None

            elif msg == 'alive':
                alive = self.is_alive()
                self.back_pipe.send(alive)
                
            elif msg == 'terminate':
                self.active = False
                winmm.timeEndPeriod(1)
        print('CameraProcess exiting')
                

class BufferRelay:
    def __init__(self, 
                 buffer: ModifiableRingBuffer, 
                 camera: Camera, 
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.buffer = buffer
        self.camera = camera
        self.active = True
        self.event = threading.Event()
    
    def start_acquisition(self):
        self.camera.start_acquisition()
        # time.sleep(0.5)
        self.event.set()
    
    def stop_acquisition(self): 
        self.event.clear()
        self.active = False
        time.sleep(0.5)
        self.camera.stop_acquisition()
        print('Bye from BufferRelay!')

    def terminate(self):
        self.active = False
        # self.camera.stop_acquisition()
        time.sleep(1)
        print('Bye from BufferRelay!')

    def run(self):
        print('BufferRelay worker started')
        # self.init_time = time.perf_counter_ns()
        # print(f"Initialisation time for BufferRelay is {(self.init_time - self.start_time)/1e9}")
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)
        self.previous_qsize = -1
        fd = open('cam_frames_threads_AQ_highres_record_200_sentinel(4).txt', 'w')
        while self.active:
            if self.event.is_set():
                self.current_qsize = self.buffer.qsize()
                frame = self.camera.get_frame()
                if frame is not None:
                    self.buffer.put(frame)
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                if self.current_qsize != self.previous_qsize:
                        print(f'Camera buffer queue size: {self.current_qsize}')
                        self.previous_qsize = self.current_qsize
        fd.close()
        winmm.timeEndPeriod(1)


class SinkWorker:
    def __init__(self, 
                 buffer: ModifiableRingBuffer,
                 termination_event):
        super().__init__()
        self.buffer = buffer
        self.active = True
        self.termination_event = termination_event
    
    def init_videowriter(self):
        height = 488
        width = 648
        fps = 200

        # fourcc = cv2.VideoWriter_fourcc(*'XVID')
        # self.video_writer = cv2.VideoWriter('AQ_XVID_200_sentinel.mp4', fourcc, fps, (width, height), False)

        self.video_writer = FFMPEG_VideoWriter_CPU_Grayscale(height=height,
                                                             width=width,
                                                             codec='h264',
                                                             fps=fps,
                                                             q=5,
                                                             profile='high',
                                                             preset='superfast',
                                                             filename='FFMPEG_H264_q5_200.mp4')
        
    def terminate(self):
        # self.video_writer.release()
        self.video_writer.close()
        self.active = False
        self.termination_event.set()
        
    def run(self):
        print('SinkWorker running')
        self.init_videowriter()
        self.previous_qsize = -1
        fd = open('record_frames_threads_AQ_highres_200_sentinel(4).txt', 'w')
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)

        while self.active:  
            self.current_qsize = self.buffer.qsize()
            try:
                frame = self.buffer.get()
                if frame['image'].sum() > 0:
                    # self.video_writer.write(frame['image'])
                    self.video_writer.write_frame(frame['image'])
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                else: 
                    self.terminate()
                    winmm.timeEndPeriod(1)
                    print('sink buffer got sentinel, exiting')

                if self.current_qsize != self.previous_qsize:
                    print(f'Sink buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
            
            except Empty:
                pass
                # if self.buffer.empty():
                #     self.terminate()
                #     print('sink buffer empty, exiting')


class Sink(Process):
    def __init__(self, 
                back_pipe: connection.Connection, 
                buffer: ModifiableRingBuffer,
                start_time,
                *args, 
                **kwargs):
        super().__init__(*args, **kwargs)
    
        self.back_pipe = back_pipe
        self.buffer = buffer
        self.active = True
        self.worker = None
        self.start_time = start_time
        self.termination_event = Event()

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_time = time.perf_counter_ns()
        print(f"Initialisation time for {self.name} is {(self.init_time - self.start_time)/1e9}")
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)
        while self.active:
            msg = self.back_pipe.recv()
            
            if msg == 'start':
                print(f'SinkProcess received {msg} message')
                self.worker = SinkWorker(buffer=self.buffer,
                                         termination_event=self.termination_event)
                self.worker_thread = Thread(target=self.worker.run)
                self.worker_thread.start()

            elif msg == 'stop':
                print(f'SinkProcess received {msg} message')
                self.worker_thread.join()
                print('SinkWorker released')

            elif msg == 'terminate':
                if self.termination_event.is_set():
                    self.active = False
                    winmm.timeEndPeriod(1)
                    # break
                    time.sleep(1)
        print('Sink process exiting')

            # elif msg == 'alive':

if __name__ == "__main__":
    
    # winmm = ctypes.WinDLL('winmm.dll')
    # winmm.timeBeginPeriod(1)

    width = 648
    height = 488

    camera_constructor = partial(XimeaCamera, dev_id=0)
    
    # buffer = ModifiableRingBuffer(num_bytes=(width*height*100), 
    #                               t_refresh=1e-3)
    
    buffer = ArrayQueue(100)

    front_pipe_cam, back_pipe_cam = Pipe()
    front_pipe_sink, back_pipe_sink = Pipe()

    start_event = Event()
    terminate_event = Event()

    start_time = time.perf_counter_ns()
    print(start_time)

    camera_process = CameraProcess(back_pipe=back_pipe_cam,
                                    buffer=buffer,
                                    camera_constructor=camera_constructor,
                                    start_time=start_time)
    
    sink_process = Sink(back_pipe=back_pipe_sink,
                        buffer=buffer,
                        start_time=start_time)
    
    camera_process.start()
    sink_process.start()

    time.sleep(5)
    
    front_pipe_cam.send('start')
    # time.sleep(2)
    front_pipe_sink.send('start')

    time.sleep(30)

    front_pipe_cam.send('stop')
    front_pipe_sink.send('stop')

    # time.sleep(3)

    front_pipe_cam.send('terminate')
    front_pipe_sink.send('terminate')
    
    # time.sleep(1)

    camera_process.join()
    sink_process.join()

    # winmm.timeEndPeriod(1)