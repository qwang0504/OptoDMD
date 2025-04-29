from camera_tools import XimeaCamera, Camera
from old_code.camera_widgets import CameraControl
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
from arrayqueues import ArrayQueue

# TODO: synchronise recording with stim manager 
# TODO: progress bar for buffer capacity
# TODO: better naming for classes
# TODO: split relevant classes into own .py files
# TODO: rename pipes



class TestDisplayWorker(QObject):
    frameReady = pyqtSignal()

    def __init__(self, 
                 display_buffer: RingBuffer,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.display_buffer = display_buffer
        self.active = True

    def terminate(self):
        self.active = False
        # print(f'QThread ID: {int(QThread.currentThreadId())} terminated')

    def run(self):
        print('DisplayWorker running')
        print(f'QThread ID: {int(QThread.currentThreadId())}')
        time.sleep(1)
        previous_qsize = -1
        while self.active:  
            current_qsize = self.display_buffer.qsize()
            try:
                self.frame = self.display_buffer.get()
                # print current occupancy of buffer 
                if current_qsize != previous_qsize:
                    print(f'Display buffer queue size: {current_qsize}')
                    previous_qsize = current_qsize
                self.frameReady.emit()
            except Empty:
                pass
                # print('buffer empty')


class TestCamWidget(QWidget):

    def __init__(self, 
                 front_pipe_cam: connection.Connection,
                 front_pipe_save: connection.Connection,
                 display_buffer: RingBuffer,
                 width,
                 height,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.front_pipe_cam = front_pipe_cam
        self.front_pipe_save = front_pipe_save
        self.display_buffer = display_buffer
        self.width = width
        self.height = height
        self.worker = None

        self.declare_components()
        self.layout_components()

    def declare_components(self):
        self.start_button = QPushButton(self)
        self.start_button.setText('start')
        self.start_button.clicked.connect(self.start_acquisition)

        self.stop_button = QPushButton(self)
        self.stop_button.setText('stop')
        self.stop_button.clicked.connect(self.stop_acquisition)

        self.record_button = QPushButton(self)
        self.record_button.setText('record')
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton(self)
        self.stop_record_button.setText('stop recording')
        self.stop_record_button.clicked.connect(self.stop_recording)

        self.terminate_button = QPushButton(self)
        self.terminate_button.setText('terminate')
        self.terminate_button.clicked.connect(self.terminate)

        self.alive_button = QPushButton(self)
        self.alive_button.setText('alive?')
        self.alive_button.clicked.connect(self.query_alive)

        self.camera_preview = QLabel(self)
        self.camera_preview.setFixedSize(self.width, self.height)

    def layout_components(self):
        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)

        layout_record = QHBoxLayout()
        layout_record.addWidget(self.record_button)
        layout_record.addWidget(self.stop_record_button)
        
        layout_misc = QHBoxLayout()
        layout_misc.addWidget(self.terminate_button)
        layout_misc.addWidget(self.alive_button)

        layout = QVBoxLayout()
        layout.addWidget(self.camera_preview)
        layout.addLayout(layout_start_stop)
        layout.addLayout(layout_record)
        layout.addLayout(layout_misc)
        
        self.setLayout(layout)

### Callbacks
    def start_acquisition(self):
        self.front_pipe_cam.send('start')
        print('Main process sent start command')
        self.worker = TestDisplayWorker(self.display_buffer)
        self.worker.frameReady.connect(self.update_preview)
        self.qthread = QThread()
        self.worker.moveToThread(self.qthread)
        self.qthread.started.connect(self.worker.run)
        self.qthread.start()
    
    def stop_acquisition(self):
        self.front_pipe_cam.send('stop')
        time.sleep(1)
        print('Lost items from display: ', self.display_buffer.num_lost_item.value)
        if self.worker:
            self.worker.terminate()
            self.qthread.quit()

    def start_recording(self):
        # self.front_pipe_cam.send('get_params')
        # parameters = self.front_pipe_cam.recv()
        self.front_pipe_save.send('start_recording')
        self.front_pipe_cam.send('start')

    def stop_recording(self):
        self.front_pipe_save.send('stop_recording')
        self.front_pipe_cam.send('stop')

    def terminate(self):
        self.front_pipe_cam.send('terminate')
        self.front_pipe_cam.send('terminate')

    def query_alive(self):
        self.front_pipe_cam.send('alive')
        self.front_pipe_cam.send('alive')
        self.alive = self.front_pipe_cam.recv()
        self.alive = self.front_pipe_cam.recv()
        # print(self.alive)
    
    def update_preview(self):
        self.camera_preview.setPixmap(NDarray_to_QPixmap(self.worker.frame))

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            'Confirm Exit',
            'Are you sure you want to exit?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.front_pipe_cam.send('terminate')
            print("Exiting application...")
            event.accept() 
        else:
            event.ignore() 
        

class TestBufferRelay:
    def __init__(self, 
                 display_buffer: RingBuffer, 
                 camera: Camera, 
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.display_buffer = display_buffer
        self.camera = camera
        self.active = True
        self.event = threading.Event()
    
    def start_acquisition(self):
        self.camera.start_acquisition()
        time.sleep(0.5)
        self.event.set()
    
    def stop_acquisition(self):
        self.event.clear()
        time.sleep(1)
        self.camera.stop_acquisition()

    def terminate(self):
        self.active = False
        self.camera.stop_acquisition()
        time.sleep(1)
        print('Bye from FrameGrabWorker!')

    def run(self):
        while self.active:
            self.event.wait()
            frame = self.camera.get_frame()
            if frame['image'] is not None:
                self.display_buffer.put(frame['image'])


class TestDoubleBufferRelay:
    def __init__(self, 
                 display_buffer: RingBuffer, 
                 save_buffer: RingBuffer,
                 camera: Camera, 
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        self.camera = camera
        self.active = True
        self.event = threading.Event()
    
    def start_acquisition(self):
        self.camera.start_acquisition()
        time.sleep(0.5)
        self.event.set()
    
    def stop_acquisition(self):
        self.event.clear()
        time.sleep(1)
        self.camera.stop_acquisition()

    def terminate(self):
        self.active = False
        self.camera.stop_acquisition()
        time.sleep(1)
        print('Bye from DoubleBufferRelay!')
    
    def run(self):
        while self.active:
            self.event.wait()
            frame = self.camera.get_frame()
            if frame['image'] is not None:
                self.display_buffer.put(frame['image'])
                self.save_buffer.put(frame['image'])


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
        # self.parameters = parameters
        
        self.controls = [
                'frame_rate', 
                'exposure', 
                'gain', 
                'offsetX', 
                'offsetY', 
                'height', 
                'width'
            ]

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
        fps = 300
        fourcc = 'XVID'


        self.video_writer = OpenCV_VideoWriter(height=height,
                                               width=width,
                                               fps=fps,
                                               fourcc=fourcc)

        if self.video_writer:
            print('Video writer initialised')

    def run(self):
        self.init_videowriter() 
        print('FrameSaveWorker running')
        time.sleep(1)
        previous_qsize = -1
        while self.active:  
            current_qsize = self.save_buffer.qsize()
            try:
                self.frame = self.save_buffer.get()
                self.video_writer.write_frame(self.frame)
                # print current occupancy of buffer 
                if current_qsize != previous_qsize:
                    print(f'Save buffer queue size: {current_qsize}')
                    previous_qsize = current_qsize
                
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
        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        self.active = True
        self.save_worker = None

    def run(self):
        print('SaveProcess started')
        while self.active:
            msg = self.back_pipe.recv()
            # if isinstance(msg, dict):
            #     self.save_worker = TestFrameSaveWorker(save_buffer=RingBuffer,
            #                                            parameters=msg)
            
            if msg == 'start_recording' and self.save_worker is None:
                self.save_worker = TestFrameSaveWorker(save_buffer=self.save_buffer)
                self.worker_thread = Thread(target=self.save_worker.run)
                self.worker_thread.start()

            elif msg == 'stop_recording':
                self.save_worker.video_writer.close()
                self.save_worker.active = False
                self.worker_thread.join()
                self.save_worker = None

            # elif msg == 'terminate':

            # elif msg == 'alive':
        

class TestCamProcess(Process):
    def __init__(self, 
                 back_pipe: connection.Connection, #because Pipe is not a type but a function
                 display_buffer: RingBuffer,
                 save_buffer: RingBuffer,
                 camera_constructor: Callable[[int], Camera],
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.back_pipe = back_pipe
        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        self.camera_constructor = camera_constructor
        self.active = True
        self.display_worker = None
        self.save_worker = None

        self.controls = [
                'frame_rate', 
                'exposure', 
                'gain', 
                'offsetX', 
                'offsetY', 
                'height', 
                'width'
            ]

    # add some init method and cleanup method for before and after while poop 
    def init_cam(self):
        self.camera = self.camera_constructor()
        print(f'Exposure: {self.camera.get_exposure()}')
        print(f'Frame rate: {self.camera.get_framerate()}')
        self.camera.set_exposure(2000)
        self.camera.set_framerate(250)

    def run(self):
        print('CamProcess started')
        self.init_cam()
        while self.active: 
            msg = self.back_pipe.recv()
            if msg == 'start':
                print(f'CamProcess received {msg} message')
                if self.display_worker is None:
                    self.display_worker = TestBufferRelay(display_buffer=self.display_buffer, 
                                                              camera=self.camera)
                    self.thread = Thread(target=self.display_worker.run)
                    self.thread.start()
                self.display_worker.start_acquisition()
                
            elif msg == 'stop' and self.display_worker:
                print(f'CamProcess received {msg} message')
                self.display_worker.stop_acquisition()

            elif msg == 'get_params':
                print(f'CamProcess received {msg} message')

            elif msg == 'start_recording':
                print(f'CamProcess received {msg} message')
                if self.display_worker: 
                    self.display_worker.terminate()
                    self.display_worker = None
                
                if self.save_worker is None:
                    self.save_worker = TestDoubleBufferRelay(display_buffer=self.display_buffer,
                                                        save_buffer=self.save_buffer,
                                                        camera=self.camera)
                    self.thread = Thread(target=self.save_worker.run)
                    self.thread.start()
                self.save_worker.start_acquisition()
        
            elif msg == 'stop_recording':
                print(f'CamProcess received {msg} message')
                self.save_worker.terminate()
                self.thread.join()
                self.save_worker = None

            elif msg == 'terminate':
                if self.save_worker or self.display_worker:
                    self.save_worker.terminate()
                    self.display_worker.terminate()
                    self.thread.join()
                    self.test_worker = None
                self.active = False

            elif msg == 'alive':
                alive = self.is_alive()
                self.back_pipe.send(alive)

    
if __name__ == "__main__":
    # camera = XimeaCamera(0)   
    # width = camera.get_width()
    # height = camera.get_height()
    # print(width, height)

    width = 648
    height = 488
    
    camera_constructor = partial(XimeaCamera, dev_id=0)

    # display_buffer = RingBuffer(num_items=200, 
    #                             data_type=np.uint8, 
    #                             item_shape=(height, width))

    # save_buffer = RingBuffer(num_items=200,
    #                          data_type=np.uint8,
    #                          item_shape=(height, width))
    
    display_buffer = ArrayQueue(200)
    save_buffer = ArrayQueue(500)
    
    front_pipe_cam, back_pipe_cam = Pipe()
    front_pipe_save, back_pipe_save = Pipe()

    cam_process = TestCamProcess(back_pipe=back_pipe_cam, 
                                 display_buffer=display_buffer, 
                                 save_buffer=save_buffer,
                                 camera_constructor=camera_constructor)
    cam_process.start()
    print(cam_process.name)
    print('CamProcess is alive: ', cam_process.is_alive())

    save_process = TestSaveProcess(back_pipe=back_pipe_save,
                                   save_buffer=save_buffer)

    save_process.start()

    app = QApplication(sys.argv)

    widget = TestCamWidget(front_pipe_cam=front_pipe_cam,
                           front_pipe_save=front_pipe_save,
                           display_buffer=display_buffer,
                           width=width,
                           height=height)
    
    widget.show()

    # Start the Qt event loop   
    sys.exit(app.exec())

    ## define the camera before the run() method as an initialise() method, also implement some cleanup after while loops
    ## probably define cameras within the worker threads 
    ## numpy.shape by default is (height, width)
# https://github.com/ElTinmar/ZebVR/blob/main/ZebVR/workers/queue_monitor.py --> logging queue status
# https://github.com/ElTinmar/dagline/blob/main/dagline/worker.py --> try except block