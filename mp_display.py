import numpy as np
from camera_tools import XimeaCamera, Camera
from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QFileDialog, QCalendarWidget
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, QDate
from qt_widgets import NDarray_to_QPixmap, LabeledDoubleSpinBox, LabeledSliderDoubleSpinBox, LabeledSpinBox, LabeledEditLine
from ipc_tools import ModifiableRingBuffer
from arrayqueues import ArrayQueue
from multiprocessing import Process, Pipe, Queue, connection, Event
from threading import Thread
from functools import partial
from typing import Callable
import time
from queue import Empty, Full
import copy 
from datetime import datetime
from pathlib import Path
import json

# TODO: check if it's better to reuse QThread with event.wait()
# TODO: add high-res timers
# TODO: check display buffer size, stop acquisition queue.Full problem

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
    fish_folder_generated = pyqtSignal(str, str)

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

        self.acquisition_started = False

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

        self.camera_preview = QLabel(self)
        self.camera_preview.setFixedSize(self.init_params['width']['value'], self.init_params['height']['value'])

        self.automate_checkbox = QCheckBox('Automated mode', self)
        self.automate_checkbox.setCheckState(False)
        self.automate_checkbox.setTristate(False)
        self.automate_checkbox.stateChanged.connect(self.toggle_widgets)

        self.fish_metadata_checkbox = QCheckBox('Fish metadata', self)
        self.fish_metadata_checkbox.setCheckState(False)
        self.fish_metadata_checkbox.setTristate(False)
        self.fish_metadata_checkbox.stateChanged.connect(self.toggle_fish_metadata)

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

        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.calculate_age)
        self.calendar.hide()

        self.calendar_label = QLabel(self)
        self.calendar_label.setText('Date of birth: ')
        self.calendar_label.hide()

        self.dpf_label = QLabel(self)
        self.dpf_label.setText('Days post-fertilisation: ')
        self.dpf_label.hide()

        self.fishline_input = QLineEdit(self)
        self.fishline_input.setPlaceholderText('Fish line')
        self.fishline_input.returnPressed.connect(self.set_fishline)
        self.fishline_input.hide()

        self.condition_input = QLineEdit(self)
        self.condition_input.setPlaceholderText('Condition')
        self.condition_input.returnPressed.connect(self.set_condition)
        self.condition_input.hide()

        self.generate_fish_metadata_button = QPushButton(self)
        self.generate_fish_metadata_button.setText('Create fish metadata')
        self.generate_fish_metadata_button.clicked.connect(self.generate_fish_metadata)


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

        layout_file = QHBoxLayout()
        layout_file.addWidget(self.file_name_input)
        layout_file.addWidget(self.output_directory_button)

        layout_checkboxes = QVBoxLayout()
        layout_checkboxes.addWidget(self.automate_checkbox)
        layout_checkboxes.addWidget(self.fish_metadata_checkbox)

        layout_fish_num = QHBoxLayout()
        layout_fish_num.addWidget(self.fish_number_spinbox)
        layout_fish_num.addWidget(self.generate_folder_button)

        layout_fish_metadata = QVBoxLayout()
        layout_fish_metadata.addWidget(self.calendar_label)
        layout_fish_metadata.addWidget(self.calendar)
        layout_fish_metadata.addWidget(self.dpf_label)
        layout_fish_metadata.addWidget(self.fishline_input)
        layout_fish_metadata.addWidget(self.condition_input)
        layout_fish_metadata.addWidget(self.generate_fish_metadata_button)

        layout = QVBoxLayout()
        layout.addWidget(self.camera_preview)
        layout.addLayout(layout_start_stop)
        layout.addLayout(layout_record)
        layout.addLayout(layout_spinboxes)
        layout.addLayout(layout_file)
        layout.addWidget(self.directory_label)
        layout.addLayout(layout_checkboxes)
        layout.addLayout(layout_fish_num)
        layout.addLayout(layout_fish_metadata)
        
        self.setLayout(layout)


    ### Callbacks

    def setup_worker(self):
        self.worker = DisplayWorker(display_buffer=self.display_buffer)
        self.worker.frame_ready.connect(self.update_display)
        self.qthread = QThread()
        self.worker.moveToThread(self.qthread)
        self.qthread.started.connect(self.worker.run)
        self.qthread.start()

    def start_acquisition(self):
        self.setup_worker()
        self.front_pipe_gui.send('start_acquisition')
        self.acquisition_disabled()
        self.acquisition_started = True

    def stop_acquisition(self):
        if self.acquisition_started:
            self.display_buffer.put(self.sentinel_array)
            self.front_pipe_gui.send('stop_acquisition')
            self.close_thread()
            self.acquisition_enabled()
            self.acquisition_started = False
        else: 
            print('Acquisition not started')

    def start_recording(self):
        self.video_start_time = time.perf_counter_ns()
        self.params['video_start_time'] = {'value': self.video_start_time}
        self.front_pipe_gui.send('start_recording')
        self.front_pipe_gui.send(self.params)
        self.setup_worker()
        self.record_disabled()

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
        for widget in self.findChildren(QWidget):
            if widget not in (self.stop_record_button, self.camera_preview):
                widget.setEnabled(False)

    def record_enabled(self):
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)

    def toggle_widgets(self, state): #0 or 2
        self.fish_number_spinbox.setVisible(state)
        self.generate_folder_button.setVisible(state)
        self.adjustSize()
        self.params['metadata'] = {'value': state}

    def toggle_fish_metadata(self, state):
        self.calendar.setVisible(state)
        self.calendar_label.setVisible(state)
        self.dpf_label.setVisible(state)
        self.fishline_input.setVisible(state)
        self.condition_input.setVisible(state)
        self.adjustSize()

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
            self.fish_folder_generated.emit(str(self.fish_folder), str(self.fish_id))

        else:
            print('No output directory or fish number')
    
    def set_stim_number(self, stim_number):
        self.stim_number = stim_number
        self.params['stim_number'] = {'value': self.stim_number}

    def set_trial_index(self, trial_index):
        self.trial_index = trial_index
        self.params['trial_index'] = {'value': self.trial_index}
    
    def calculate_age(self):
        # Get the selected date
        dob = self.calendar.selectedDate()
        # Format the date as a string
        dob_str = dob.toString("yyyy-MM-dd")
        self.dob = dob.toString("yyyyMMdd")
        # Update the label with the selected date
        self.calendar_label.setText(f"Date of birth: {dob_str}")
        self.today = datetime.today()
        today_qdate = QDate(self.today.year, self.today.month, self.today.day)
        # self.age = today_qdate.daysTo(dob)
        self.age = dob.daysTo(today_qdate) - 1
        self.dpf_label.setText(f'Days post-fertilisation: {self.age}')
        # print(self.age)

    def set_fishline(self):
        self.fishline = self.fishline_input.text()
        self.fishline_input.clearFocus()

    def set_condition(self):
        self.condition = self.condition_input.text()
        self.condition_input.clearFocus()

    def generate_fish_metadata(self):
        if self.fish_folder:
            self.calculate_age()
            fish_metadata = {
            'fish_id': str(self.fish_id),
            'line': self.fishline,
            'condition': self.condition, 
            'dob': self.dob, 
            'age': self.age, 
            }

            metadata_path = Path(self.fish_folder / (str(self.fish_id) + '.json'))

            with open(metadata_path, 'w') as file:
                json.dump(fish_metadata, file)
        
        else:
            print('Fish folder not found!')

    def close_thread(self):
        self.qthread.quit()
        self.qthread.wait() 
        self.qthread = None
        self.worker = None
        print('qthread closed, defaults to None')

    def closeEvent(self, event):
        self.terminate()
        event.accept()  # Accept the event to close the window
