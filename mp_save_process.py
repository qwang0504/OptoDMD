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
from video_writer import FFMPEG_VideoWriter_CPU_Grayscale
from pathlib import Path


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

        self.codec = 'h264'
        self.q = 10
        self.profile = 'high'

        self.fish_id = None
        self.active = True

        self.metadata = 0

    def get_params(self):
        msg = self.back_pipe_save.recv()
        # print(f'Process {self.name} received {msg}')

        if isinstance(msg, dict):
            for attr, param in msg.items():
                value = param['value']
                setattr(self, attr, value)
                # print(f'save: {attr}, {value}')

        elif msg == 'terminate':
            self.terminate()

    def terminate(self):
        self.active = False

    def init_videowriter(self):
        if self.fish_id:
            self.video_name = self.filename + str(self.trial_index)
            self.stim_folder = 'stim' + str(self.stim_number)
            self.video_path = str(Path(self.output_dir, 
                                       self.fish_id, 
                                       self.stim_folder, 
                                       self.video_name))
            self.video_writer = FFMPEG_VideoWriter_CPU_Grayscale(height=self.height,
                                                                 width=self.width,
                                                                 codec=self.codec,
                                                                 fps=self.framerate,
                                                                 q=self.q,
                                                                 profile=self.profile,
                                                                 preset='ultrafast',
                                                                 filename=self.video_path + '.mp4')
            
        else:
            self.video_name = self.filename 
            self.video_path = str(Path(self.output_dir, self.video_name))
            self.video_writer = FFMPEG_VideoWriter_CPU_Grayscale(height=self.height,
                                                                width=self.width,
                                                                codec='h264',
                                                                fps=self.framerate,
                                                                q=10,
                                                                profile='high',
                                                                preset='ultrafast',
                                                                filename=self.video_path + '.mp4')

        print('VideoWriter initialised')

    def release_file(self):
        self.video_writer.close()
        self.video_writer = None
        # self.termination_event.set()

    def generate_trial_metadata(self):
        if self.metadata == 2: #checkbox state; 0=unchecked, 2=checked
            trial_metadata = {
                'fish_id': self.fish_id,
                'trial_index': self.trial_index,
                'stim_number': self.stim_number,
                'video_start': self.video_start_time,
                'fps': self.framerate,
                'exposure': self.exposure,
                'gain': self.gain,
                'frame_width': self.width, 
                'frame_height': self.height, 
                'codec': self.codec, 
                'q': self.q,
                'profile': self.profile,
                'video_filename': self.filename
                }

            metadata_path = Path(self.video_path +'.json')
            with open(metadata_path, 'w') as file:
                json.dump(trial_metadata, file)
        
    def run(self):
        print(f'Process {self.name} running')
        while not self.terminate_event.is_set():
            self.get_params()
            if self.terminate_event.is_set():
                break 
            self.init_videowriter()
            frame_count_filename = 'save_frames' + str(self.trial_index) + '.txt'
            frame_count_path = Path(self.output_dir) / self.fish_id / self.stim_folder
            frame_count_filepath = frame_count_path / frame_count_filename
            fd = open(str(frame_count_filepath), 'w')
            
            frame_count = 0
            while self.active:
                frame = self.save_buffer.get()
                if frame_count == 0:
                    print(f'video_start_time_SAVE = {time.perf_counter_ns()}')
                if frame['image'].sum() > 0:
                    self.video_writer.write_frame(frame['image'])
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                    frame_count += 1
                else: 
                    fd.close()
                    self.release_file()
                    self.generate_trial_metadata()
                    break
            print('File saving finished')

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