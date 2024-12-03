from camera_tools.camera import Camera
from camera_tools.frame import Frame, BaseFrame
from typing import Optional, Tuple
from ximea import xiapi
from numpy.typing import NDArray
from camera_tools import XimeaCamera
from camera_tools import RandomCam, CameraPreview
import numpy as np
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool
import sys
import matplotlib.pyplot as plt
import matplotlib
import time
matplotlib.use('Qt5Agg')
from video_writer import OpenCV_VideoWriter

from camera_widgets_new import CameraControl_MP, CameraControl
from daq import LabJackU3LV, LabJackU3LV_new
from LED import LEDD1B, LEDWidget
from DrawMasks import  MaskManager, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
import sys
import numpy as np
from image_tools import DrawPolyMask
import json
from stimulation import StimManager

app = QApplication(sys.argv)
cam = XimeaCamera(0)
# cam = OpenCV_Webcam()
# cam = RandomCam((512, 512), dtype=np.float64)
camera_controls = CameraControl(cam)
camera_controls.show()

daio = LabJackU3LV_new()
led = LEDD1B(daio, pwm_channel=6, name = "465 nm") 
led_widget = LEDWidget(led_drivers=[led])
led_widget.show()

# camera_controls = CameraControlRecording(cam)
# camera_controls.show()

# preview = CameraPreview(camera_controls)
# preview.show()

app.exec()

# img = cam.get_frame().image
# plt.imshow(img)
# plt.show()

# cam.time_start
# cam.img_count
# cam.get_frame().timestamp

# QApplication.quit()

# videowriter = OpenCV_VideoWriter(height=500, width=400)

from video_writer import OpenCV_VideoWriter
import cv2
import time

w = OpenCV_VideoWriter(height=cam.get_height(), 
                       width=cam.get_width())
w.filename = 'test.avi'
w.fps = 200
w.write_file = cv2.VideoWriter(w.filename, w.fourcc, w.fps, (w.width, w.height), w.color)
cam.set_framerate(200)
cam.start_acquisition()
now = time.time()
duration = 5

while time.time() < now + duration:
    f = cam.get_frame()
    w.write_frame(f.image)
w.close()
cam.stop_acquisition()






cam.start_acquisition()

cam.stop_acquisition()
cam.get_frame()

SCREEN_DMD = 1
DMD_HEIGHT = 1140
DMD_WIDTH = 912

# labjack settingss
PWM_CHANNEL = 6

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


# Camera 
cam = XimeaCamera(0)
camera_controls = CameraControl_MP(cam)
camera_controls.show()

cam_drawer = DrawPolyMask(np.zeros((512,512)))
dmd_drawer = DrawPolyMask(np.zeros((DMD_HEIGHT,DMD_WIDTH)))
twop_drawer = DrawPolyMask(np.zeros((512,512)))

cam_mask = DrawPolyMaskOpto(cam_drawer)
dmd_mask = DrawPolyMaskOptoDMD(dmd_drawer)
twop_mask = DrawPolyMaskOpto(twop_drawer)

masks = MaskManager([cam_mask, dmd_mask, twop_mask], ["Camera", "DMD", "Two Photon"], transformations)
masks.show()
# masks.print_names()

# stim = StimManager(mask_manager=masks, led_driver=led)
# stim.show()

# connect signals and slots
# dmd_mask.DMD_update.connect(dmd_widget.update_image)
masks.mask_expose.connect(dmd_mask.expose)
# stim.mask_expose.connect(dmd_mask.expose)
masks.clear_dmd.connect(dmd_mask.clear)
# stim.clear_dmd.connect(dmd_mask.clear)
camera_controls.image_ready.connect(cam_mask.set_image)
# twop_sender.scan_image.image_ready.connect(twop_mask.set_image)