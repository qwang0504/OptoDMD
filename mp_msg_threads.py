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
        self.camera.set_exposure(1000)
        self.camera.set_framerate(200)
        print(f'Exposure: {self.camera.get_exposure()}') #exposure time in microseconds
        print(f'Frame rate: {self.camera.get_framerate()}')

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_cam()
        print(self.camera.get_framerate())
        print(self.camera.get_exposure())
        self.init_time = time.perf_counter_ns()
        print(f"Initialisation time for {self.name} is {(self.init_time - self.start_time)/1e9}")

        while self.active: 
            msg = self.back_pipe.recv()
            if msg == 'start':
                print(f'CameraProcess received {msg} message')
                if self.save_worker is None:
                    self.save_worker = BufferRelay(buffer=self.buffer,
                                                   camera=self.camera,
                                                   start_time=self.start_time)
                    self.thread = Thread(target=self.save_worker.run)
                    self.thread.start()
                self.save_worker.start_acquisition()
        
            elif msg == 'stop':
                print(f'CameraProcess received {msg} message')
                self.save_worker.stop_acquisition()
                self.save_worker.terminate()
                self.thread.join()
                self.save_worker = None

            elif msg == 'alive':
                alive = self.is_alive()
                self.back_pipe.send(alive)
                
            elif msg == 'terminate':
                self.active = False
        print('CameraProcess exiting')
                

class BufferRelay:
    def __init__(self, 
                 buffer: ModifiableRingBuffer, 
                 camera: Camera, 
                 start_time,
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.buffer = buffer
        self.camera = camera
        self.active = True
        self.event = threading.Event()
        self.start_time = start_time
    
    def start_acquisition(self):
        self.camera.start_acquisition()
        # time.sleep(0.5)
        self.event.set()
    
    def stop_acquisition(self): 
        self.event.clear()
        time.sleep(0.5)
        self.camera.stop_acquisition()

    def terminate(self):
        self.active = False
        # self.camera.stop_acquisition()
        time.sleep(1)
        print('Bye from BufferRelay!')

    def run(self):
        print('BufferRelay worker started')
        self.init_time = time.perf_counter_ns()
        print(f"Initialisation time for BufferRelay is {(self.init_time - self.start_time)/1e9}")
        # winmm = ctypes.WinDLL('winmm.dll')
        # winmm.timeBeginPeriod(1)
        self.previous_qsize = -1
        fd = open('cam_frames_threads_AQ_200.txt', 'w')
        while self.active:
            if self.event.is_set():
                self.current_qsize = self.buffer.qsize()
                frame = self.camera.get_frame()
                if frame is not None:
                    self.buffer.put(frame)
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                    # print(frame['index'], frame['timestamp'])
                if self.current_qsize != self.previous_qsize:
                        print(f'Camera buffer queue size: {self.current_qsize}')
                        self.previous_qsize = self.current_qsize
        fd.close()
        # winmm.timeEndPeriod(1)


class SinkWorker:
    def __init__(self, 
                 buffer: ModifiableRingBuffer,
                 start_time):
        super().__init__()
        self.buffer = buffer
        self.active = True
        self.start_time = start_time
    
    def terminate(self):
        self.active = False
        # while self.current_qsize > 0:
        #     continue
        
    def run(self):
        print('SinkWorker running')
        self.init_time = time.perf_counter_ns()
        print(f"Initialisation time for SinkWorker is {(self.init_time - self.start_time)/1e9}")
        # winmm = ctypes.WinDLL('winmm.dll')
        # winmm.timeBeginPeriod(1)
        self.previous_qsize = -1
        fd = open('sink_frames_threads_AQ_200.txt', 'w')
        

        while self.active:  
            
            self.current_qsize = self.buffer.qsize()
            try:
                frame = self.buffer.get(timeout=3)
                if frame is not None:
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                if self.current_qsize != self.previous_qsize:
                    print(f'Sink buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
            except Empty:
                self.terminate()
                # winmm.timeEndPeriod(1)
                print('sink buffer empty, exiting')


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

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_time = time.perf_counter_ns()
        print(f"Initialisation time for {self.name} is {(self.init_time - self.start_time)/1e9}")
        
        while self.active:
            msg = self.back_pipe.recv()
            
            if msg == 'start':
                print(f'Sink received {msg}')
                self.worker = SinkWorker(buffer=self.buffer,
                                         start_time=self.start_time)
                self.worker_thread = Thread(target=self.worker.run)
                self.worker_thread.start()

            elif msg == 'stop':
                print(f'Sink received {msg}')
                self.worker_thread.join()
                print('Worker released')

            elif msg == 'terminate':
                self.active = False
                break
        print('Sink process exiting')

            # elif msg == 'alive':

if __name__ == "__main__":
    
    width = 648
    height = 488

    camera_constructor = partial(XimeaCamera, dev_id=0)
    
    # buffer = ModifiableRingBuffer(num_bytes=(width*height*500), 
    #                               t_refresh=1e-3)
    
    buffer = ArrayQueue(500)

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

    front_pipe_cam.send('start')
    time.sleep(1)
    front_pipe_sink.send('start')

    time.sleep(25)

    front_pipe_cam.send('stop')
    front_pipe_sink.send('stop')

    time.sleep(3)

    front_pipe_cam.send('terminate')
    front_pipe_sink.send('terminate')
    
    # time.sleep(1)

    camera_process.join()
    sink_process.join()
