# TODO record to file ?

from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QObject
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit, QFileDialog
from qt_widgets import LabeledDoubleSpinBox, LabeledSliderDoubleSpinBox, LabeledSpinBox, NDarray_to_QPixmap
from camera_tools import Camera, Frame
import numpy as np
from video_writer import OpenCV_VideoWriter
import cv2 
import time
from pathlib import Path
from datetime import datetime
import os
import zmq
import json

# TODO show camera FPS, display FPS, and camera statistics in status bar
# TODO subclass CameraWidget for camera with specifi controls



class FrameSignal(QObject):
    image_ready = pyqtSignal(np.ndarray)

class FrameSignalBool(QObject):
    image_ready = pyqtSignal(int)
    
# TODO do the same using a MP_Queue/RingBuffer/ZMQ instead
class FrameSender(QRunnable):

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera
        self.signal = FrameSignal()
        self.acquisition_started = False
        self.keepgoing = True

    def start_acquisition(self):
        self.acquisition_started = True

    def stop_acquisition(self):
        self.acquisition_started = False

    def terminate(self):
        self.keepgoing = False

    def run(self):
        while self.keepgoing:
            if self.acquisition_started:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    self.signal.image_ready.emit(frame.image)


class FrameSenderCombined(QRunnable):

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera
        self.width = int(self.camera.get_width())
        self.height = int(self.camera.get_height())
        self.writer = OpenCV_VideoWriter(height=self.height, 
                                         width=self.width)
        self.signal = FrameSignalBool()
        self.acquisition_started = False
        self.record_started = False
        self.keepgoing = True

        # self.signal.connect()

    def start_recording(self):
        self.camera.start_acquisition()        
        # self.writer.write_file = cv2.VideoWriter(filename=str(Path(self.file_dir, self.videoname)), 
        #                                          fourcc=self.fourcc, 
        #                                          fps=self.fps, 
        #                                          frameSize=(self.width, self.height), 
        #                                          isColor=self.writer.color)

        self.writer.write_file = cv2.VideoWriter(filename=str(Path(self.stim_folder, self.filename + self.video_index + '.avi')), 
                                                 fourcc=self.fourcc, 
                                                 fps=self.fps, 
                                                 frameSize=(self.width, self.height), 
                                                 isColor=self.writer.color)
        time.sleep(1)
        self.video_start_time = time.time()
        self.record_started = True
        print(self.video_start_time)
    
    def stop_recording(self):
        self.record_started = False
        self.writer.close()
        time.sleep(1)
        self.camera.stop_acquisition()

    def start_acquisition(self):
        self.camera.start_acquisition()
        time.sleep(1)
        self.acquisition_started = True

    def stop_acquisition(self):
        self.acquisition_started = False
        time.sleep(1)
        self.camera.stop_acquisition()

    def terminate(self):
        self.keepgoing = False

    def set_fps(self, fps: int):
        self.fps = fps

    def set_filename(self, filename: str):
        # video_name = filename + self.video_index+'.avi'
        # self.videoname = video_name
        self.filename = filename 
        # self.output_dir = self.file_dir+'/'+self.filename

    def set_video_index(self, index: str):
        self.video_index = index

    def set_stim_folder(self, stim_dir: str):
        self.stim_folder = stim_dir

    # def set_video_number(self, video_number: str):
    #     self.video_number = video_number

    def set_directory(self, file_dir: str):
        self.file_dir = file_dir

    def set_fourcc(self, fourcc: str):
        self.fourcc = cv2.VideoWriter_fourcc(*fourcc)

    def run(self):
        # fd = open('timings_2.txt', 'w')
        # self.i = 0
        while self.keepgoing:
            if self.acquisition_started: 
                frame = self.camera.get_frame()
                if frame.image is not None: 
                    self.frame = frame.image 
                    self.signal.image_ready.emit(True)

            if self.record_started:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    self.frame = frame.image
                    # fd.write(f"{frame.index}, {frame.timestamp}\n")
                    self.writer.write_frame(frame.image)
                    self.signal.image_ready.emit(True)
            
            # if self.record_started:
            #     frame = self.camera.get_frame()
            #     if frame.image is not None:
            #         # self.frame = frame.image
            #         cv2.imwrite(self.output_dir + str(self.i) + '.tif', frame.image)
            #         # self.signal.image_ready.emit(True)
            #         self.i += 1
            #         print(self.i)
        
        # fd.close()



