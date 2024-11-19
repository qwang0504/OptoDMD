from daq import DigitalAnalogIO
import time
from PyQt5.QtCore import QRunnable, QThreadPool
from PyQt5.QtWidgets import QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from qt_widgets import LabeledSliderSpinBox, LabeledSpinBox
from typing import Protocol, List

class LEDDriver(Protocol):
    
    def set_intensity(self, intensity: float) -> None:
        ...

    def on(self) -> None:
        ...

    def off(self) -> None:
        ...

    def pulse(self, duration_ms: int) -> None:
        ...

class PulseSender(QRunnable):

    def __init__(
            self, 
            DAIO: DigitalAnalogIO, 
            pulse_duration_ms: float, 
            pwm_channel: int,
            duty_cycle: float,
            pwm_frequency: int,
            *args, **kwargs):

        super().__init__(*args, **kwargs)
        
        self.DAIO = DAIO
        self.pulse_duration_ms = pulse_duration_ms
        self.pwm_channel = pwm_channel
        self.duty_cycle = duty_cycle
        self.pwm_frequency = pwm_frequency

    def run(self):
        self.DAIO.pwm(channel=self.pwm_channel, duty_cycle=self.duty_cycle, frequency=self.pwm_frequency)
        time_start = time.time() 
        time.sleep(self.pulse_duration_ms/1000.0)
        self.DAIO.pwm(channel=self.pwm_channel, duty_cycle=0, frequency=self.pwm_frequency)
        time_end = time.time()
        print('start: ', time_start)
        print('end: ', time_end)
        duration = time_end - time_start
        print('duration: ', duration)


class LEDD1B:
    '''
    Control a Thorlabs LED driver for optogenetics stimulation using PWM
    Two modes of operations.
    - LEDD1B switched to MOD: intensity controls the brightness of the LED, 
        high PWM frequency recommended
    - LEDD1B switched to TRIG: LED brightness controlled via the knob on the device,
        can use PWM frequency to flash the light at set brightness at a given frequency. 
        Intensity controls the duty cycle
    '''

    def __init__(
            self, 
            DAIO: DigitalAnalogIO, 
            pwm_frequency: float = 1000, 
            pwm_channel: int = 6,
            name: str = 'LED'
        ) -> None:

        self.DAIO = DAIO
        self.name = name
        self.pwm_frequency = pwm_frequency
        self.pwm_channel = pwm_channel 
        self.intensity = 1
        self.started = False
        self.thread_pool = QThreadPool()

    def set_intensity(self, intensity: float) -> None:

        if not (0 <= intensity <= 1):
            ValueError("intensity should be between 0 and 1")
            
        self.intensity = intensity
        if self.started:
            self.DAIO.pwm(channel=self.pwm_channel, duty_cycle=self.intensity, frequency=self.pwm_frequency)

    def set_frequency(self, freq: float) -> None:
        self.pwm_frequency = freq
        if self.started:
            self.DAIO.pwm(channel=self.pwm_channel, duty_cycle=self.intensity, frequency=self.pwm_frequency)
    
    def on(self):
        self.started = True
        self.DAIO.pwm(channel=self.pwm_channel, duty_cycle=self.intensity, frequency=self.pwm_frequency)

    def off(self):
        self.DAIO.pwm(channel=self.pwm_channel, duty_cycle=0, frequency=self.pwm_frequency)
        self.started = False

    def pulse(self, duration_ms: int = 1000):
        if self.started:
            raise RuntimeError('Already ON')

        pulse_sender = PulseSender(
            self.DAIO, 
            duration_ms, 
            self.pwm_channel, 
            self.intensity, 
            self.pwm_frequency
        )
        self.thread_pool.start(pulse_sender)



class DriverWidget(QWidget):
    
    def __init__(self, driver: LEDDriver, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.driver = driver
        self.declare_components()
        self.layout_components()

    def declare_components(self):

        self.name_label = QLabel(self)
        self.name_label.setText(self.driver.name)

        self.intensity_slider = LabeledSliderSpinBox(self)
        self.intensity_slider.setText('intensity (%)')
        self.intensity_slider.setRange(0, 100)
        self.intensity_slider.setValue(0)
        self.intensity_slider.valueChanged.connect(self.set_intensity)
        self.driver.set_intensity(0.5)

        self.on_button = QPushButton(self)
        self.on_button.setText('ON')
        self.on_button.clicked.connect(self.on)

        self.off_button = QPushButton(self)
        self.off_button.setText('OFF')
        self.off_button.clicked.connect(self.off)

        self.pulse_spinbox = LabeledSpinBox(self)
        self.pulse_spinbox.setText('pulse duration (ms)')
        self.pulse_spinbox.setRange(0, 100_000)
        self.pulse_spinbox.setValue(1000)

        self.freq_spinbox = LabeledSpinBox(self)
        self.freq_spinbox.setText('PWM frequency (Hz)')
        self.freq_spinbox.setRange(0, 100_000)
        self.freq_spinbox.setValue(1000)
        self.freq_spinbox.valueChanged.connect(self.set_frequency)

        self.pulse_button = QPushButton(self)
        self.pulse_button.setText('pulse')
        self.pulse_button.clicked.connect(self.pulse)

    def layout_components(self):
         
        main_layout = QHBoxLayout(self)
        main_layout.addStretch()
        main_layout.addWidget(self.name_label)
        main_layout.addWidget(self.intensity_slider)
        main_layout.addWidget(self.on_button)
        main_layout.addWidget(self.off_button)
        main_layout.addWidget(self.pulse_spinbox)
        main_layout.addWidget(self.freq_spinbox)
        main_layout.addWidget(self.pulse_button)
        main_layout.addStretch()

    def set_frequency(self, val: int):
        self.driver.set_frequency(val)

    def set_intensity(self, val: int):
        self.driver.set_intensity(val/100)

    def on(self):
        self.driver.on()

    def off(self):
        self.driver.off()

    def pulse(self):
        self.driver.pulse(duration_ms=self.pulse_spinbox.value())


class LEDWidget(QWidget):

    def __init__(self, led_drivers: List[LEDDriver], *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.led_drivers = led_drivers
        self.declare_components()
        self.layout_components()

    def declare_components(self):
        
        self.driver_widgets = []
        for driver in self.led_drivers:
            self.driver_widgets.append(DriverWidget(driver))

    def layout_components(self):
        
        main_layout = QVBoxLayout(self)
        main_layout.addStretch()
        for w in self.driver_widgets:
            main_layout.addWidget(w)
        main_layout.addStretch()