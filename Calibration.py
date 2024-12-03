from Microscope import ImageSender, ScanImage
from DrawMasks import  MaskManager, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
from daq import LabJackU3LV, myArduino
from LED import LEDD1B, LEDWidget
from DMD import DMD
from camera_tools import XimeaCamera, CameraControl
from camera_tools import CameraControl, OpenCV_Webcam
from PyQt5.QtWidgets import QApplication
from alignment_tools import AlignAffine2D
import sys
import numpy as np
from typing import Tuple
from numpy.typing import NDArray
import cv2
from image_tools import regular_polygon, star
import json

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

if __name__ == "__main__":

    CALIBRATE_CAMERA = True
    CALIBRATE_TWOPHOTON = False
    SCREEN_DMD = 1
    DMD_HEIGHT = 1140
    DMD_WIDTH = 912
    XIMEA_INDEX = 1

    I = np.eye(3)
    dmd_to_cam = I
    cam_to_dmd = I
    cam_to_twop = I
    twop_to_cam = I
    dmd_to_twop = I
    twop_to_dmd = I
    
    if CALIBRATE_CAMERA:

        # Project a pattern onto a slide, and image the slide on the camera
        pattern = create_calibration_pattern(5, DMD_HEIGHT, DMD_WIDTH)

        app = QApplication(sys.argv)

        # projector
        dmd_widget = DMD(screen_num=SCREEN_DMD)
        dmd_widget.update_image(pattern)

        # get image from camera 
        cam = XimeaCamera(XIMEA_INDEX)
        #cam = OpenCV_Webcam(-1)
        cam.set_exposure(1000)
        cam.start_acquisition()
        input("Press Enter to grab frame...")
        frame = cam.get_frame()
        cam.stop_acquisition()
        dmd_widget.close()

        register = AlignAffine2D(pattern, frame.image)
        register.show()
        app.exec()

        cam_to_dmd = register.affine_transform        
        dmd_to_cam = np.linalg.inv(cam_to_dmd)

        calibration_cam_dmd = {
            'dmd_to_cam': dmd_to_cam.tolist(),
            'cam_to_dmd': cam_to_dmd.tolist()
        }
    
        with open('calibration_cam_dmd.json', 'w') as f:
            json.dump(calibration_cam_dmd, f)

    if CALIBRATE_TWOPHOTON:
    
        app = QApplication(sys.argv)
    
        # communicate with scanimage
        PROTOCOL = "tcp://"
        HOST = "o1-317"
        PORT = 5560

        print("""
        Put a slide with some structure under the microscope
        and take an epifluorescence image with the camera.
        The slide should be very thin and (auto-)fluorescent.
        """)

        # use the DMD to expose the image
        dmd_widget = DMD(screen_num=SCREEN_DMD)
        dmd_widget.update_image(255*np.ones((DMD_HEIGHT,DMD_WIDTH,3), np.uint8))
        
        # get image from camera
        cam = XimeaCamera(XIMEA_INDEX)
        cam.set_exposure(10_000)
        cam.start_acquisition()
        input("Press Enter to grab frame...")
        frame = cam.get_frame()
        print("...image captured")
        cam.stop_acquisition()

        # stop light
        dmd_widget.close()

        # get image from scanimage 
        scan_image = ScanImage(PROTOCOL, HOST, PORT)
        input("Acquire image with scanimage, then press Enter to grab frame...")
        twop_image = scan_image.get_image() 
        print("...image captured")

        # do the registration
        register = AlignAffine2D(twop_image, frame.image)
        register.show()
        app.exec()
        
        cam_to_twop = register.affine_transform
        twop_to_cam = np.linalg.inv(cam_to_twop)

        calibration_cam_twop = {
            'cam_to_twop': cam_to_twop.tolist(),
            'twop_to_cam': twop_to_cam.tolist()
        }

        with open('calibration_cam_twop.json', 'w') as f:
            json.dump(calibration_cam_twop, f)

    # DMD to 2P ----------------------------------------------------------------

    with open('calibration_cam_dmd.json', 'r') as f1:
        cal_cam_dmd = json.load(f1)

    with open('calibration_cam_twop.json', 'r') as f2:
        cal_cam_twop = json.load(f2)
        
    dmd_to_twop = np.asarray(cal_cam_twop['cam_to_twop']) @ np.asarray(cal_cam_dmd['dmd_to_cam']) 
    twop_to_dmd = np.asarray(cal_cam_dmd['cam_to_dmd']) @ np.asarray(cal_cam_twop['twop_to_cam']) 

    # Save results to file -----------------------------------------------------

    calibration = {
        'dmd_to_cam': cal_cam_dmd['dmd_to_cam'],
        'cam_to_dmd': cal_cam_dmd['cam_to_dmd'],
        'cam_to_twop': cal_cam_twop['cam_to_twop'],
        'twop_to_cam': cal_cam_twop['twop_to_cam'],
        'dmd_to_twop': dmd_to_twop.tolist(),
        'twop_to_dmd': twop_to_dmd.tolist()
    }

    with open('calibration.json', 'w') as f:
        json.dump(calibration, f)