from DMD import DMD
import numpy as np
import sys
import json
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    # dmd settings
    SCREEN_DMD = 2
    # main screen: 0, right vertical screen: 1, DMD: 2
    DMD_HEIGHT = 1140
    DMD_WIDTH = 912

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

    # Control DMD
    dmd_widget = DMD(screen_num=SCREEN_DMD)


    app.exec()