from PyQt5.QtCore import pyqtSignal, Qt, pyqtSlot
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QPushButton, QFrame, QLineEdit, QCheckBox, QListWidget 
import numpy as np
from qt_widgets import LabeledSpinBox, LabeledDoubleSpinBox, LabeledSliderSpinBox
from DrawMasks import MaskManager
from LED import LEDDriver, PulseSender
from daq import LabJackU3LV, LabJackU3LV_new, DigitalAnalogIO
import time

class StimManager(QWidget):

    mask_expose = pyqtSignal(int)
    
    def __init__(
            self,
            mask_manager : MaskManager,
            # daio: DigitalAnalogIO, 
            led_driver: LEDDriver,
            *args, **kwargs
            ):
    
        super().__init__(*args, **kwargs)

        self.mask_manager = mask_manager
        self.mask_widgets = self.mask_manager.mask_widgets
        self.mask_widgets_checked = {}
        # self.daio = daio
        self.led_driver = led_driver
        self.mask_keys = list(self.mask_widgets.keys())
        self.shuffled_mask_keys = None

        # self.get_checked_masks()
        self.create_components()
        self.layout_components()

    # only gets masks that are checked in the main window 
    def get_checked_masks(self):
        for key in self.mask_keys:
            mask_widget = self.mask_widgets[key]
            if mask_widget.show.checkState() == Qt.Checked:
                self.mask_widgets_checked[key] = mask_widget

    def create_components(self):
        self.rep_spinbox = LabeledSpinBox(self)
        self.rep_spinbox.setText('Number of repetitions')

        self.interval_spinbox = LabeledDoubleSpinBox(self)
        self.interval_spinbox.setText('Interval duration (s)')
        
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
        self.shuffle_button.setText('Shuffle stimuli order')
        self.shuffle_button.clicked.connect(self.shuffle_order)

        self.start_stim_button = QPushButton(self)
        self.start_stim_button.setText('Start stimulation')
        self.start_stim_button.clicked.connect(self.start_stim)

        # list display showing the shuffled masks order 
        self.shuffled_masks_display = QListWidget(self)
        self.shuffled_masks_names = []
        if self.shuffled_mask_keys is not None:
            for key in self.shuffled_mask_keys:
                self.shuffled_masks_names.append(self.mask_widgets[key].name)
        self.shuffled_masks_display.addItems(self.shuffled_masks_names)
        

    def layout_components(self):
        
        layout_overall = QHBoxLayout(self)

        layout_shuffle = QVBoxLayout()
        layout_shuffle.addWidget(self.shuffle_button)
        layout_shuffle.addWidget(self.shuffled_masks_display)

        layout_overall.addLayout(layout_shuffle)
        
        layout_controls = QVBoxLayout()

        layout_trial_controls = QHBoxLayout()
        layout_trial_controls.addWidget(self.rep_spinbox)
        layout_trial_controls.addWidget(self.interval_spinbox)

        layout_controls.addLayout(layout_trial_controls)

        layout_led_controls = QHBoxLayout()
        layout_led_controls.addWidget(self.intensity_slider)
        layout_led_controls.addWidget(self.freq_spinbox)
        layout_led_controls.addWidget(self.duration_spinbox)

        layout_controls.addLayout(layout_led_controls)

        layout_overall.addLayout(layout_controls)
        
    # shuffling with or without identical consecutive elements?
    # def randomise(self, masks, reps):
    #     #some code
    #     mask_copy = masks.copy()
    #     np.random.shuffle(mask_copy)

    #     while True:
    #         np.random.shuffle(lst)
    #         # Check for consecutive duplicates
    #         if all(lst[i] != lst[i + 1] for i in range(len(lst) - 1)):
    #             return lst


    # Callbacks
    def set_intensity(self, value: int):
        self.led_driver.set_intensity(value/100)

    def set_frequency(self, value: int):
        self.led_driver.set_frequency(value)

    def shuffle_order(self):
        mask_keys_copy = self.mask_keys.copy()
        self.shuffled_mask_keys = np.random.shuffle(mask_keys_copy)
        print(self.shuffled_mask_keys)
        # return self.shuffled_mask_list

    def start_stim(self):
        for key in self.shuffled_mask_keys:
            self.mask_expose.emit(key)
            print('Mask ' + self.mask_widgets[key].name + ' exposed')
            time.sleep(5)
            self.led_driver.pulse(duration_ms=self.duration_spinbox.value())
            time.sleep(self.interval_spinbox.value())