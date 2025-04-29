from PyQt5.QtCore import pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QObject, QThread
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit, QFileDialog
from qt_widgets import LabeledDoubleSpinBox, LabeledSliderDoubleSpinBox, LabeledSpinBox, NDarray_to_QPixmap
from camera_tools import Camera
import numpy as np
from old_code.video_writer import OpenCV_VideoWriter
import cv2 
import time
from pathlib import Path
from datetime import datetime
import os
import zmq
import json
from multiprocessing import Process, Pipe, Queue, Event
from ipc_tools import RingBuffer
from threading import Thread

# TODO: synchronise recording with stim manager 

class CameraWorker:
    def __init__(self, 
                 camera: Camera, 
                 display_buffer: RingBuffer, 
                 save_buffer: RingBuffer,
                 *args, 
                 **kwargs):
        self.camera = camera
        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        self.active = True
        self.acquisition_started = False
    
    def start_acquisition(self):
        self.camera.start_acquisition()
        time.sleep(1)
        self.acquisition_started = True

    def stop_acquisition(self):
        self.acquisition_started = False
        time.sleep(1)
        self.camera.stop_acquisition()

    def terminate(self):
        self.active = False 

    def run_display(self):
        while self.active: 
            if self.acquisition_started:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    self.display_buffer.put(frame)

    def run_save(self):
        while self.active: 
            if self.acquisition_started:
                frame = self.camera.get_frame()
                if frame.image is not None: 
                    self.display_buffer.put(frame)
                    self.save_buffer.put(frame)
                

