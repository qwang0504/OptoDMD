from camera_tools import XimeaCamera, Camera
from camera_widgets import CameraControl
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QMessageBox
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, QMutex, QWaitCondition
from qt_widgets import NDarray_to_QPixmap
import sys
import numpy as np
import json
import psutil
from ipc_tools import RingBuffer, Logger
import multiprocessing
from multiprocessing import Process, Pipe, Queue, connection
import threading
from threading import Thread
from functools import partial
from typing import Callable
import time
from queue import Empty
import logging
# from video_writer import OpenCV_VideoWriter
from video_tools import OpenCV_VideoWriter, FFMPEG_VideoWriter_CPU_Grayscale
import matplotlib.pyplot as plt
import cv2
from camera_tools import BaseFrame

class TestCamProcess(Process):
    def __init__(self, 
                 back_pipe: connection.Connection, #because Pipe is not a type but a function
                 save_buffer: RingBuffer,
                 camera_constructor: Callable[[int], Camera],
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.back_pipe = back_pipe
        self.save_buffer = save_buffer
        self.camera_constructor = camera_constructor
        self.active = True
        self.save_worker = None

    # add some init method and cleanup method for before and after while poop 
    def init_cam(self):
        self.camera = self.camera_constructor()
        print(f'Exposure: {self.camera.get_exposure()}')
        print(f'Frame rate: {self.camera.get_framerate()}')
        self.camera.set_exposure(1000)
        self.camera.set_framerate(250)

    def run(self):
        print('CamProcess started')
        self.init_cam()
        print(self.camera.get_framerate())
        while self.active: 
            msg = self.back_pipe.recv()
            if msg == 'start_recording':
                print(f'CamProcess received {msg} message')
                if self.save_worker is None:
                    self.save_worker = TestBufferRelay(buffer=self.save_buffer,
                                                       camera=self.camera)
                    self.thread = Thread(target=self.save_worker.run)
                    self.thread.start()
                self.save_worker.start_acquisition()
        
            elif msg == 'stop_recording':
                print(f'CamProcess received {msg} message')
                self.save_worker.stop_acquisition()
                self.save_worker.terminate()
                self.thread.join()
                self.save_worker = None

            elif msg == 'alive':
                alive = self.is_alive()
                self.back_pipe.send(alive)
                
            elif msg == 'terminate':
                self.active = False


class TestBufferRelay:
    def __init__(self, 
                 buffer: RingBuffer, 
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
        time.sleep(0.5)
        self.camera.stop_acquisition()

    def terminate(self):
        self.active = False
        # self.camera.stop_acquisition()
        # time.sleep(1)
        print('Bye from BufferRelay!')

    def run(self):
        fd = open('cam_frame_count.txt', 'w')
        while self.active:
            self.event.wait()
            frame = self.camera.get_frame()
            if frame.image is not None:
                self.buffer.put(frame.image)
                print(frame.index, frame.timestamp)
            fd.write(f"{frame.index}, {frame.timestamp}\n")
        fd.close()


class TestFrameSaveWorker: 
    #create an instance for each record button press
    def __init__(self, 
                save_buffer: RingBuffer,
                # parameters: dict,
                *args, 
                **kwargs):
        super().__init__(*args, **kwargs)
        
        self.save_buffer = save_buffer
        self.active = True
        self.video_writer = None
        
        # self.controls = [
        #         'frame_rate', 
        #         'exposure', 
        #         'gain', 
        #         'offsetX', 
        #         'offsetY', 
        #         'height', 
        #         'width'
        #     ]

    def init_videowriter(self):
        # height = self.parameters['height']
        # width = self.parameters['width']
        # fps = self.parameters['frame_rate']
        # fourcc = self.parameters['fourcc']
        # video_name = self.parameters['video_name']
        # file_path = self.parameters['file_path']
        # gain = self.parameters['gain']
        # offsetX = self.parameters['offsetX']
        # offsetY = self.parameters['offsetY']

        height = 488
        width = 648
        fps = 250

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter('output.avi', fourcc, fps, (width, height), False)

        # self.video_writer = OpenCV_VideoWriter(height=488,
        #                                        width=648,
        #                                        fps=200)

        if self.video_writer:
            print('Video writer initialised')

    def terminate(self):
        while self.current_qsize > 0:
            continue
        self.video_writer.release()
        self.active = False
        print('Lost items: ', self.save_buffer.num_lost_item.value)

    def run(self):
        # f = open('save_frame_count.txt', 'w')
        self.init_videowriter() 
        print('FrameSaveWorker running')
        # time.sleep(1)
        self.previous_qsize = -1
        
        while self.active:  
            self.current_qsize = self.save_buffer.qsize()
            try:
                frame = self.save_buffer.get()
                if frame is not None:
                    self.frame = frame
                    self.video_writer.write(self.frame)
                # print current occupancy of buffer 
                if self.current_qsize != self.previous_qsize:
                    print(f'Save buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
            except Empty:
                pass
                # print('buffer empty')


class TestSaveProcess(Process):
    def __init__(self, 
                back_pipe: connection.Connection, 
                save_buffer: RingBuffer,
                *args, #need camera parameters!! 
                **kwargs):
        super().__init__(*args, **kwargs)
    
        self.back_pipe = back_pipe
        self.save_buffer = save_buffer
        self.active = True
        self.save_worker = None

    def run(self):
        print('SaveProcess started')
        while self.active:
            msg = self.back_pipe.recv()
            
            if msg == 'start_recording':
                print(f'SaveProcess received {msg}')
                self.save_worker = TestFrameSaveWorker(save_buffer=self.save_buffer)
                self.worker_thread = Thread(target=self.save_worker.run)
                self.worker_thread.start()

            elif msg == 'stop_recording':
                print(f'SaveProcess received {msg}')
                self.save_worker.terminate()
                self.worker_thread.join()
                print('released')
  
                # self.worker_thread.join()
                # self.save_worker = None

            elif msg == 'terminate':
                self.active = False

            # elif msg == 'alive':


if __name__ == "__main__":

    width = 648
    height = 488

    camera_constructor = partial(XimeaCamera, dev_id=0)

    front_pipe_save, back_pipe_save = Pipe()
    front_pipe_cam, back_pipe_cam = Pipe()

    save_buffer = RingBuffer(num_items=300,
                             data_type=np.uint8,
                             item_shape=(height, width))
    
    save_process = TestSaveProcess(back_pipe=back_pipe_save,
                                   save_buffer=save_buffer)
    
    cam_process = TestCamProcess(back_pipe=back_pipe_cam,
                                 save_buffer=save_buffer,
                                 camera_constructor=camera_constructor)
    
    cam_process.start()
    save_process.start()


    front_pipe_cam.send('start_recording')
    front_pipe_save.send('start_recording')

    time.sleep(10)
    
    front_pipe_cam.send('stop_recording')
    front_pipe_save.send('stop_recording')