class CameraControl(QWidget):

    # image_ready = pyqtSignal(np.ndarray)
    fps_ready = pyqtSignal(int)
    fourcc_ready = pyqtSignal(str)
    filename_ready = pyqtSignal(str)
    dir_ready = pyqtSignal(str)
    # video_number_ready = pyqtSignal(str)
    recording_finished = pyqtSignal(int)
    stim_dir_ready = pyqtSignal(str)
    video_idx_ready = pyqtSignal(str)
    

    def __init__(self, 
                 camera: Camera, 
                 protocol: str, 
                 stim_host: str, 
                 stim_port: int,
                #  cam_port: int, 
                 *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera

        self.sender = FrameSenderCombined(camera)
        self.message_receiver = MessageReceiver(cam_controls=self, 
                                                protocol=protocol, 
                                                stim_host=stim_host, 
                                                stim_port=stim_port)
        self.metadata = CameraMetadata(cam_controls=self)
        # this is breaking encapsulation a bit 
        # self.sender.signal.image_ready.connect(self.image_ready)
        
        self.sender.signal.image_ready.connect(self.preview)

        self.fps_ready.connect(self.sender.set_fps)
        self.fourcc_ready.connect(self.sender.set_fourcc)
        self.filename_ready.connect(self.sender.set_filename)
        self.dir_ready.connect(self.sender.set_directory)
        self.stim_dir_ready.connect(self.sender.set_stim_folder)
        self.video_idx_ready.connect(self.sender.set_video_index)

        self.thread_pool = QThreadPool()
        self.thread_pool.start(self.sender)

        self.message_threadpool = QThreadPool()
        self.message_threadpool.start(self.message_receiver)

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
        
        # self.make_dir_button = QPushButton(self)
        # self.make_dir_button.setText('Create folder')
        # self.make_dir_button.clicked.connect(self.make_dir)
                                             
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

        # self.video_number_input = LabeledSpinBox(self)
        # self.video_number_input.setText('Video number')
        # self.video_number_input.setRange(0, 999)
        # self.video_number_input.setSingleStep(1)
        # self.video_number_input.valueChanged.connect(self.set_video_number)
        
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
        # layout_files.addWidget(self.make_dir_button)

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
            # self.camera.start_acquisition()
            self.sender.start_acquisition()
            self.acquisition_status.setText('Acquiring')
            self.record_button.setEnabled(False)
            self.stop_record_button.setEnabled(False)
            self.acquisition_started = True
            
    def stop_acquisition(self):
        if self.acquisition_started:
            self.sender.stop_acquisition()
            # self.camera.stop_acquisition()
            self.acquisition_status.setText('Not acquiring')
            self.record_button.setEnabled(True)
            self.stop_record_button.setEnabled(True)
            self.acquisition_started = False
    
    def start_recording(self):
        # if not (self.file_name_input.text().strip() or self.fourcc_input.text().strip() or self.encoding_fps_input.text().strip()):
        #     print('parameters not filled in') 
        if not self.acquisition_started:
            self.sender.start_recording()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.record_started = True
            # self.start_socket.send_string("START_STIMULATION")  # Send start signal to o1-609

    def stop_recording(self):
        if self.record_started:
            self.sender.stop_recording()
            self.record_button.setEnabled(True)
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.record_started = False
            self.recording_finished.emit(True)

    # def finish_recording(self, signal):
    #     if self.record_started & signal:
    #         self.sender.stop_recording()
    #         self.record_button.setEnabled(True)
    #         self.start_button.setEnabled(True)
    #         self.stop_button.setEnabled(True)
    #         self.record_started = False
    #         self.recording_finished.emit(True)

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
        # self.sender.set_params(filename = self.file_name_input.text())
        # self.filename = self.file_name_input.text()

    # def set_video_number(self):
    #     video_number = str(self.video_number_input.value())
    #     self.video_number_ready.emit(video_number)

    def set_fourcc(self):
        fourcc = self.fourcc_input.text()
        self.fourcc_input.clearFocus()
        self.fourcc_ready.emit(fourcc)
        # self.fourcc = self.fourcc_input.text()

    def set_fps(self):
        fps = int(self.encoding_fps_input.text())
        self.encoding_fps_input.clearFocus()
        self.fps_ready.emit(fps)
        # self.fps = int(self.encoding_fps_input.text())

    def preview(self, image_ready: int):
        if image_ready:
            self.camera_preview.setPixmap(NDarray_to_QPixmap(self.sender.frame))

    def select_directory(self):
        self.directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if self.directory and self.fish_id:
            self.directory_label.setText(f"Selected Directory: {self.directory}")
            self.fish_dir = Path(self.directory, self.fish_id) 
            if not self.fish_dir.exists():
                self.fish_dir.mkdir(parents=True)
                print(f'Fish folder {str(self.fish_dir)} created')
                self.dir_ready.emit(str(self.fish_dir))
            else: 
                print(f'Fish folder already exists')
                self.dir_ready.emit(str(self.fish_dir))
        else: 
            print('please enter fish number')


    def set_fish_number(self):
        fish_number = self.fish_number_input.value()
        self.fish_number = f'{fish_number:03}' #adds leading zeros
        date_today = datetime.today()
        self.date = date_today.strftime('%Y%m%d')
        # self.time_h_m = date_today.strftime('%H%M')
        self.fish_id = self.date + self.fish_number

    def set_stim_number(self):
        stim_number = self.stimulation_number_input.value()
        self.stim_number = stim_number
        self.stim_folder = 'stim'+str(stim_number)
        stim_folder_path = Path(self.fish_dir) / self.stim_folder
        if not stim_folder_path.exists():
            stim_folder_path.mkdir(parents=True)
            print(f'stim folder {self.stim_folder} created')
            self.stim_folder_path = str(stim_folder_path)
            self.stim_dir_ready.emit(self.stim_folder_path)
        else: 
            print("stim folder already exists")
            self.stim_folder_path = str(stim_folder_path)
            self.stim_dir_ready.emit(self.stim_folder_path)
        
    def set_video_index(self, idx):
        self.video_index = idx
        self.video_idx_ready.emit(idx)


class CameraMetadata:
    def __init__(
            self, 
            cam_controls: CameraControl,
            *args, 
            **kwargs
            ):
        
        super().__init__(*args, **kwargs)

        self.cam_controls = cam_controls
        # self.video_names = []

    def get_metadata(self):
        self.get_video_names()
        self.get_id()
        self.get_video_settings()
        self.get_directory()
        self.export_metadata()

    # gets today's date and time and formats it into YYYYmmDDHHMM
    # creates unique id with fish number 
    
    def get_video_names(self):
        video_index = self.cam_controls.sender.video_index
        filename = self.cam_controls.sender.filename 
        self.video_name = filename + video_index
        self.video_index = video_index
        # self.video_names.append(filename + video_index)

    def get_id(self):
        self.id = self.cam_controls.fish_id
    
    # def set_fishline(self):
    #     self.fishline = self.fishline_input.text()

    # def set_condition(self):
    #     self.condition = self.condition_input.text()
    
    def get_video_settings(self):
        self.fps = self.cam_controls.camera.get_framerate()
        self.exposure = self.cam_controls.camera.get_exposure()
        self.gain = self.cam_controls.camera.get_gain()
        self.width = self.cam_controls.camera.get_width()
        self.height = self.cam_controls.camera.get_height()
        self.fourcc = self.cam_controls.sender.fourcc
        self.filename = self.cam_controls.sender.filename
        self.video_start_time = self.cam_controls.sender.video_start_time 

    def get_directory(self):
        self.directory = self.cam_controls.stim_folder_path
        # self.directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        # if self.directory: 
        #     self.directory_label.setText(f'Selected directory: {self.directory}')

    def export_metadata(self):
        metadata_dict = {
            'fish_id': self.id, 
            'fps': self.fps, 
            'exposure': self.exposure, 
            'gain': self.gain, 
            'frame_width': self.width, 
            'frame_height': self.height, 
            'fourcc': self.fourcc, 
            'video_filename': self.filename,
            'trial_index': self.video_index,
            'video_start': self.video_start_time, 
        }

        metadata_path = Path(self.directory, self.video_name+'.json')

        with open(metadata_path, 'w') as file:
            json.dump(metadata_dict, file)


class MessageReceiver(QRunnable): 
    
    def __init__(self, 
                 protocol: str, 
                 stim_host: str, 
                 stim_port: int, 
                #  cam_port: int,
                 cam_controls: CameraControl, 
                #  video_metadata: CameraMetadata,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.cam_controls = cam_controls
        self.video_metadata = CameraMetadata(cam_controls=self.cam_controls)
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(protocol + stim_host + ":" + str(stim_port))
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # self.socket.setsockopt_string(zmq.SUBSCRIBE, "START_RECORDING")
        # self.socket.setsockopt_string(zmq.SUBSCRIBE, "STOP_RECORDING")

    def run(self):
        while True: 
            message = self.socket.recv_string()  
            if message == "START_RECORDING":
                self.cam_controls.sender.start_recording()
                print('Start message received')
            elif message == "STOP_RECORDING": 
                self.cam_controls.sender.stop_recording()
                print('Stop message received')
                self.video_metadata.get_metadata()
            else: 
                self.cam_controls.set_video_index(message)
                print('index received: ', message)
        
                
# class RunReceiver(QObject):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.threadpool = QThreadPool()
#         self.receiver = MessageReceiver()
#         self.threadpool.start(self.receiver)
 



class CameraControl_MP(QWidget):

    image_ready = pyqtSignal(np.ndarray)

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera

        self.sender = FrameSender(camera)
        # this is breaking encapsulation a bit 
        self.sender.signal.image_ready.connect(self.image_ready)

        self.thread_pool = QThreadPool()
        self.thread_pool.start(self.sender)

        self.acquisition_started = False
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

        # controls 
        for c in self.controls:
            self.create_spinbox(c)

        # Region of interest ------------------------------------

        self.ROI_groupbox = QGroupBox('ROI:')

    def layout_components(self):

        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)

        layout_frame = QVBoxLayout(self.ROI_groupbox)
        layout_frame.addStretch()
        layout_frame.addWidget(self.offsetX_spinbox)
        layout_frame.addWidget(self.offsetY_spinbox)
        layout_frame.addWidget(self.height_spinbox)
        layout_frame.addWidget(self.width_spinbox)
        layout_frame.addStretch()

        layout_controls = QVBoxLayout(self)
        layout_controls.addStretch()
        layout_controls.addWidget(self.exposure_spinbox)
        layout_controls.addWidget(self.gain_spinbox)
        layout_controls.addWidget(self.framerate_spinbox)
        layout_controls.addWidget(self.ROI_groupbox)
        layout_controls.addLayout(layout_start_stop)
        layout_controls.addStretch()

    # Callbacks --------------------------------------------------------- 

    def closeEvent(self, event):
        self.sender.terminate()
        self.stop_acquisition()

    def start_acquisition(self):
        if not self.acquisition_started:
            self.camera.start_acquisition()
            self.sender.start_acquisition()
            self.acquisition_started = True
            
    def stop_acquisition(self):
        if self.acquisition_started:
            self.sender.stop_acquisition()
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


class CameraPreview(QWidget):

    def __init__(self, camera_control: CameraControl, *args, **kwargs) -> None:
        
        super().__init__(*args, **kwargs)

        self.image_label = QLabel()

        self.camera_control = camera_control
        self.camera_control.image_ready.connect(self.update_image)

        layout = QHBoxLayout(self)
        layout.addWidget(self.image_label)
        layout.addWidget(self.camera_control)

    def update_image(self, image: np.ndarray):
        self.image_label.setPixmap(NDarray_to_QPixmap(image))
        


