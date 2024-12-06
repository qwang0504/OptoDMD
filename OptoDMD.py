from Microscope import ImageSender, ScanImage
from DrawMasks import  MaskManager, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
from daq import LabJackU3LV, LabJackU3LV_new
from LED import LEDD1B, LEDWidget
from DMD import DMD
from camera_tools import XimeaCamera, CameraControl
# from camera_tools import CameraControl, OpenCV_Webcam
from camera_widgets_new import CameraControl
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool
from stimulation import StimManager
from metadata import StimMetadata

import sys
import numpy as np
from image_tools import DrawPolyMask
import json

if __name__ == "__main__":

    # zmq settings
    PROTOCOL = "tcp://"
    SCANIMAGE_HOST = "o1-317"
    # STIM_HOST = "o1-609"
    SCANIMAGE_PORT = 5572
    STIM_PORT = 5506
    CAM_PORT = 5507

    # dmd settings
    SCREEN_DMD = 1
    DMD_HEIGHT = 1140
    DMD_WIDTH = 912

    # labjack settingss
    PWM_CHANNEL = 6

    # calibration file
    transformations = np.tile(np.eye(3), (3,3,1,1))
    try:
        with open('calibration_3x/calibration.json', 'r') as f:
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

    # Communication with ScanImage
    scan_image = ScanImage(PROTOCOL, SCANIMAGE_HOST, SCANIMAGE_PORT)
    twop_sender = ImageSender(scan_image)
    thread_pool = QThreadPool()
    thread_pool.start(twop_sender)

    # Camera 
    # cam = XimeaCamera(0)
    # camera_controls = CameraControl(cam)
    # camera_controls.show()

    # Control LEDs
    daio = LabJackU3LV_new()
    led = LEDD1B(daio, pwm_channel=PWM_CHANNEL, name = "465 nm") 
    led_widget = LEDWidget(led_drivers=[led])
    led_widget.show()

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
    masks.show()
    # masks.print_names()

    stim = StimManager(mask_manager=masks, 
                       led_driver=led, 
                       protocol=PROTOCOL,
                       cam_host=SCANIMAGE_HOST,
                       stim_port=STIM_PORT)
    stim.show()

    # metadata = Metadata(stim_manager=stim, cam_controls=camera_controls)
    stim_metadata = StimMetadata(stim_manager=stim)

    # connect signals and slots
    dmd_mask.DMD_update.connect(dmd_widget.update_image)
    masks.mask_expose.connect(dmd_mask.expose)
    stim.mask_expose.connect(dmd_mask.expose)
    masks.clear_dmd.connect(dmd_mask.clear)
    stim.clear_dmd.connect(dmd_mask.clear)
    # camera_controls.image_ready.connect(cam_mask.set_image)
    twop_sender.scan_image.image_ready.connect(twop_mask.set_image)
    # stim.run_complete.connect(camera_controls.finish_recording)
    stim.run_complete.connect(stim_metadata.initialise_widget)

    app.exec()

    twop_sender.stop()
