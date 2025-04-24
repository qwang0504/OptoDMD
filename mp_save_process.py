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
from queue import Empty, Full
import cv2
from arrayqueues import ArrayQueue
import ctypes
from video_tools import FFMPEG_VideoWriter_CPU_Grayscale


class SaveProcess(Process):
    def __init__(self, 
                 back_pipe_save: connection.Connection,
                 save_buffer: ArrayQueue,
                 start_event, 
                 terminate_event,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.back_pipe_save = back_pipe_save
        self.save_buffer = save_buffer
        self.start_event = start_event
        self.terminate_event = terminate_event
        self.active = True

    def get_params(self):
        params = self.back_pipe_save.recv()
        print('Received parameters')
        for key, value in params.items():
            setattr(self, key, value)

    def init_videowriter(self):

        height = 488
        width = 648
        fps = 200

        self.video_writer = FFMPEG_VideoWriter_CPU_Grayscale(height=height,
                                                             width=width,
                                                             codec='h264',
                                                             fps=fps,
                                                             q=10,
                                                             profile='high',
                                                             preset='ultrafast',
                                                             filename='FFMPEG_H264_q10_200_mp_test3.mp4')
        
    def release_file(self):
        self.video_writer.close()
        # self.termination_event.set()
    
    def run(self):
        while not self.terminate_event.is_set():
            self.get_params()
            self.init_videowriter()
            while self.start_event.is_set():
                frame = self.save_buffer.get()
                if frame['image'].sum() > 0:
                    self.video_writer.write_frame(frame['image'])
                else: 
                    self.video_writer.close()
                    break
        
        print('SaveProcess finished, exiting')



class FrameWorker:
    def __init__(self, 
                 save_buffer: ArrayQueue,
                 termination_event):
        super().__init__()
        self.buffer = save_buffer
        self.active = True
        self.termination_event = termination_event
    
    def init_videowriter(self):
        height = 488
        width = 648
        fps = 200

        self.video_writer = FFMPEG_VideoWriter_CPU_Grayscale(height=height,
                                                             width=width,
                                                             codec='h264',
                                                             fps=fps,
                                                             q=10,
                                                             profile='high',
                                                             preset='superfast',
                                                             filename='FFMPEG_H264_q10_200_test1.mp4')
        
    def release_file(self):
        self.video_writer.close()
        # self.termination_event.set()

    def terminate(self):
        self.active = False
        
    def run(self):
        print('FrameWorker running')
        self.init_videowriter()
        self.previous_qsize = -1
        fd = open('Video_AQ_200.txt', 'w')
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
                    self.release_file()
                    print(f'{self.video_writer.filename} released')
                    continue

                if self.current_qsize != self.previous_qsize:

                    print(f'Sink buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
            
            except Full:
                print('Save buffer full')
                pass

        winmm.timeEndPeriod(1)
        print('FrameWorker exiting')


class SaveProcessThreads(Process):
    def __init__(self, 
                 back_pipe: connection.Connection, 
                 save_buffer: ArrayQueue,
                 sentinel: np.ndarray,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)
    
        self.back_pipe = back_pipe
        self.save_buffer = save_buffer
        self.sentinel = sentinel
        self.active = True
        self.worker = None
        self.termination_event = Event()

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)
        while self.active:
            msg = self.back_pipe.recv()
            
            if msg == 'start_recording':
                print(f'SinkProcess received {msg} message')
                if self.worker is None:
                    self.worker = FrameWorker(buffer=self.save_buffer,
                                              termination_event=self.termination_event)
                    self.thread = Thread(target=self.worker.run)
                    self.thread.start()
                # else:
                #     self.thread.start()

            elif msg == 'stop_recording':
                print(f'SaveProcess received {msg} message')
                # self.thread.join()
                # print('FrameWorker released')
                # self.thread = None
                # self.worker = None
                self.save_buffer.put(self.sentinel)
                
            elif msg == 'terminate':
                self.worker.terminate()
                self.thread.join()
                self.active = False
                winmm.timeEndPeriod(1)
        print('SaveProcess exiting')