from PyQt5.QtCore import pyqtSignal, Qt, QRunnable, QThreadPool, pyqtSlot
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QPushButton, QFrame, QLineEdit, QCheckBox, QListWidget
from qt_widgets import LabeledSpinBox, LabeledDoubleSpinBox, LabeledSliderSpinBox
from DrawMasks import MaskManager
from LED import LEDDriver, PulseSender
from daq import LabJackU3LV, LabJackU3LV_new, DigitalAnalogIO
import time
import numpy as np


class StimManager(QWidget):

    mask_expose = pyqtSignal(int)
    clear_dmd = pyqtSignal()
    
    def __init__(
            self,
            mask_manager : MaskManager,
            led_driver: LEDDriver,
            *args, **kwargs
            ):
    
        super().__init__(*args, **kwargs)

        self.mask_manager = mask_manager

        self.led_driver = led_driver
        self.mask_manager.draw_complete.connect(self.update_draw_display)
        self.thread_pool = QThreadPool()

        self.create_components()
        self.layout_components()
    
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

        self.shuffle_button = QPushButton(self)
        self.shuffle_button.setText('Shuffle order')
        self.shuffle_button.clicked.connect(self.shuffle_order)

        self.start_stim_button = QPushButton(self)
        self.start_stim_button.setText('Start stimulation')
        self.start_stim_button.clicked.connect(self.start)

        self.masks_display = QListWidget(self)


    def layout_components(self):
        
        layout_overall = QHBoxLayout(self)

        layout_shuffle = QVBoxLayout()
        layout_shuffle.addWidget(self.shuffle_button)
        layout_shuffle.addWidget(self.masks_display)
        layout_shuffle.setSpacing(10)

        layout_overall.addLayout(layout_shuffle)
        
        layout_controls = QVBoxLayout()

        layout_controls.addWidget(self.intensity_slider)
        layout_controls.addWidget(self.freq_spinbox)
        layout_controls.addWidget(self.duration_spinbox)


        layout_trial_controls = QHBoxLayout()
        layout_trial_controls.addWidget(self.rep_spinbox)
        layout_trial_controls.addWidget(self.interval_spinbox)

        layout_controls.addLayout(layout_trial_controls)
        layout_controls.addWidget(self.start_stim_button)
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

    def update_shuffle_display(self, shuffled):
        if self.masks_display.count() > 0:
            self.masks_display.clear()
            self.masks_display.addItems(shuffled)

    def start(self):
        start_stim = StartStim(stim_manager=self, 
                               led_driver=self.led_driver) #insert parameters
        self.thread_pool.start(start_stim)


class StartStim(QRunnable):
    
    def __init__(self, 
                 stim_manager: StimManager, 
                 led_driver: LEDDriver, 
                 *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.stim_manager = stim_manager
        self.led_driver = led_driver

    def run(self):
        if self.stim_manager.shuffled_mask_keys:
            for key in self.stim_manager.shuffled_mask_keys:
                # self.clear_dmd.emit()
                self.stim_manager.mask_expose.emit(key)
                print('Mask ' + self.stim_manager.mask_widgets[key].name + ' exposed')
                time.sleep(1)
                self.led_driver.pulse(duration_ms=self.stim_manager.duration_spinbox.value())
                time.sleep(self.stim_manager.interval_spinbox.value())
        else: 
             for key in self.stim_manager.mask_keys:
                # self.clear_dmd.emit()
                self.stim_manager.mask_expose.emit(key)
                print('Mask ' + self.stim_manager.mask_widgets[key].name + ' exposed')
                time.sleep(1)
                self.led_driver.pulse(duration_ms=self.stim_manager.duration_spinbox.value())
                time.sleep(self.stim_manager.interval_spinbox.value())

# stim logger 
# to save: idx and name of mask exposed, time of exposure, time of appearance on screen, duration, fish_id 
