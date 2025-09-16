import sys
from multiprocessing import Process, Pipe, Event
from arrayqueues import ArrayQueue
from ipc_tools import ModifiableRingBuffer
from mp_display import CameraWidget
from mp_msg_relay import MessageRelay
from camera_tools import XimeaCamera
from functools import partial
from mp_cam_process import CameraProcess
from mp_save_process import SaveProcess
from DrawMasks import MaskManager
from stimulation import StimManager
from LED import LEDD1B
from metadata import Metadata
import numpy as np
import json
from daq import LabJackU3LV_hl
from LED import LEDWidget, LEDD1B
from DMD import DMD
from DrawMasks import DrawPolyMask, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
from Microscope import ImageSender, ScanImage
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool

# TODO: check arrayqueue length
# TODO: PWM duty cycle not precise
# TODO: termination methods
# TODO: close sockets cleanly

if __name__ == "__main__":

    # labjack settingss
    PWM_CHANNEL = 4
    PMT_TTL_CHANNEL = 5 
    
    app = QApplication(sys.argv)
    
    
    # Control LEDs
    daio = LabJackU3LV_hl()
    led = LEDD1B(daio, pwm_channel=PWM_CHANNEL, name = "475 nm", gating_channel=PMT_TTL_CHANNEL) 
    led_widget = LEDWidget(led_drivers=[led])
    led_widget.show()

    app.exec()