class CameraProcess(Process):
    def __init__(self,
                 camera: Camera, 
                 back_pipe_gui: Pipe, 
                 display_buffer: RingBuffer, 
                 save_buffer: RingBuffer,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.camera = camera
        self.back_pipe_gui = back_pipe_gui
        self.display_buffer = display_buffer
        self.save_buffer = save_buffer

        # needs to get camera settings from GUI 
        # also needs to send initial camera parameters and ranges
    
        self.controls = [
                'frame_rate', 
                'exposure', 
                'gain', 
                'offsetX', 
                'offsetY', 
                'height', 
                'width'
            ]
    
    def send_default_params(self): 
        default_params = {}
        for attr in self.controls:
            value = getattr(self.camera, 'get_' + attr)()
            range = getattr(self.camera, 'get_' + attr + '_range')()
            increment = getattr(self.camera, 'get_' + attr + '_increment')()
            attr_info = {
                "value": value, 
                "range": range, 
                "increment": increment
            }
            default_params[attr] = attr_info
        self.back_pipe_gui.send(default_params)
    
    def set_camera_params(self):
        msg = self.back_pipe_gui.recv()
        # set all camera parameters from GUI inputs 
        # this needs to be responsive to any changes in the GUI... 

    def run(self):
        self.send_default_params()
        while self.active:
            msg = self.back_pipe_gui.recv()
            if msg == 'start_acquisition':
                self.camera_worker = CameraWorker(self.camera, 
                                                   self.display_buffer, 
                                                   self.save_buffer)
                self.worker_thread = Thread(target=self.camera_worker.run_display)
                self.camera_worker.start_acquisition()
                self.worker_thread.start()
               
            elif msg == 'stop_acquisition' and self.camera_worker is not None:
                self.camera_worker.stop_acquisition()

            elif msg == 'start_recording':
                self.camera_worker = CameraWorker(self.camera, 
                                                   self.display_buffer, 
                                                   self.save_buffer)
                self.worker_thread = Thread(target=self.camera_worker.run_save)
                self.camera_worker.start_acquisition()
                self.worker_thread.start()

            elif msg == 'stop_recording':
                self.camera.stop_acquisition()


class SaveWorker:
    def __init__(self, 
                 frame_rate, 
                 exposure, 
                 gain, 
                 height,
                 width,
                 file_name,
                 file_path,
                 fourcc,
                 buffer,
                 *args, 
                 **kwargs):

        self.fps = frame_rate
        self.exposure = exposure
        self.gain = gain
        self.height = height
        self.width = width
        self.file_name = file_name
        self.file_path = file_path
        self.fourcc = fourcc
        self.buffer = buffer

        self.active = True

    def init_videowriter(self):
        self.video_writer = OpenCV_VideoWriter(self.height, 
                                               self.width, 
                                               self.fps, 
                                               self.file_path, 
                                               self.fourcc)

    def run(self):
        self.init_videowriter()
        while self.active: 
            frame = self.buffer.get()
            self.video_writer.write(frame)
    
    def stop(self):
        #stop saving frames
        self.video_writer.close()

    def terminate(self):
        self.active = False 
        


class VideoWriterProcess(Process):
    def __init__(self,
                 save_buffer: RingBuffer, 
                 back_pipe: Pipe,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.save_buffer = save_buffer
        self.back_pipe = back_pipe
        self.active = True

    def run(self):
        while self.active:
            msg = self.back_pipe.recv() #blocks?
            if isinstance(msg, dict) and 'start' in msg:
                params = msg['start']
                self.save_worker = SaveWorker(params, save_buffer)
                # for param, value in msg['start'].items():
                #     setattr(self, param, value)
                self.worker_thread = Thread(target=self.save_worker.run)
                self.worker_thread.start()
            
            elif msg == 'stop' and self.save_worker:
                self.save_worker.stop()
                self.worker_thread.join()
                #stop thread safely

            elif msg == 'exit':
                self.active == False
                print('VideoWriterProcess loop has stopped')





                    
class CameraWidget(QWidget):
    def __init__(self, 
                 front_pipe_camera: Pipe, 
                 front_pipe_saver: Pipe,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.acquisition_started = False
        self.record_started = False 


        self.controls = [
            'framerate', 
            'exposure', 
            'gain', 
            'offsetX', 
            'offsetY', 
            'height', 
            'width'
        ]
        
        self.declare_components()
        self.layout_components()
        
    def create_spinbox(self, attr: str):
        '''
        Creates spinbox with correct label, value, range and increment
        as specified by the camera object. Connects to relevant
        callback.
        WARNING This is compact but a bit terse and introduces dependencies
        in the code. 
        '''
        if attr in ['framerate', 'exposure', 'gain']:
            setattr(self, attr + '_spinbox', LabeledSliderDoubleSpinBox(self))
        else:
            setattr(self, attr + '_spinbox', LabeledDoubleSpinBox(self))
        spinbox = getattr(self, attr + '_spinbox')
        spinbox.setText(attr)
        
        value = getattr(self.camera, 'get_' + attr)()
        range = getattr(self.camera, 'get_' + attr + '_range')()
        increment = getattr(self.camera, 'get_' + attr + '_increment')()
        
        if (
            value is not None 
            and range is not None
            and increment is not None
        ):
            spinbox.setRange(range[0],range[1])
            spinbox.setSingleStep(increment)
            spinbox.setValue(value)
        else:
            spinbox.setDisabled(True)

        callback = getattr(self, 'set_' + attr)
        spinbox.valueChanged.connect(callback)

    def update_values(self):

        for attr in self.controls:
            spinbox = getattr(self, attr + '_spinbox')
            value = getattr(self.camera, 'get_' + attr)()
            range = getattr(self.camera, 'get_' + attr + '_range')()
            increment = getattr(self.camera, 'get_' + attr + '_increment')()

            if (
                value is not None 
                and range is not None
                and increment is not None
            ):
                spinbox.setRange(range[0],range[1])
                spinbox.setSingleStep(increment)
                spinbox.setValue(value)
            else:
                spinbox.setDisabled(True)

    def declare_components(self):

        # Basic camera controls ----------------------------------
         
        self.start_button = QPushButton(self)
        self.start_button.setText('start')
        self.start_button.clicked.connect(self.start_acquisition)

        self.stop_button = QPushButton(self)
        self.stop_button.setText('stop')
        self.stop_button.clicked.connect(self.stop_acquisition)

        self.record_button = QPushButton(self)
        self.record_button.setText('start recording')
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton(self)
        self.stop_record_button.setText('stop recording')
        self.stop_record_button.clicked.connect(self.stop_recording) #lock down all buttons except for stop when recording started 

        self.instructions = QLabel(self)
        self.instructions.setText('please press Enter after input')

        self.directory_button = QPushButton(self)
        self.directory_button.setText('select directory')
        self.directory_button.clicked.connect(self.select_directory)

        self.directory_label = QLabel(self)
        self.directory_label.setText('directory selected: ')
                                             
        self.fish_number_input = LabeledSpinBox(self)
        self.fish_number_input.setText('Fish number')
        self.fish_number_input.setRange(0, 999)
        self.fish_number_input.setSingleStep(1)
        self.fish_number_input.valueChanged.connect(self.set_fish_number)

        self.stimulation_number_input = LabeledSpinBox(self)
        self.stimulation_number_input.setText('Stimulation number')
        self.stimulation_number_input.setRange(0, 999)
        self.stimulation_number_input.setSingleStep(1)
        self.stimulation_number_input.valueChanged.connect(self.set_stim_number)

        
        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText('file_name.avi')
        self.file_name_input.returnPressed.connect(self.set_filename)

        self.encoding_fps_input = QLineEdit(self)
        self.encoding_fps_input.setPlaceholderText('encoding fps in integers')
        self.encoding_fps_input.returnPressed.connect(self.set_fps)

        self.fourcc_input = QLineEdit(self)
        self.fourcc_input.setPlaceholderText('fourcc code in capital letters')
        self.fourcc_input.returnPressed.connect(self.set_fourcc)

        self.acquisition_status_label = QLabel(self)
        self.acquisition_status_label.setText('Acquisition status:')
        self.acquisition_status = QLabel(self)
        if self.acquisition_started:
            self.acquisition_status.setText('Acquiring')
        else: 
            self.acquisition_status.setText('Not acquiring')

        self.camera_preview = QLabel(self)

        # controls 
        for c in self.controls:
            self.create_spinbox(c)

        # Region of interest ------------------------------------

        self.ROI_groupbox = QGroupBox('ROI:')

    def layout_components(self):

        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)
        layout_start_stop.addWidget(self.record_button)
        layout_start_stop.addWidget(self.stop_record_button)

        layout_frame = QVBoxLayout(self.ROI_groupbox)
        layout_frame.addStretch()
        layout_frame.addWidget(self.offsetX_spinbox)
        layout_frame.addWidget(self.offsetY_spinbox)
        layout_frame.addWidget(self.height_spinbox)
        layout_frame.addWidget(self.width_spinbox)
        layout_frame.addStretch()

        layout_acquisition_status = QVBoxLayout()
        layout_acquisition_status.addWidget(self.acquisition_status_label)
        layout_acquisition_status.addWidget(self.acquisition_status)

        layout_dir = QVBoxLayout()
        layout_dir.addWidget(self.directory_label)
        layout_dir.addWidget(self.directory_button)

        layout_files = QHBoxLayout()
        layout_files.addWidget(self.fish_number_input)
        layout_files.addWidget(self.stimulation_number_input)
        layout_files.addLayout(layout_dir)

        layout_controls = QVBoxLayout(self)
        layout_controls.addStretch()
        layout_controls.addWidget(self.framerate_spinbox)
        layout_controls.addWidget(self.exposure_spinbox)
        layout_controls.addWidget(self.gain_spinbox)

        layout_controls.addLayout(layout_files)

        layout_controls.addWidget(self.instructions)
        layout_controls.addWidget(self.file_name_input)
        layout_controls.addWidget(self.encoding_fps_input)
        layout_controls.addWidget(self.fourcc_input)
        layout_controls.addWidget(self.camera_preview)
        layout_controls.addLayout(layout_start_stop)
        layout_controls.addWidget(self.ROI_groupbox)
        layout_controls.addLayout(layout_acquisition_status)
        layout_controls.addStretch()

# Callbacks

    def closeEvent(self, event):
        self.sender.terminate()
        self.stop_acquisition()

    def start_acquisition(self):
        if not self.acquisition_started:
            self.camera.start_acquisition()
            self.acquisition_started = True
            
    def stop_acquisition(self):
        if self.acquisition_started:
            self.camera.stop_acquisition()
            self.acquisition_started = False

    def set_exposure(self):
        self.camera.set_exposure(self.exposure_spinbox.value())
        self.update_values()

    def set_gain(self):
        self.camera.set_gain(self.gain_spinbox.value())
        self.update_values()

    def set_framerate(self):
        self.camera.set_framerate(self.framerate_spinbox.value())
        self.update_values()

    def set_offsetX(self):
        self.camera.set_offsetX(int(self.offsetX_spinbox.value()))
        self.update_values()
    
    def set_offsetY(self):
        self.camera.set_offsetY(int(self.offsetY_spinbox.value()))
        self.update_values()

    def set_width(self):
        self.camera.set_width(int(self.width_spinbox.value()))
        self.update_values()

    def set_height(self):
        self.camera.set_height(int(self.height_spinbox.value()))
        self.update_values()

    def set_filename(self):
        filename = self.file_name_input.text()
        self.file_name_input.clearFocus()
        self.filename_ready.emit(filename)

    def set_fourcc(self):
        fourcc = self.fourcc_input.text()
        self.fourcc_input.clearFocus()
        self.fourcc_ready.emit(fourcc)

    def set_fps(self):
        fps = int(self.encoding_fps_input.text())
        self.encoding_fps_input.clearFocus()
        self.fps_ready.emit(fps)

    def preview(self, image_ready: int):
        if image_ready:
            self.camera_preview.setPixmap(NDarray_to_QPixmap(self.sender.frame))


    



class CameraWidget(QWidget):
   
    def __init__(self, 
                 camera_control: CameraControl,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.queue = Queue()
        self.camera_control = camera_control
        self.acquisition_started = False
        self.record_started = False 

        self.controls = [
            'framerate', 
            'exposure', 
            'gain', 
            'offsetX', 
            'offsetY', 
            'height', 
            'width'
        ]
        
        self.declare_components()
        self.layout_components()

        # self.context = zmq.Context()
        # self.start_socket = self.context.socket(zmq.PUB)
        # self.start_socket.bind(protocol + "*:" +str(cam_port))

    # UI ---------------------------------------------------------
    
    def create_spinbox(self, attr: str):
        '''
        Creates spinbox with correct label, value, range and increment
        as specified by the camera object. Connects to relevant
        callback.
        WARNING This is compact but a bit terse and introduces dependencies
        in the code. 
        '''
        if attr in ['framerate', 'exposure', 'gain']:
            setattr(self, attr + '_spinbox', LabeledSliderDoubleSpinBox(self))
        else:
            setattr(self, attr + '_spinbox', LabeledDoubleSpinBox(self))
        spinbox = getattr(self, attr + '_spinbox')
        spinbox.setText(attr)
        
        value = getattr(self.camera, 'get_' + attr)()
        range = getattr(self.camera, 'get_' + attr + '_range')()
        increment = getattr(self.camera, 'get_' + attr + '_increment')()
        
        if (
            value is not None 
            and range is not None
            and increment is not None
        ):
            spinbox.setRange(range[0],range[1])
            spinbox.setSingleStep(increment)
            spinbox.setValue(value)
        else:
            spinbox.setDisabled(True)

        callback = getattr(self, 'set_' + attr)
        spinbox.valueChanged.connect(callback)

    def update_values(self):

        for attr in self.controls:
            spinbox = getattr(self, attr + '_spinbox')
            value = getattr(self.camera, 'get_' + attr)()
            range = getattr(self.camera, 'get_' + attr + '_range')()
            increment = getattr(self.camera, 'get_' + attr + '_increment')()

            if (
                value is not None 
                and range is not None
                and increment is not None
            ):
                spinbox.setRange(range[0],range[1])
                spinbox.setSingleStep(increment)
                spinbox.setValue(value)
            else:
                spinbox.setDisabled(True)

    def declare_components(self):

        # Basic camera controls ----------------------------------
         
        self.start_button = QPushButton(self)
        self.start_button.setText('start')
        self.start_button.clicked.connect(self.start_acquisition)

        self.stop_button = QPushButton(self)
        self.stop_button.setText('stop')
        self.stop_button.clicked.connect(self.stop_acquisition)

        self.record_button = QPushButton(self)
        self.record_button.setText('start recording')
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton(self)
        self.stop_record_button.setText('stop recording')
        self.stop_record_button.clicked.connect(self.stop_recording)

        self.instructions = QLabel(self)
        self.instructions.setText('please press Enter after input')

        self.directory_button = QPushButton(self)
        self.directory_button.setText('select directory')
        self.directory_button.clicked.connect(self.select_directory)

        self.directory_label = QLabel(self)
        self.directory_label.setText('directory selected: ')
                                             
        self.fish_number_input = LabeledSpinBox(self)
        self.fish_number_input.setText('Fish number')
        self.fish_number_input.setRange(0, 999)
        self.fish_number_input.setSingleStep(1)
        self.fish_number_input.valueChanged.connect(self.set_fish_number)

        self.stimulation_number_input = LabeledSpinBox(self)
        self.stimulation_number_input.setText('Stimulation number')
        self.stimulation_number_input.setRange(0, 999)
        self.stimulation_number_input.setSingleStep(1)
        self.stimulation_number_input.valueChanged.connect(self.set_stim_number)

        
        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText('file_name.avi')
        self.file_name_input.returnPressed.connect(self.set_filename)

        self.encoding_fps_input = QLineEdit(self)
        self.encoding_fps_input.setPlaceholderText('encoding fps in integers')
        self.encoding_fps_input.returnPressed.connect(self.set_fps)

        self.fourcc_input = QLineEdit(self)
        self.fourcc_input.setPlaceholderText('fourcc code in capital letters')
        self.fourcc_input.returnPressed.connect(self.set_fourcc)

        self.acquisition_status_label = QLabel(self)
        self.acquisition_status_label.setText('Acquisition status:')
        self.acquisition_status = QLabel(self)
        if self.acquisition_started:
            self.acquisition_status.setText('Acquiring')
        else: 
            self.acquisition_status.setText('Not acquiring')

        self.camera_preview = QLabel(self)

        # controls 
        for c in self.controls:
            self.create_spinbox(c)

        # Region of interest ------------------------------------

        self.ROI_groupbox = QGroupBox('ROI:')

    def layout_components(self):

        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)
        layout_start_stop.addWidget(self.record_button)
        layout_start_stop.addWidget(self.stop_record_button)

        layout_frame = QVBoxLayout(self.ROI_groupbox)
        layout_frame.addStretch()
        layout_frame.addWidget(self.offsetX_spinbox)
        layout_frame.addWidget(self.offsetY_spinbox)
        layout_frame.addWidget(self.height_spinbox)
        layout_frame.addWidget(self.width_spinbox)
        layout_frame.addStretch()

        layout_acquisition_status = QVBoxLayout()
        layout_acquisition_status.addWidget(self.acquisition_status_label)
        layout_acquisition_status.addWidget(self.acquisition_status)

        layout_dir = QVBoxLayout()
        layout_dir.addWidget(self.directory_label)
        layout_dir.addWidget(self.directory_button)

        layout_files = QHBoxLayout()
        layout_files.addWidget(self.fish_number_input)
        layout_files.addWidget(self.stimulation_number_input)
        layout_files.addLayout(layout_dir)

        layout_controls = QVBoxLayout(self)
        layout_controls.addStretch()
        layout_controls.addWidget(self.framerate_spinbox)
        layout_controls.addWidget(self.exposure_spinbox)
        layout_controls.addWidget(self.gain_spinbox)

        layout_controls.addLayout(layout_files)

        layout_controls.addWidget(self.instructions)
        layout_controls.addWidget(self.file_name_input)
        layout_controls.addWidget(self.encoding_fps_input)
        layout_controls.addWidget(self.fourcc_input)
        layout_controls.addWidget(self.camera_preview)
        layout_controls.addLayout(layout_start_stop)
        layout_controls.addWidget(self.ROI_groupbox)
        layout_controls.addLayout(layout_acquisition_status)
        layout_controls.addStretch()

    # Callbacks --------------------------------------------------------- 

    def closeEvent(self, event):
        self.sender.terminate()
        self.stop_acquisition()

    def start_acquisition(self):
        if not self.acquisition_started:
            self.sender.start_acquisition()
            self.acquisition_status.setText('Acquiring')
            self.record_button.setEnabled(False)
            self.stop_record_button.setEnabled(False)
            self.acquisition_started = True
            
    def stop_acquisition(self):
        if self.acquisition_started:
            self.sender.stop_acquisition()
            self.acquisition_status.setText('Not acquiring')
            self.record_button.setEnabled(True)
            self.stop_record_button.setEnabled(True)
            self.acquisition_started = False
    
    def start_recording(self):
        if not self.acquisition_started:
            self.sender.start_recording()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.record_started = True


    def stop_recording(self):
        if self.record_started:
            self.sender.stop_recording()
            self.record_button.setEnabled(True)
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.record_started = False
            self.recording_finished.emit(True)

    def set_exposure(self):
        self.camera.set_exposure(self.exposure_spinbox.value())
        self.update_values()

    def set_gain(self):
        self.camera.set_gain(self.gain_spinbox.value())
        self.update_values()

    def set_framerate(self):
        self.camera.set_framerate(self.framerate_spinbox.value())
        self.update_values()

    def set_offsetX(self):
        self.camera.set_offsetX(int(self.offsetX_spinbox.value()))
        self.update_values()
    
    def set_offsetY(self):
        self.camera.set_offsetY(int(self.offsetY_spinbox.value()))
        self.update_values()

    def set_width(self):
        self.camera.set_width(int(self.width_spinbox.value()))
        self.update_values()

    def set_height(self):
        self.camera.set_height(int(self.height_spinbox.value()))
        self.update_values()

    def set_filename(self):
        filename = self.file_name_input.text()
        self.file_name_input.clearFocus()
        self.filename_ready.emit(filename)

    def set_fourcc(self):
        fourcc = self.fourcc_input.text()
        self.fourcc_input.clearFocus()
        self.fourcc_ready.emit(fourcc)

    def set_fps(self):
        fps = int(self.encoding_fps_input.text())
        self.encoding_fps_input.clearFocus()
        self.fps_ready.emit(fps)

    def preview(self, image_ready: int):
        if image_ready:
            self.camera_preview.setPixmap(NDarray_to_QPixmap(self.sender.frame))

