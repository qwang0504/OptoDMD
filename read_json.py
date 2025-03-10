import json 
import numpy as np
import matplotlib.pyplot as plt
import sys
from PyQt5.QtWidgets import QApplication
from camera_tools import XimeaCamera
from camera_widgets import CameraControl
import time
import cv2

# Open and read the JSON file
with open('camera_test.json', 'r') as file:
    cm = json.load(file)

with open('stim2.json', 'r') as file:
    tm = json.load(file)

start = np.array(tm['pulse_start'])
end = np.array(tm['pulse_end'])
vstart = np.array(cm['video_start'])

start_frames = (start - vstart)*200

# actual = np.array([533, 6737, 12933, 19136, 25340, 31543, 37746, 
#                   43949, 50155, 56360, 62563, 68769, 74972, 81175, 
#                   87360, 93562, 99765, 105918, 112121, 118318])

actual = np.array([206, 6410, 12616, 18820, 25022, 31184, 37387, 43504, 49763, 55827, 62030, 68233, 74353, 80557, 86609, 92680, 98883, 105171, 111246, 117406])

actual - start_frames

actual = np.array([183, 6410, 12616, 18820, 25022, 31184, 37387, 43504, 49763, 55827, 62030, 68233, 74353, 80557, 86609, 92680, 98883, 105171, 111246, 117406])



with open('100fps_4.5exp.avi.json', 'r') as file:
    m = json.load(file)

start = np.array(m['pulse_start'])
end = np.array(m['pulse_end'])
vstart = np.array(m['video_start'])

start_frames = (start - vstart)*100

actual = np.array([270, 3372, 6474, 9575, 12677, 15778, 
                   18880, 21982, 25085, 28186, 31288, 
                   34390, 37491 , 40592, 43695])

actual - start_frames



with open('test/20241205001/stim1.json', 'r') as file:
    m = json.load(file)

start = np.array(m['pulse_start'])
end = np.array(m['pulse_end'])

light_appeared = 875
vs = 875/200
vstart = start[0] - vs


start_frames = (start - vstart)*200

actual = np.array([270, 3372, 6474, 9575, 12677, 15778, 
                   18880, 21982, 25085, 28186, 31288, 
                   34390, 37491 , 40592, 43695])

actual - start_frames




app = QApplication(sys.argv)
cam = XimeaCamera(0)
cam_controls = CameraControl(cam)
cam_controls.show()




cam.stop_acquisition()
cam.start_acquisition()
duration = 600 
ts = np.zeros(duration*200)
index = np.zeros((duration+1)*200)
frame = np.zeros([(duration+1)*200, 2])
cam.set_framerate(200)
i = 0
now = time.time()
while time.time() < now + duration: 
    # frame[i] = cam.get_frame().image.shape
    ts[i] = cam.get_frame().timestamp
    # index[i] = cam.get_frame().index
    i += 1
cam.stop_acquisition()

np.sum(np.diff(ts) != 0)
ts = ts[:6000]

np.where(np.diff(ts) > 0)

np.save('timestamp_5min_200fps.npy', ts)
np.save('index_5min_200fps.npy', index)


np.save('timestamp_10min_200fps.npy', ts)
np.save('index_10min_200fps.npy', index)

cam.xi_cam.get_framerate()


writer = cv2.VideoWriter('test_frames.avi', 
                         cv2.VideoWriter_fourcc(*'XVID'), 
                         200, 
                         (488, 648), 
                         True)
i = 0
now = time.time()
while time.time() < now + duration: 
    # frame[i] = cam.get_frame().image.shape
    frame = cam.get_frame().image
    writer.write(frame)
    # index[i] = cam.get_frame().index
    i += 1
cam.stop_acquisition()