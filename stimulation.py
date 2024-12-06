from PyQt5.QtCore import pyqtSignal, Qt, QRunnable, QThreadPool, pyqtSlot, QObject
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QPushButton, QFrame, QLineEdit, QCheckBox, QListWidget
from qt_widgets import LabeledSpinBox, LabeledDoubleSpinBox, LabeledSliderSpinBox
from DrawMasks import MaskManager
from LED import LEDDriver, PulseSender
from daq import LabJackU3LV, LabJackU3LV_new, DigitalAnalogIO
import time
import numpy as np
import zmq

class StimManager(QWidget):

    mask_expose = pyqtSignal(int)
    clear_dmd = pyqtSignal()
    run_complete = pyqtSignal(int)
    stim_started = pyqtSignal(int)
    
    def __init__(
            self,
            mask_manager : MaskManager,
            led_driver: LEDDriver,
            protocol: str, 
            cam_host: str,
            stim_port: int,
            # cam_port: int,  
            *args, **kwargs
            ):
    
        super().__init__(*args, **kwargs)

        self.mask_manager = mask_manager

        # self.message_receiver = MessageReceiver(stim_manager=self, 
        #                                         protocol=protocol,
        #                                         cam_host=cam_host)

        self.led_driver = led_driver
        self.mask_manager.draw_complete.connect(self.update_draw_display)
        self.thread_pool = QThreadPool()

        # self.message_threadpool = QThreadPool()
        # self.message_threadpool.start(self.message_receiver)

        self.create_components()
        self.layout_components()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(protocol + '*:' + str(stim_port))

    # def receive_message(self):
    #     message = self.start_stim_socket.recv_string()
    #     if message == "START_STIMULATION":
    #         self.start()

    def update_draw_display(self, signal: int):
        print(signal)
        self.shuffled_mask_keys = None
        self.mask_widgets = self.mask_manager.mask_widgets
        self.mask_keys = list(self.mask_widgets.keys())
        self.mask_names = [self.mask_widgets[key].name for key in self.mask_keys] 
        mask_names_display = [str(key) + ': ' + self.mask_widgets[key].name for key in self.mask_keys] 
        # mask_keys_str = [str(key) for key in self.mask_keys]
        if signal: 
            self.masks_display.clear()
            self.masks_display.addItems(mask_names_display)
        else: 
            self.masks_display.clear()
    
    # only gets masks that are checked in the main window 
    def get_checked_masks(self):
        for key in self.mask_keys:
            mask_widget = self.mask_widgets[key]
            if mask_widget.show.checkState() == Qt.Checked:
                self.mask_widgets_checked[key] = mask_widget

    def create_components(self):
        self.rep_spinbox = LabeledSpinBox(self)
        self.rep_spinbox.setText('Number of repetitions')
        self.rep_spinbox.setValue(1)

        self.interval_spinbox = LabeledSpinBox(self)
        self.interval_spinbox.setText('Interval duration (s)')
        self.interval_spinbox.setValue(0)
        self.interval_spinbox.valueChanged.connect(self.set_interval)
        
        self.intensity_slider = LabeledSliderSpinBox(self)
        self.intensity_slider.setText('intensity (%)')
        self.intensity_slider.setRange(0, 100)
        self.intensity_slider.setValue(0)
        self.intensity_slider.valueChanged.connect(self.set_intensity)
        self.led_driver.set_intensity(0.5)

        self.freq_spinbox = LabeledSpinBox(self)
        self.freq_spinbox.setText('PWM frequency (Hz)')
        self.freq_spinbox.setRange(0, 100_000)
        self.freq_spinbox.setValue(1000)
        self.freq_spinbox.valueChanged.connect(self.set_frequency)

        self.duration_spinbox = LabeledSpinBox(self)
        self.duration_spinbox.setText('pulse duration (ms)')
        self.duration_spinbox.setRange(0, 100_000)
        self.duration_spinbox.setValue(1000)
        # self.duration_spinbox.valueChanged.connect(self.set_stim_duration)

        self.shuffle_button = QPushButton(self)
        self.shuffle_button.setText('Shuffle order')
        self.shuffle_button.clicked.connect(self.shuffle_order)

        self.start_stim_button = QPushButton(self)
        self.start_stim_button.setText('Start stimulation')
        self.start_stim_button.clicked.connect(self.start)

        self.stop_stim_button = QPushButton(self)
        self.stop_stim_button.setText('Stop stimulation')
        self.stop_stim_button.clicked.connect(self.stop)


        self.masks_display = QListWidget(self)

        self.fish_number_input = LabeledSpinBox(self)
        self.fish_number_input.setText('Fish number')
        self.fish_number_input.setRange(0, 999)
        self.fish_number_input.setSingleStep(1)
        self.fish_number_input.valueChanged.connect(self.set_fish_number)
        
        self.stim_number_input = LabeledSpinBox(self)
        self.stim_number_input.setText('Stimulation number')
        self.stim_number_input.setRange(0, 999)
        self.stim_number_input.setSingleStep(1)
        self.stim_number_input.valueChanged.connect(self.set_stim_number)

        self.recording_duration_input = LabeledSpinBox(self)
        self.recording_duration_input.setText('Duration of recording (s)')
        self.recording_duration_input.setRange(0, 999)
        self.recording_duration_input.setSingleStep(1)
        self.recording_duration_input.setValue(10)
        # self.recording_duration_input.valueChanged.connect(self.set_recording_duration)


    def layout_components(self):
        
        layout_overall = QHBoxLayout(self)

        layout_shuffle = QVBoxLayout()
        layout_shuffle.addWidget(self.shuffle_button)
        layout_shuffle.addWidget(self.masks_display)
        layout_shuffle.setSpacing(10)

        layout_overall.addLayout(layout_shuffle)
        
        layout_controls = QVBoxLayout()

        layout_controls.addWidget(self.fish_number_input)
        layout_controls.addWidget(self.stim_number_input)
        
        layout_controls.addWidget(self.intensity_slider)
        layout_controls.addWidget(self.freq_spinbox)
        layout_controls.addWidget(self.duration_spinbox)
        layout_controls.addWidget(self.recording_duration_input)

        layout_trial_controls = QHBoxLayout()
        layout_trial_controls.addWidget(self.rep_spinbox)
        layout_trial_controls.addWidget(self.interval_spinbox)

        layout_controls.addLayout(layout_trial_controls)
        layout_controls.addWidget(self.start_stim_button)
        layout_controls.addWidget(self.stop_stim_button)
        layout_controls.setSpacing(20)

        layout_overall.addLayout(layout_controls)
        

    # Callbacks
    def set_intensity(self, value: int):
        self.led_driver.set_intensity(value/100)

    def set_frequency(self, value: int):
        self.led_driver.set_frequency(value)

    def shuffle_order(self):
        if self.mask_widgets:
            # self.mask_keys = list(self.mask_widgets.keys())
            mask_keys_copy = list(self.mask_keys.copy())
            reps = self.rep_spinbox.value()
            if reps > 1:
                mask_keys_copy = [key for key in mask_keys_copy for _ in range(reps)]
                # np.random.shuffle(mask_keys_copy) #returns None!
                mask_keys_copy = self.shuffle_no_consecutive(mask_keys_copy)
            else: 
                np.random.shuffle(mask_keys_copy) 
            self.shuffled_mask_keys = mask_keys_copy
            print(self.shuffled_mask_keys)
            self.shuffled_mask_names = [self.mask_widgets[key].name 
                                        for key in self.shuffled_mask_keys]
            shuffled_mask_names_display = [str(key) + ': ' + self.mask_widgets[key].name 
                                           for key in self.shuffled_mask_keys] 
            
            # shuffed_mask_keys_str = [str(key) for key in self.shuffled_mask_keys]
            self.update_shuffle_display(shuffled_mask_names_display)
        else:
            print('No masks drawn!')
        # return self.shuffled_mask_list
    
    def shuffle_no_consecutive(self, mask_list):
        while True:
            np.random.shuffle(mask_list)
        # Check for consecutive duplicates
            if all(mask_list[i] != mask_list[i + 1] for i in range(len(mask_list) - 1)):
                return mask_list

    def set_number_of_elements(self):
        if self.shuffled_mask_keys:
            self.n_elements = len(self.shuffled_mask_keys)
        else: 
            self.n_elements = len(self.mask_keys)

    def update_shuffle_display(self, shuffled):
        if self.masks_display.count() > 0:
            self.masks_display.clear()
            self.masks_display.addItems(shuffled)

    def set_fish_number(self):
        fish_number = self.fish_number_input.value()
        self.fish_number = f'{fish_number:03}' #adds leading zeros

    def set_stim_number(self):
        stim_protocol_number = self.stim_number_input.value()
        self.stim_number = str(stim_protocol_number)

    # def set_recording_duration(self):
    #     self.recording_duration = self.recording_duration_input.value()
    
    # def set_stim_duration(self):
    #     self.stim_duration = self.duration_spinbox.value()

    def set_interval(self):
        self.interval = self.interval_spinbox.value()

    def start(self):
        self.set_number_of_elements()
        self.start_stim = StartStim(stim_manager=self, 
                               led_driver=self.led_driver) #insert parameters
        self.start_stim.started = True
        self.thread_pool.start(self.start_stim)

    def stop(self):
        self.start_stim.started = False


