from camera_tools import Camera
import sys
import numpy as np
import psutil
from ipc_tools import ModifiableRingBuffer
import multiprocessing
from multiprocessing import Process, connection
import threading
from threading import Thread
from functools import partial
from typing import Callable
import time
from queue import Empty, Full
import cv2
from arrayqueues import ArrayQueue
import ctypes
from ximea.xiapi import Xi_error

# TODO: experiment with reusing threads 


class CameraProcess(Process):
    def __init__(self,
                 back_pipe_cam: connection.Connection,
                 camera_constructor: Callable[[int], Camera],
                 display_buffer: ArrayQueue,
                 save_buffer: ArrayQueue,
                 start_event,
                 terminate_event,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.back_pipe_cam = back_pipe_cam
        self.camera_constructor = camera_constructor

        self.start_event = start_event
        self.terminate_event = terminate_event

        self.display_buffer = display_buffer
        self.save_buffer = save_buffer

        self.mode = None
        self.active = True

        self.controls = [
            'framerate', 
            'exposure', 
            'gain', 
            'height', 
            'width'
        ]
        
    def init_cam(self):
        self.camera = self.camera_constructor()
        
        self.camera.set_framerate(200)
        self.camera.set_exposure(2000)

        init_params = {}
    
        for attr in self.controls:
            value = getattr(self.camera, 'get_' + attr)()
            range = getattr(self.camera, 'get_' + attr + '_range')()
            increment = getattr(self.camera, 'get_' + attr + '_increment')()
            init_params[attr] = {'value' : value,
                                 'range': range, 
                                 'increment': increment}
        
        self.back_pipe_cam.send(init_params)

        print('Camera initialised')

    def start_acquisition(self):
        self.camera.start_acquisition()
        # self.start_event.set()
    
    def stop_acquisition(self):
        self.camera.stop_acquisition()

    def update(self):
        msg = self.back_pipe_cam.recv()
        if isinstance(msg, dict):
            set_method = getattr(self.camera, msg['command'], None)
            set_method(msg['value'])    
            updated_cam_params = {}
            for attr in ['framerate', 'exposure', 'gain']:
                updated_value = getattr(self.camera, 'get_' + attr)()
                updated_range = getattr(self.camera, 'get_' + attr + '_range')()
                updated_increment = getattr(self.camera, 'get_' + attr + '_increment')()
                updated_cam_params[attr] = {'value': updated_value, 
                                            'range': updated_range, 
                                            'increment': updated_increment}
            self.frame_interval = np.round(updated_cam_params['framerate']['value'] / 60) #display at 60 fps
            self.back_pipe_cam.send(updated_cam_params)

        elif isinstance(msg, str):
            self.mode = msg

    def display_mode(self):
        self.start_acquisition()
        self.previous_qsize = -1
        fd = open('cam_frames_AQ_250_display.txt', 'w')
        while self.start_event.is_set():
            if self.back_pipe_cam.poll():
                self.update()
            else: 
                frame = self.camera.get_frame()
                if frame is not None:
                    self.display_buffer.put(frame)
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
            
                self.current_qsize = self.display_buffer.qsize()
                if self.current_qsize != self.previous_qsize:
                    print(f'cam buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize

        self.stop_acquisition()
        fd.close()
        self.mode = None
        print('Acquisition stopped, exiting display mode')

    def save_mode(self):
        self.start_acquisition()
        # self.previous_qsize = -1
        fs = open('cam_frames_AQ_250_save.txt', 'w')
        fd = open('cam_frames_AQ_250_display_ds.txt', 'w')
        frame_count = 0
        while self.start_event.is_set():
            frame = self.camera.get_frame()
            if frame is not None:
                frame_count += 1
                self.save_buffer.put(frame)
                fs.write(f"{frame['index']}, {frame['timestamp']}\n")
                if frame_count >= self.frame_interval:
                # if frame_count % 10 == 0:
                    self.display_buffer.put(frame)
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
                    frame_count = 0
            
            # self.current_qsize = self.save_buffer.qsize()
            # if self.current_qsize != self.previous_qsize:
            #     print(f'save buffer queue size: {self.current_qsize}')
            #     self.previous_qsize = self.current_qsize
        self.stop_acquisition()
        fs.close()
        fd.close()
        self.mode = None
        print('Acquisition stopped, exiting save mode')

    def run(self):
        # winmm = ctypes.WinDLL('winmm.dll')
        # winmm.timeBeginPeriod(1)
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_cam()
        # self.start_acquisition()
        while not self.terminate_event.is_set():
            self.update()
            if self.mode == 'display':
                self.display_mode()
            elif self.mode == 'save':
                self.save_mode()
            elif self.mode == None:
                continue
            else: 
                break
        print('CameraProcess finished, exiting')



class CameraProcessThreads(Process):
    def __init__(self, 
                 back_pipe_cam: connection.Connection, 
                 display_buffer: ArrayQueue,
                 save_buffer: ArrayQueue,
                 camera_constructor: Callable[[int], Camera],
                 start_event: threading.Event,
                 sentinel: np.ndarray,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.back_pipe_cam = back_pipe_cam

        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        
        self.camera_constructor = camera_constructor
        self.start_event = start_event
        self.sentinel = sentinel

        self.display_worker = None
        self.save_worker = None
        self.thread = None
        
        self.active = True

    # add some init method and cleanup method for before and after while poop 
    def init_cam(self):
        self.camera = self.camera_constructor()
        self.camera.set_exposure(4800)
        self.camera.set_framerate(200)
        self.camera.set_gain(7.4)
        # print(f'Exposure: {self.camera.get_exposure()}') #exposure time in microseconds
        # print(f'Frame rate: {self.camera.get_framerate()}')

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.init_cam()
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)

        while self.active: 
            
            msg = self.back_pipe_cam.recv()
            
            if msg == 'start_acquisition':
                print(f'CameraProcess received {msg} message')
                if self.display_worker and self.thread is None:
                    self.display_worker = BufferRelay(buffer=self.display_buffer,
                                                      camera=self.camera,
                                                      start_event=self.start_event,
                                                      sentinel=self.sentinel)
                    self.thread = Thread(target=self.display_worker.run)
                    self.thread.start()
                    self.display_worker.start_acquisition()
                else: 
                    self.display_worker.start_acquisition()
        
            elif msg == 'stop_acquisition':
                print(f'CameraProcess received {msg} message')
                if self.display_worker:
                    self.display_worker.stop_acquisition()
                    # self.display_buffer.put(self.sentinel)
                    # self.thread.join()
                    # self.thread = None
                    # self.display_worker = None
                else:
                    print('Acquisition not started')

            elif msg == 'start_recording':
                print(f'CameraProcess received {msg} message')
                if self.display_worker:
                    self.display_worker.stop_acquisition()
                    self.start_event.set()
                    self.thread.join()
                    self.thread = None
                    self.display_worker = None

                if self.save_worker and self.thread is None:
                    self.save_worker = DoubleBufferRelay(display_buffer=self.display_buffer,
                                                        save_buffer=self.save_buffer,
                                                        camera=self.camera)
                    self.thread = Thread(target=self.save_worker.run)
                    self.thread.start()
                    self.save_worker.start_acquisition()

            elif msg == 'stop_recording':
                print(f'CameraProcess received {msg} message')
                if self.save_worker:
                    self.save_worker.stop_acquisition()
                    # self.save_buffer.put(self.sentinel)
                    # self.display_buffer.put(self.sentinel)
                    self.thread.join()
                    self.thread = None
                    self.save_worker = None
                else:
                    print('Acquisition not started')
                
            elif msg == 'terminate':
                self.active = False
                winmm.timeEndPeriod(1)
        print('CameraProcess exiting')
                

class BufferRelay:
    def __init__(self, 
                 buffer: ArrayQueue, 
                 camera: Camera,
                 start_event: threading.Event,
                 sentinel: np.ndarray):

        self.buffer = buffer
        self.camera = camera
        self.start_event = start_event
        self.sentinel = sentinel
        self.active = True
    
    def start_acquisition(self):
        self.camera.start_acquisition()
        self.start_event.set()
    
    def stop_acquisition(self): 
        self.start_event.clear()
        time.sleep(0.5)
        self.camera.stop_acquisition()
        # self.buffer.put(self.sentinel)

    def terminate(self):
        self.active = False

    def run(self):
        print('BufferRelay worker started')
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)
        self.previous_qsize = -1
        fd = open('BR_source_AQ_200.txt', 'w')
        while self.active:
            self.start_event.wait()
            self.current_qsize = self.buffer.qsize()
            try: 
                frame = self.camera.get_frame()
                if frame['image'] is not None:
                    self.buffer.put(frame)
                    fd.write(f"{frame['index']}, {frame['timestamp']}\n")
            except Xi_error:
                self.terminate()

            if self.current_qsize != self.previous_qsize:
                    print(f'Camera buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
        fd.close()
        winmm.timeEndPeriod(1)
        print('BufferRelay finished, exiting')


class DoubleBufferRelay:
    def __init__(self, 
                 display_buffer: ArrayQueue, 
                 save_buffer: ArrayQueue,
                 sentinel: np.ndarray,
                 camera: Camera):
        
        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        self.camera = camera
        self.sentinel = sentinel
        self.active = True
    
    def start_acquisition(self):
        self.camera.start_acquisition()
    
    def stop_acquisition(self): 
        self.active = False
        time.sleep(0.5)
        self.camera.stop_acquisition()
        self.display_buffer.put(self.sentinel)
        self.save_buffer.put(self.sentinel)

    def run(self):
        print('DoubleBufferRelay worker started')
        winmm = ctypes.WinDLL('winmm.dll')
        winmm.timeBeginPeriod(1)
        self.previous_qsize = -1
        fd = open('DBR_source_AQ_200.txt', 'w')
        while self.active:
        # if self.event.is_set():
            self.current_qsize = self.save_buffer.qsize()
            frame = self.camera.get_frame()
            if frame['image'] is not None:
                self.save_buffer.put(frame)
                self.display_buffer.put(frame)
                fd.write(f"{frame['index']}, {frame['timestamp']}\n")
            if self.current_qsize != self.previous_qsize:
                    print(f'Save buffer queue size: {self.current_qsize}')
                    self.previous_qsize = self.current_qsize
        fd.close()
        winmm.timeEndPeriod(1)
        print('DoubleBufferRelay finished, exiting')
    

    
# controls = ['framerate', 'exposure', 'gain', 'height', 'width']
# params = {}
# for attr in controls:
#     value = getattr(cam, 'get_' + attr)()   
#     range = getattr(cam, 'get_' + attr + '_range')()
#     increment = getattr(cam, 'get_' + attr + '_increment')()
#     params[attr] = {'value': value,
#                     'range': range,
#                     'increment': increment}

# start = time.time()
# duration = 5
# frames1 =  open('phase2.txt', 'w')
# cam.start_acquisition()
# while time.time() < start + duration:
#     frame = cam.get_frame()
#     frames1.write(f"{frame['index']}, {frame['timestamp']}\n")
# frames1.close()
# cam.stop_acquisition()


# if __name__ == "__main__":
    
#     # winmm = ctypes.WinDLL('winmm.dll')
#     # winmm.timeBeginPeriod(1)

#     width = 648
#     height = 488

#     camera_constructor = partial(XimeaCamera, dev_id=0)
    
#     # buffer = ModifiableRingBuffer(num_bytes=(width*height*100), 
#     #                               t_refresh=1e-3)
    
#     buffer = ArrayQueue(100)

#     front_pipe_cam, back_pipe_cam = Pipe()
#     front_pipe_sink, back_pipe_sink = Pipe()

#     start_event = Event()
#     terminate_event = Event()

#     start_time = time.perf_counter_ns()
#     print(start_time)

#     camera_process = CameraProcess(back_pipe=back_pipe_cam,
#                                     buffer=buffer,
#                                     camera_constructor=camera_constructor,
#                                     start_time=start_time)
    
#     sink_process = Sink(back_pipe=back_pipe_sink,
#                         buffer=buffer,
#                         start_time=start_time)
    
#     camera_process.start()
#     sink_process.start()

#     time.sleep(5)
    
#     front_pipe_cam.send('start')
#     # time.sleep(2)
#     front_pipe_sink.send('start')

#     time.sleep(30)

#     front_pipe_cam.send('stop')
#     front_pipe_sink.send('stop')

#     # time.sleep(3)

#     front_pipe_cam.send('terminate')
#     front_pipe_sink.send('terminate')
    
#     # time.sleep(1)

#     camera_process.join()
#     sink_process.join()

#     # winmm.timeEndPeriod(1)