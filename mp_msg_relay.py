from camera_tools import XimeaCamera, Camera
import sys
import numpy as np
import json
import psutil
from ipc_tools import RingBuffer, Logger, ModifiableRingBuffer
import multiprocessing
from multiprocessing import Process, Pipe, Queue, connection, Event
# from multiprocessing.synchronize import Event
from functools import partial
from typing import Callable
import time
from queue import Empty
import logging
# from video_writer import OpenCV_VideoWriter
from video_tools import OpenCV_VideoWriter, FFMPEG_VideoWriter_CPU_Grayscale
import matplotlib.pyplot as plt
import cv2
from arrayqueues import ArrayQueue
import ctypes


class CameraProcess(Process):
    def __init__(self,
                 camera_constructor: Callable[[int], Camera],
                 start_event,
                 terminate_event,
                 buffer: ArrayQueue,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_constructor = camera_constructor
        self.start_event = start_event
        self.terminate_event = terminate_event
        self.buffer = buffer
        self.active = True

    def init_cam(self):
        self.camera = self.camera_constructor()
        self.camera.set_exposure(1000)
        self.camera.set_framerate(200)
        print('cam initialised')

    def start_acquisition(self):
        self.camera.start_acquisition()
    
    def stop_acquisition(self):
        self.camera.stop_acquisition()
    
    def run(self):
        # winmm = ctypes.WinDLL('winmm.dll')
        # winmm.timeBeginPeriod(1)
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_cam()
        self.start_acquisition()
        self.previous_qsize = -1
        fd = open('cam_frames_AQ_200.txt', 'w')
        while not self.terminate_event.is_set():
            if self.start_event.is_set():
                # self.event.wait()
                self.current_qsize = self.buffer.qsize()
                frame = self.camera.get_frame()
                if frame is not None:
                    self.buffer.put(frame)
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                    # print(f"camera frames: {frame['index']}, {frame['timestamp']}")

                if self.current_qsize != self.previous_qsize:
                    print(f'cam buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
            else: 
                self.stop_acquisition()
                # print('camera acquisition stopped')
                fd.close()
                # winmm.timeEndPeriod(1)
                time.sleep(1)
                
  

class MessageRelay(Process):
    def __init__(self, 
                 back_pipe_gui: connection.Connection,
                 camera_constructor: Callable[[int], Camera],
                 buffer: ArrayQueue,
                 start_event,
                 terminate_event,
                 *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        self.back_pipe_gui = back_pipe_gui
        self.camera_constructor = camera_constructor
        self.buffer = buffer
        self.start_event = start_event
        self.terminate_event = terminate_event
        self.camera_process = None

        self.active = True

    # def terminate(self):
    #     self.active = False

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        while self.active:
            msg = self.back_pipe_gui.recv()
            if msg == 'start' and self.camera_process is None:
                self.camera_process = CameraProcess(camera_constructor=self.camera_constructor,
                                                    start_event=self.start_event,
                                                    terminate_event=self.terminate_event,
                                                    buffer=self.buffer)
                self.camera_process.start()
                self.start_event.set()


            elif msg == 'start' and self.camera_process:
                print('start received')
                self.start_event.set()

            elif msg == 'stop':
                print('stop received')
                self.start_event.clear()

            elif msg == 'terminate':
                print('terminate received')
                self.terminate_event.set()
                self.camera_process.join()
                break


class Sink(Process):
    def __init__(self, 
                 buffer):
        super().__init__()
        self.buffer = buffer
        self.active = True
    
    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        previous_qsize = -1
        fd = open('sink_frames_AQ_200.txt', 'w')
        # winmm = ctypes.WinDLL('winmm.dll')
        # winmm.timeBeginPeriod(1)
        while self.active:
            try:
                frame = self.buffer.get(timeout=3)
                if frame is not None:
                    # print(f"got frame number {frame['index']}")
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                    current_qsize = self.buffer.qsize()
                    if current_qsize != previous_qsize:
                        print(f"Sink buffer queue size: {self.buffer.qsize()}")
                        previous_qsize = current_qsize
            
            except Empty:
                print('buffer is empty, entering exit steps')
                # self.buffer.clear()
                fd.close()
                self.active = False
                # winmm.timeEndPeriod(1)
                # break 
        print('sink loop finished')
       


# def get_from_queue(buffer):
#     while True:
#         try:
#             item = buffer.get(timeout=1)
#             shape = item['image'].shape
#             index = item['index']
#             print(shape, index)
#         except Empty:
#             buffer.clear() #need to "flush" queues for process to join?
#             break
#     print('loop over')


if __name__ == "__main__":

    width = 648
    height = 488

    # cam = camera_constructor()
    # cam.start_acquisition()
    # cam.set_exposure(1000)
    # cam.set_framerate(200)
    # t_prev = time.perf_counter()
    # timestamp_prev = 0
    # for i in range(100):
    #     frame = cam.get_frame()
    #     mod_buffer.put(frame)
    #     t = time.perf_counter()
    #     print(frame['index'], 1/(frame['timestamp']-timestamp_prev), 1/(t-t_prev))
    #     t_prev = t
    #     timestamp_prev = frame['timestamp']

    camera_constructor = partial(XimeaCamera, dev_id=0)
    
    buffer = ArrayQueue(500)

    # buffer = ModifiableRingBuffer(num_bytes=(width*height*500), 
    #                               t_refresh=1e-3)

    front_pipe, back_pipe = Pipe()
    start_event = Event()
    terminate_event = Event()

    message_process = MessageRelay(back_pipe_gui=back_pipe,
                                   start_event=start_event,
                                   terminate_event=terminate_event,
                                   camera_constructor=camera_constructor,
                                   buffer=buffer)
    

    # winmm = ctypes.WinDLL('winmm.dll')
    # winmm.timeBeginPeriod(1)


    message_process.start()

    front_pipe.send('start')
    time.sleep(5)
    sink = Sink(buffer=buffer)
    sink.start()
    time.sleep(10)
    front_pipe.send('stop')
    time.sleep(2)
    front_pipe.send('terminate')

    message_process.join()
    sink.join()

    # winmm.timeEndPeriod(1)



    # buffer = ArrayQueue(500)

    # cam = XimeaCamera(0)

    # cam.set_framerate(250)
    # cam.set_exposure(1000)

    # cam.start_acquisition()
    
    # start = time.time()
    # duration = 3

    # frames = []
    # while time.time() < start + duration: 
    #     frame = cam.get_frame()
    #     buffer.put(frame)
    #     print(frame['index'])
        
    # p1 = Process(target=get_from_queue, args=(buffer,))
    # p1.start()
    # time.sleep(8)
    # print(p1.is_alive())
    # p1.join()
    # print(p1.is_alive())

    # try:
    #     buffer.get(timeout=1)
    # except Empty:
    #     print('empty')