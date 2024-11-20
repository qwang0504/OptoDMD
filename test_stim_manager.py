from DrawMasks import  MaskManager, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
from daq import LabJackU3LV, LabJackU3LV_new
from LED import LEDD1B, LEDWidget
from DMD import DMD
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool
from stimulation import StimManager

import sys
import numpy as np
from image_tools import DrawPolyMask
import json


PROTOCOL = "tcp://"
HOST = "o1-317"
PORT = 5555

# dmd settings
SCREEN_DMD = 1
DMD_HEIGHT = 1140
DMD_WIDTH = 912

# labjack settingss
PWM_CHANNEL = 6

# calibration file
transformations = np.tile(np.eye(3), (3,3,1,1))
try:
    with open('calibration_4x/calibration.json', 'r') as f:
        calibration = json.load(f)

    # 0: cam, 1: dmd, 2: twop
    transformations[0,1] = np.asarray(calibration["cam_to_dmd"])
    transformations[0,2] = np.asarray(calibration["cam_to_twop"])
    transformations[1,0] = np.asarray(calibration["dmd_to_cam"])
    transformations[1,2] = np.asarray(calibration["dmd_to_twop"])
    transformations[2,0] = np.asarray(calibration["twop_to_cam"])
    transformations[2,1] = np.asarray(calibration["twop_to_dmd"])
except:
    print("calibration couldn't be loaded, defaulting to identity")

app = QApplication(sys.argv)


# Control LEDs
daio = LabJackU3LV_new()
led = LEDD1B(daio, pwm_channel=PWM_CHANNEL, name = "465 nm") 
led_widget = LEDWidget(led_drivers=[led])
# led_widget.show()

# Control DMD
dmd_widget = DMD(screen_num=SCREEN_DMD)

# Masks
cam_drawer = DrawPolyMask(np.zeros((512,512)))
dmd_drawer = DrawPolyMask(np.zeros((DMD_HEIGHT,DMD_WIDTH)))
twop_drawer = DrawPolyMask(np.zeros((512,512)))

cam_mask = DrawPolyMaskOpto(cam_drawer)
dmd_mask = DrawPolyMaskOptoDMD(dmd_drawer)
twop_mask = DrawPolyMaskOpto(twop_drawer)

masks = MaskManager([cam_mask, dmd_mask, twop_mask], ["Camera", "DMD", "Two Photon"], transformations)
# masks.show()

stim = StimManager(mask_manager=masks, led_driver=led)
stim.show()

# connect signals and slots
dmd_mask.DMD_update.connect(dmd_widget.update_image)
masks.mask_expose.connect(dmd_mask.expose)
stim.mask_expose.connect(dmd_mask.expose)
masks.clear_dmd.connect(dmd_mask.clear)


app.exec()

