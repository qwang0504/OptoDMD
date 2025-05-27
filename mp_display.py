import multiprocessing
from camera_tools import XimeaCamera, Camera
from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QFileDialog
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, QMutex, QWaitCondition
from qt_widgets import NDarray_to_QPixmap, LabeledDoubleSpinBox, LabeledSliderDoubleSpinBox, LabeledSpinBox, LabeledEditLine
import numpy as np
from ipc_tools import ModifiableRingBuffer
from arrayqueues import ArrayQueue
from multiprocessing import Process, Pipe, Queue, connection, Event
import threading
from threading import Thread
from functools import partial
from typing import Callable
import time
from queue import Empty, Full
import ctypes
import copy 
from datetime import datetime
from pathlib import Path

# TODO: check if it's better to reuse QThread with event.wait()
# TODO: add high-res timers
# TODO: link terminate to StimManager
# TODO: fix layout order
# TODO: fix params state sent to CameraProcess 

class DisplayWorker(QObject):
    frame_ready = pyqtSignal()

    def __init__(self, 
                 display_buffer: ArrayQueue,
                #  start_event: threading.Event,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.display_buffer = display_buffer
        self.active = True
        # self.start_event = start_event

    def terminate(self):
        self.active = False

    def run(self):
        print('DisplayWorker running')
        # print(f'QThread ID: {int(QThread.currentThreadId())}')
        previous_qsize = -1
        while self.active:
            current_qsize = self.display_buffer.qsize()

            self.frame = self.display_buffer.get() #blocking
            if self.frame['image'].sum() > 0:
                self.frame_ready.emit()
            else: 
                print('DisplayWorker received sentinel')
                self.terminate()
            
            if current_qsize != previous_qsize:
                print(f'Display buffer queue size: {current_qsize}')
                previous_qsize = current_qsize
        
        print('DisplayWorker finished, exiting')


class CameraWidget(QWidget):

    record_started = pyqtSignal(int)
    record_stopped = pyqtSignal(int)
    terminate_pressed = pyqtSignal()

    def __init__(self, 
                 front_pipe_gui: connection.Connection,
                 display_buffer: ArrayQueue,
                 save_buffer: ArrayQueue,
                 sentinel_array: np.ndarray,
                 *args, 
                 **kwargs):
        
        super().__init__(*args, **kwargs)

        self.front_pipe_gui = front_pipe_gui

        self.display_buffer = display_buffer
        self.save_buffer = save_buffer
        self.sentinel_array = sentinel_array

        self.worker = None
        self.qthread = None

        self.params = {}

        self.controls = [
            'framerate', 
            'exposure', 
            'gain', 
            'height', 
            'width'
        ]

        self.output_dir = None
        self.fish_number = None

        self.declare_components()
        self.layout_components()

    def create_spinbox(self, attr: str, cam_params: dict):
        '''
        Creates spinbox with correct label, value, range and increment
        as specified by the camera object. Connects to relevant
        callback.
        WARNING This is compact but a bit terse and introduces dependencies
        in the code. 
        '''
        
        setattr(self, attr + '_spinbox', LabeledSliderDoubleSpinBox(self))
    
        spinbox = getattr(self, attr + '_spinbox')
        spinbox.setText(attr)
        
        value = cam_params[attr]['value']
        range = cam_params[attr]['range']
        increment = cam_params[attr]['increment']

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

    def update_spinbox_values(self, updated_cam_params):
        for attr in ['framerate', 'exposure', 'gain']:
            spinbox = getattr(self, attr + '_spinbox')
            value = updated_cam_params[attr]['value']
            range = updated_cam_params[attr]['range']
            increment = updated_cam_params[attr]['increment']

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
        self.front_pipe_gui.send('init_params')
        self.init_params = self.front_pipe_gui.recv()
        self.params = copy.deepcopy(self.init_params)

        for attr in ['framerate', 'exposure', 'gain']:
            self.create_spinbox(attr=attr, cam_params=self.init_params)

        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText('file_name')
        self.file_name_input.returnPressed.connect(self.set_filename)

        self.start_button = QPushButton(self)
        self.start_button.setText('Start acquisition')
        self.start_button.clicked.connect(self.start_acquisition)

        self.stop_button = QPushButton(self)
        self.stop_button.setText('Stop acquisition')
        self.stop_button.clicked.connect(self.stop_acquisition)

        self.record_button = QPushButton(self)
        self.record_button.setText('Record to file')
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton(self)
        self.stop_record_button.setText('Stop recording')
        self.stop_record_button.clicked.connect(self.stop_recording)

        self.terminate_button = QPushButton(self)
        self.terminate_button.setText('Terminate all processes')
        self.terminate_button.clicked.connect(self.terminate)

        self.camera_preview = QLabel(self)
        self.camera_preview.setFixedSize(self.init_params['width']['value'], self.init_params['height']['value'])

        self.automate_checkbox = QCheckBox('Automated mode', self)
        self.automate_checkbox.setCheckState(False)
        self.automate_checkbox.stateChanged.connect(self.toggle_widgets)

        self.output_directory_button = QPushButton('Select output directory')
        self.output_directory_button.clicked.connect(self.select_directory) 
        
        self.directory_label = QLabel(self)
        self.directory_label.setText('Directory selected: ')

        self.fish_number_spinbox = LabeledSpinBox(self)
        self.fish_number_spinbox.setText('Fish number')
        self.fish_number_spinbox.setValue(0)
        self.fish_number_spinbox.setSingleStep(1)
        self.fish_number_spinbox.setRange(0,99)
        self.fish_number_spinbox.valueChanged.connect(self.set_fish_number)
        self.fish_number_spinbox.hide()

        self.generate_folder_button = QPushButton('Generate fish folder')
        self.generate_folder_button.clicked.connect(self.generate_fish_folder)
        self.generate_folder_button.hide()

        self.metadata_checkbox = QCheckBox('Trial metadata', self)
        self.metadata_checkbox.setCheckState(False)
        self.metadata_checkbox.stateChanged.connect(self.generate_metadata)

    def layout_components(self):
        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)

        layout_record = QHBoxLayout()
        layout_record.addWidget(self.record_button)
        layout_record.addWidget(self.stop_record_button)

        layout_spinboxes = QHBoxLayout()
        layout_spinboxes.addWidget(self.framerate_spinbox)
        layout_spinboxes.addWidget(self.exposure_spinbox)
        layout_spinboxes.addWidget(self.gain_spinbox)

        layout_directory = QVBoxLayout()
        layout_directory.addWidget(self.output_directory_button)
        layout_directory.addWidget(self.directory_label)
        layout_directory.addWidget(self.metadata_checkbox)
        layout_directory.addWidget(self.automate_checkbox)

        layout_fish_num = QHBoxLayout()
        layout_fish_num.addWidget(self.fish_number_spinbox)
        layout_fish_num.addWidget(self.generate_folder_button)

        layout = QVBoxLayout()
        layout.addWidget(self.camera_preview)
        layout.addLayout(layout_start_stop)
        layout.addLayout(layout_record)
        layout.addLayout(layout_spinboxes)
        layout.addWidget(self.terminate_button)
        layout.addWidget(self.file_name_input)
        layout.addLayout(layout_directory)
        layout.addLayout(layout_fish_num)
        
        self.setLayout(layout)


    ### Callbacks

    def start_acquisition(self):
        # if self.worker is None:
        self.worker = DisplayWorker(display_buffer=self.display_buffer)
        self.worker.frame_ready.connect(self.update_display)
        self.qthread = QThread()
        self.worker.moveToThread(self.qthread)
        self.qthread.started.connect(self.worker.run)
        self.qthread.start()
        self.front_pipe_gui.send('start_acquisition')
        self.acquisition_disabled()

        # else: 
        #     self.front_pipe_gui.send('start_acquisition')
        #     self.acquisition_disabled()

    def stop_acquisition(self):
        self.display_buffer.put(self.sentinel_array)
        self.front_pipe_gui.send('stop_acquisition')
        self.close_thread()
        self.acquisition_enabled()

    def start_recording(self):
        self.video_start_time = time.perf_counter_ns()
        self.params['video_start_time'] = {'value': self.video_start_time}
        # print(self.params)
        self.front_pipe_gui.send('start_recording')
        # self.update_params()
        self.front_pipe_gui.send(self.params)

        # if self.worker is None: 
        self.worker = DisplayWorker(display_buffer=self.display_buffer)
        self.worker.frame_ready.connect(self.update_display)
        self.qthread = QThread()
        self.worker.moveToThread(self.qthread)
        self.qthread.started.connect(self.worker.run)
        self.qthread.start()
        self.record_disabled()

        # else:
        #     self.front_pipe_gui.send('start_recording')
        #     self.front_pipe_gui.send(self.params)
        #     self.record_disabled()

    def stop_recording(self):
        self.front_pipe_gui.send('stop_recording')
        self.display_buffer.put(self.sentinel_array)
        self.save_buffer.put(self.sentinel_array)
        self.close_thread()
        self.record_enabled()

    def terminate(self):
        if self.worker:
            self.stop_acquisition()
            self.display_buffer.put(self.sentinel_array)
            self.save_buffer.put(self.sentinel_array)
            self.close_thread()
            self.front_pipe_gui.send('terminate')
            self.terminate_pressed.emit()
        else:
            print('DisplayWorker / QThread undefined, nothing to terminate')
            self.front_pipe_gui.send('terminate')
            self.terminate_pressed.emit()

    def update_display(self):
        try:
            self.camera_preview.setPixmap(NDarray_to_QPixmap(self.worker.frame['image']))
        except AttributeError:
            pass    
    
    # def update_params(self):
    #     # some function to finalise params before sending 
    #     print(self.params)

    def set_exposure(self):
        msg = {'command': 'set_exposure', 'value': self.exposure_spinbox.value()}
        self.front_pipe_gui.send(msg)
        updated_params = self.front_pipe_gui.recv()
        self.params.update(updated_params)
        self.update_spinbox_values(self.params)

    def set_gain(self):
        msg = {'command': 'set_gain', 'value': self.gain_spinbox.value()}
        self.front_pipe_gui.send(msg)
        updated_params = self.front_pipe_gui.recv()
        self.params.update(updated_params)
        self.update_spinbox_values(self.params)

    def set_framerate(self):
        msg = {'command': 'set_framerate', 'value': self.framerate_spinbox.value()}
        self.front_pipe_gui.send(msg)
        updated_params = self.front_pipe_gui.recv()
        self.params.update(updated_params)
        self.update_spinbox_values(self.params)

    def set_filename(self):
        if self.file_name_input.text() == "":
            self.params['filename'] = {'value': 'test'}
        else:
            self.params['filename'] = {'value': self.file_name_input.text()}
            self.file_name_input.clearFocus()

    def acquisition_disabled(self):
        self.start_button.setEnabled(False)
        self.record_button.setEnabled(False)
        self.stop_record_button.setEnabled(False)

    def acquisition_enabled(self):
        self.start_button.setEnabled(True)
        self.record_button.setEnabled(True)
        self.stop_record_button.setEnabled(True)
        
    def record_disabled(self):
        self.record_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.exposure_spinbox.setEnabled(False)
        self.gain_spinbox.setEnabled(False)
        self.framerate_spinbox.setEnabled(False)
        self.file_name_input.setEnabled(False)
        
    def record_enabled(self):
        self.record_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.exposure_spinbox.setEnabled(True)
        self.gain_spinbox.setEnabled(True)
        self.framerate_spinbox.setEnabled(True)
        self.file_name_input.setEnabled(True)

    def toggle_widgets(self):
        if self.automate_checkbox.isChecked():
            self.fish_number_spinbox.show()
            self.generate_folder_button.show()
            
        else:
            self.fish_number_spinbox.hide()
            self.generate_folder_button.hide()

    def select_directory(self):
        self.output_dir = QFileDialog.getExistingDirectory(self, 'Select output directory')
        self.directory_label.setText(f'Selected directory: {str(self.output_dir)}')
        self.params['output_dir'] = {'value': str(self.output_dir)}

    def set_fish_number(self):
        self.fish_number = self.fish_number_spinbox.value()
    
    def generate_fish_folder(self):
        if self.output_dir and self.fish_number:
            date = datetime.today().strftime('%Y%m%d')
            self.fish_id = date + f'{self.fish_number:03}'
            self.fish_folder = Path(self.output_dir, self.fish_id)
            
            if not self.fish_folder.exists():
                self.fish_folder.mkdir(parents=True)
                print(f'Fish folder {str(self.fish_folder)} created')
                self.params['fish_id'] = {'value': str(self.fish_id)}
            else:
                print(f'Fish folder {self.fish_id} already exists')
                self.params['fish_id'] = {'value': str(self.fish_id)}

        else:
            print('No output directory or fish number')
    
    def set_stim_number(self, stim_number):
        self.stim_number = stim_number
        self.params['stim_number'] = {'value': self.stim_number}

    def set_trial_index(self, trial_index):
        self.trial_index = trial_index
        self.params['trial_index'] = {'value': self.trial_index}

    def generate_metadata(self):
        if self.metadata_checkbox.isChecked:
            self.params['metadata'] = {'value': True}
        else: 
            self.params['metadata'] = {'value': False}

    def close_thread(self):
        self.qthread.quit()
        self.qthread.wait() 
        self.qthread = None
        self.worker = None
        print('qthread closed, defaults to None')

    def closeEvent(self, event):
        self.terminate()
        event.accept()  # Accept the event to close the window
