from camera_tools.camera import Camera
from camera_tools.frame import Frame, BaseFrame
from typing import Optional, Tuple
from ximea import xiapi
from numpy.typing import NDArray
from camera_tools import XimeaCamera, CameraControl
from camera_tools import CameraControl, OpenCV_Webcam, RandomCam, CameraPreview
import numpy as np
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool
import sys
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')


app = QApplication(sys.argv)
# cam = XimeaCamera(1)
# cam = OpenCV_Webcam()
cam = RandomCam((512, 512), dtype=np.float64)
camera_controls = CameraControl(cam)
camera_controls.show()

preview = CameraPreview(camera_controls)
preview.show()

app.exec()

img = cam.get_frame().image
plt.imshow(img)
plt.show()

cam.time_start
cam.img_count
cam.get_frame().timestamp

QApplication.quit()