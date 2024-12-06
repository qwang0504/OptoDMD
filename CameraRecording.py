
from camera_tools import XimeaCamera
# from camera_tools import CameraControl, OpenCV_Webcam
from camera_widgets_new import CameraControl, CameraMetadata
from PyQt5.QtWidgets import QApplication
# from metadata import CameraMetadata

import sys
import numpy as np
from image_tools import DrawPolyMask
import json

if __name__ == "__main__":

    # zmq settings
    PROTOCOL = "tcp://"
    # SCANIMAGE_HOST = "o1-317"
    STIM_HOST = "o1-609"
    # SCANIMAGE_PORT = 5556
    STIM_PORT = 5506
    CAM_PORT = 5507
    
    app = QApplication(sys.argv)

    # Camera 
    cam = XimeaCamera(0)
    camera_controls = CameraControl(cam, protocol=PROTOCOL, stim_host=STIM_HOST, stim_port=STIM_PORT)#, cam_port=CAM_PORT)
    # zmq_threadpool = QThreadpool()

    camera_controls.show()

    # cam_metadata = CameraMetadata(cam_controls=camera_controls)

    # # # connect signals and slots
    # camera_controls.recording_finished.connect(cam_metadata.get_metadata)
    # cam_metadata.show()

    app.exec()