class FinishedSignal(QObject):
    run_finished = pyqtSignal(int)

class StartSignal(QObject):
    stim_started = pyqtSignal(int)

class StartStim(QRunnable):

    def __init__(self, 
                 stim_manager: StimManager, 
                 led_driver: LEDDriver, 
                 *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.started = False 
        self.keepgoing = True
        self.stim_manager = stim_manager
        self.led_driver = led_driver
        self.finished_signal = FinishedSignal()
        # self.start_signal = StartSignal()
        self.finished_signal.run_finished.connect(self.stim_manager.run_complete)
        # self.start_signal.connect(self.stim_manager.stim_started)
        
        self.pulse_start = np.zeros(self.stim_manager.n_elements)
        self.pulse_end = np.zeros(self.stim_manager.n_elements)
        self.pulse_duration = np.zeros(self.stim_manager.n_elements)


    def run(self):
        if self.started == True: 
            if self.stim_manager.shuffled_mask_keys:
                for i, key in enumerate(self.stim_manager.shuffled_mask_keys):
                    # self.start_signal.emit(True)
                    self.stim_manager.socket.send_string(str(i))
                    self.stim_manager.socket.send_string("START_RECORDING")
                    print('signal sent: ', time.time())
                    time.sleep(2) #1s sleep at camera code already 
                    # self.clear_dmd.emit()
                    self.stim_manager.mask_expose.emit(key)
                    print('Mask ' + self.stim_manager.mask_widgets[key].name + ' exposed')
                    time.sleep(1) #time.sleep given because sending command for mask exposure takes time
                    self.led_driver.pulse(duration_ms=self.stim_manager.duration_spinbox.value())
                    time.sleep(self.stim_manager.recording_duration_input.value())
                    self.stim_manager.socket.send_string('STOP_RECORDING')
                    interval = self.stim_manager.interval - self.stim_manager.recording_duration_input.value()
                    time.sleep(interval)

                    self.pulse_start[i] = self.led_driver.pulse_sender.time_start
                    self.pulse_end[i] = self.led_driver.pulse_sender.time_end
                    self.pulse_duration[i] = self.pulse_end[i] - self.pulse_start[i]

            else: 
                for key in self.stim_manager.mask_keys:
                    # self.clear_dmd.emit()
                    self.stim_manager.mask_expose.emit(key)
                    print('Mask ' + self.stim_manager.mask_widgets[key].name + ' exposed')
                    time.sleep(1)
                    self.led_driver.pulse(duration_ms=self.stim_manager.duration_spinbox.value())
                    time.sleep(self.stim_manager.interval_spinbox.value())

                    self.pulse_start[i] = self.led_driver.pulse_sender.time_start
                    self.pulse_end[i] = self.led_driver.pulse_sender.time_end
                    self.pulse_duration[i] = self.pulse_end[i] - self.pulse_start[i]
        
            # additional 2s before automatically ending the recording 
            time.sleep(2)
        
            self.finished_signal.run_finished.emit(True)
            # self.stim_manager.socket.send_string("LAUNCH METADATA")


# stim logger 
# to save: idx and name of mask exposed, time of exposure, time of appearance on screen, duration, fish_id 

# class MessageReceiver(QRunnable):
    
#     def __init__(self, 
#                  protocol: str, 
#                  cam_host: str, 
#                  cam_port: int,
#                  stim_manager: StimManager,
#                  *args, **kwargs):
        
#         super().__init__(*args, **kwargs)
        
#         self.stim_manager = stim_manager
        
#         self.context = zmq.Context()
#         self.start_stim_socket = self.context.socket(zmq.SUB)
#         self.start_stim_socket.connect(protocol + cam_host + ":" + str(cam_port))
#         self.start_stim_socket.setsockopt_string(zmq.SUBSCRIBE, "START_STIMULATION")

#     def run(self):
#         # while True: 
#         message = self.start_stim_socket.recv_string()
#         if message == "START_STIMULATION":
#             self.stim_manager.start()