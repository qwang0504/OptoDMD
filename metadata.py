# import numpy as np
# import pandas as pd
from stimulation import StimManager
# from LED import LEDDriver
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit, QCalendarWidget, QFileDialog
from PyQt5.QtCore import QDate
from qt_widgets import LabeledSpinBox, LabeledDoubleSpinBox
from camera_widgets_new import CameraControl
import json
from pathlib import Path
from datetime import datetime
import zmq

class Metadata(QWidget):
    def __init__(
            self, 
            stim_manager: StimManager, 
            cam_controls: CameraControl,
            # led_driver: LEDDriver,
            *args, 
            **kwargs
            ):
        
        super().__init__(*args, **kwargs)

        self.stim_manager = stim_manager 
        self.cam_controls = cam_controls
        # self.led_driver = led_driver

        self.declare_components()
        self.layout_components()

    def initialise_widget(self, signal: int):
        if signal: 
            self.show()
            self.get_id()
            self.get_video_settings()
            self.get_interval()
            self.get_directory()
            self.get_mask_order()
            self.get_interval()
            self.get_pulse_timing()
            self.get_led_params()

    def declare_components(self):

        self.fish_number_input = QLineEdit(self)
        self.fish_number_input.setText('Fish number (fn)')
        self.fish_number_input.returnPressed.connect(self.set_fish_number)
        self.fish_number_input_instructions = QLabel(self)
        self.fish_number_input_instructions.setText('001, 002 etc.')
        
        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.calculate_age)

        self.calendar_label = QLabel(self)
        self.calendar_label.setText('Date of birth: ')

        self.dpf_label = QLabel(self)
        self.dpf_label.setText('Days post-fertilisation: ')

        self.fishline_input = QLineEdit(self)
        self.fishline_input.setText('Fish line')
        self.fishline_input.returnPressed.connect(self.set_fishline)

        self.condition_input = QLineEdit(self)
        self.condition_input.setText('Condition')
        self.condition_input.returnPressed.connect(self.set_condition)

        self.led_power_input = LabeledDoubleSpinBox(self)
        self.led_power_input.setText('LED dial')
        self.led_power_input.setRange(1, 6)
        self.led_power_input.setValue(6)
        self.led_power_input.setSingleStep(0.5)
        self.led_power_input.valueChanged.connect(self.get_led_params)

        # self.directory_button = QPushButton(self)
        # self.directory_button.setText('Select directory')
        # self.directory_button.clicked.connect(self.set_directory)
        # self.directory_label = QLabel(self)
        # self.directory_label.setText('Selected directory: ')

        self.export_metadata_button = QPushButton(self)
        self.export_metadata_button.setText('Export metadata')
        self.export_metadata_button.clicked.connect(self.export_metadata)

    def layout_components(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(self.fish_number_input_instructions)
        layout.addWidget(self.fish_number_input)

        layout.addWidget(self.calendar_label)
        layout.addWidget(self.calendar)
        layout.addWidget(self.dpf_label)

        layout.addWidget(self.fishline_input)
        
        layout.addWidget(self.condition_input)
        layout.addWidget(self.led_power_input)
        layout.addWidget(self.export_metadata_button)


    # gets today's date and time and formats it into YYYYmmDDHHMM
    # creates unique id with fish number 
    def get_id(self):
        self.id = self.cam_controls.fish_id

    def set_fish_number(self):
        self.fish_number = self.fish_number_input.text()
    
    def set_fishline(self):
        self.fishline = self.fishline_input.text()

    def set_condition(self):
        self.condition = self.condition_input.text()
    
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
        print(self.age)

    def get_video_settings(self):
        self.fps = self.cam_controls.camera.get_framerate()
        self.exposure = self.cam_controls.camera.get_exposure()
        self.gain = self.cam_controls.camera.get_gain()
        self.width = self.cam_controls.camera.get_width()
        self.height = self.cam_controls.camera.get_height()
        self.fourcc = self.cam_controls.sender.fourcc
        self.video_filename = self.cam_controls.sender.filename
        self.video_start_time = self.cam_controls.sender.video_start_time 

    def get_interval(self):
        self.interval = self.stim_manager.interval_spinbox.value()

    def get_mask_order(self):
        if self.stim_manager.shuffled_mask_keys:
            self.mask_order = self.stim_manager.shuffled_mask_names

    def get_pulse_timing(self):
        self.pulse_start = self.stim_manager.start_stim.pulse_start
        self.pulse_end = self.stim_manager.start_stim.pulse_end
        self.pulse_duration = self.stim_manager.start_stim.pulse_duration
        print(self.pulse_start)
        print(self.pulse_end)
        print(self.pulse_duration)
    
    def get_led_params(self):
        self.led_power = self.led_power_input.value()
        self.pwm_frequency = self.stim_manager.led_driver.pwm_frequency
        self.duty_cycle = self.stim_manager.led_driver.intensity
        
    def get_directory(self):
        self.directory = self.cam_controls.fish_dir
        # self.directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        # if self.directory: 
        #     self.directory_label.setText(f'Selected directory: {self.directory}')

    def export_metadata(self):
        metadata_dict = {
            'fish_id': self.id, 
            'line': self.fishline,
            'condition': self.condition, 
            'dob': self.dob, 
            'age': self.age, 
            'fps': self.fps, 
            'exposure': self.exposure, 
            'gain': self.gain, 
            'frame_width': self.width, 
            'frame_height': self.height, 
            'fourcc': self.fourcc, 
            'video_filename': self.video_filename,
            'video_start': self.video_start_time, 
            'interval': self.interval, 
            'mask_order': self.mask_order, 
            'led_power': self.led_power, 
            'pwm_frequency': self.pwm_frequency, 
            'pwm_duty_cycle': self.duty_cycle,
            'pulse_start': list(self.pulse_start), 
            'pulse_end': list(self.pulse_end), 
            'pulse_duration': list(self.pulse_duration)
        }

        metadata_path = Path(self.directory, self.video_filename+'.json')

        with open(metadata_path, 'w') as file:
            json.dump(metadata_dict, file)

    #genotype, age, condition
    #mask exposed, pulse start, pulse end, duration, interval 
    #fps, exposure, gain, encoding, frame size, fourcc, filename, video start time
    #LED SETTINGS!!!!!!! duty cycle, intensity, frequency 

    #write json with id


class CameraMetadata(QWidget):
    def __init__(
            self, 
            cam_controls: CameraControl,
            *args, 
            **kwargs
            ):
        
        super().__init__(*args, **kwargs)

        self.cam_controls = cam_controls

        self.declare_components()
        self.layout_components()


    def initialise_widget(self, signal: int):
        if signal: 
            self.show()
            self.get_id()
            self.get_video_settings()
            self.get_directory()

    def declare_components(self):
        
        self.calendar_label = QLabel(self)
        self.calendar_label.setText('Date of birth: ')
        
        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.calculate_age)

        self.dpf_label = QLabel(self)
        self.dpf_label.setText('Days post-fertilisation: ')

        self.fishline_label = QLabel(self)
        self.fishline_label.setText('Fish line: ')

        self.fishline_input = QLineEdit(self)
        self.fishline_input.returnPressed.connect(self.set_fishline)

        self.condition_label = QLabel(self)
        self.condition_label.setText('Fish condition (e.g. control, blind)')

        self.condition_input = QLineEdit(self)
        self.condition_input.returnPressed.connect(self.set_condition)

        self.export_metadata_button = QPushButton(self)
        self.export_metadata_button.setText('Export metadata')
        self.export_metadata_button.clicked.connect(self.export_metadata)

    def layout_components(self):
        layout = QVBoxLayout(self)

        layout.addWidget(self.calendar_label)
        layout.addWidget(self.calendar)
        layout.addWidget(self.dpf_label)

        layout.addWidget(self.fishline_label)
        layout.addWidget(self.fishline_input)

        layout.addWidget(self.condition_label)
        layout.addWidget(self.condition_input)
        
        layout.addWidget(self.export_metadata_button)

    # gets today's date and time and formats it into YYYYmmDDHHMM
    # creates unique id with fish number 
    def get_id(self):
        self.id = self.cam_controls.fish_id
    
    def set_fishline(self):
        self.fishline = self.fishline_input.text()

    def set_condition(self):
        self.condition = self.condition_input.text()
    
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
        print(self.age)

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
        self.directory = self.cam_controls.fish_dir
        # self.directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        # if self.directory: 
        #     self.directory_label.setText(f'Selected directory: {self.directory}')

    def export_metadata(self):
        metadata_dict = {
            'fish_id': self.id, 
            'line': self.fishline,
            'condition': self.condition, 
            'dob': self.dob, 
            'age': self.age, 
            'fps': self.fps, 
            'exposure': self.exposure, 
            'gain': self.gain, 
            'frame_width': self.width, 
            'frame_height': self.height, 
            'fourcc': self.fourcc, 
            'video_filename': self.filename,
            'video_start': self.video_start_time, 
        }

        metadata_path = Path(self.directory, self.filename+'_camera.json')

        with open(metadata_path, 'w') as file:
            json.dump(metadata_dict, file)

import os 
import json

test_dict = {
    1: 1, 
    2: '2', 
    3: [1,2,3,4]
}

dir = Path(os.getcwd(), 'test_dict.json')
with open(dir, 'w') as file: 
    json.dump(test_dict, file)
