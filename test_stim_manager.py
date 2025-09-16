from DrawMasks import  MaskManager, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
from daq import LabJackU3LV, LabJackU3LV_hl
from LED import LEDD1B, LEDWidget
from DMD import DMD
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool
from stimulation import StimManager
from camera_tools import XimeaCamera
from old_code.camera_widgets import CameraControl
from numpy.typing import NDArray
import cv2
from image_tools import regular_polygon, star
import sys
import numpy as np
from image_tools import DrawPolyMask
import json
from Microscope import ImageSender, ScanImage

def create_calibration_pattern(div: int, height: int, width: int) -> NDArray:
    
    step = min(height,width)//div
    calibration_pattern = np.zeros((height,width,3), np.uint8)

    for y in range(height//(2*div),height,step):
        for x in range(width//(2*div),width,step):

            n = np.random.randint(3,7)
            s = np.random.randint(step//4, step//2)
            pos = np.array([x,y])
            theta = 2*np.pi*np.random.rand()

            if np.random.rand()>0.5:
                poly = regular_polygon(pos,n,theta,s)
            else:
                poly = star(pos,n,theta,s//2,s)

            calibration_pattern = cv2.fillPoly(calibration_pattern, pts=[poly], color=(255, 255, 255))
    
    return calibration_pattern


PROTOCOL = "tcp://"
HOST = "localhost"
SI_FRAMES_PORT = 5001
SI_TRIGGER_PORT = 6001

# dmd settings
SCREEN_DMD = 2
DMD_HEIGHT = 1140
DMD_WIDTH = 912

# labjack settingss
PWM_CHANNEL = 4
GATING_CHANNEL = 5 

# calibration file
transformations = np.tile(np.eye(3), (3,3,1,1))
try:
    with open('calibration.json', 'r') as f:
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
daio = LabJackU3LV_hl()
led = LEDD1B(daio, pwm_channel=PWM_CHANNEL, gating_channel=GATING_CHANNEL, name = "470 nm")
led_widget = LEDWidget(led_drivers=[led])
led_widget.show()

# Communication with ScanImage
scan_image = ScanImage(PROTOCOL, HOST, SI_FRAMES_PORT)
twop_sender = ImageSender(scan_image)
thread_pool = QThreadPool()
thread_pool.start(twop_sender)


# # Camera 
# cam = XimeaCamera(0)
# camera_controls = CameraControl(cam)
# camera_controls.show()

# Control DMD
dmd_widget = DMD(screen_num=SCREEN_DMD)

pattern = create_calibration_pattern(2, DMD_HEIGHT, DMD_WIDTH)
dmd_widget.update_image(pattern)

# Masks
# cam_drawer = DrawPolyMask(np.zeros((512,512)))
cam_drawer = DrawPolyMask(np.zeros((480,640)))

dmd_drawer = DrawPolyMask(np.zeros((DMD_HEIGHT,DMD_WIDTH)))
twop_drawer = DrawPolyMask(np.zeros((512,512)))

cam_mask = DrawPolyMaskOpto(cam_drawer)
dmd_mask = DrawPolyMaskOptoDMD(dmd_drawer)
twop_mask = DrawPolyMaskOpto(twop_drawer)

masks = MaskManager([cam_mask, dmd_mask, twop_mask], ["Camera", "DMD", "Two Photon"], transformations)
masks.show()

stim = StimManager(mask_manager=masks, led_driver=led)
stim.show()

# connect signals and slots
dmd_mask.DMD_update.connect(dmd_widget.update_image)
masks.mask_expose.connect(dmd_mask.expose)
stim.mask_expose.connect(dmd_mask.expose)
masks.clear_dmd.connect(dmd_mask.clear)
twop_sender.scan_image.image_ready.connect(twop_mask.set_image)

app.exec()

