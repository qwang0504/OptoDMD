import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
import pathlib
from ScanImageTiffReader import ScanImageTiffReader
from suite2p import run_s2p, default_ops
import json

# ScanImageTiffReader documentation: https://vidriotech.gitlab.io/scanimagetiffreader-python/

img_dir = pathlib.Path(r'E:\automation_test\20250711001\stim3')
analysis_dir = pathlib.Path(r'E:\2p_analysis')
tif_paths = list(img_dir.glob('*.tif'))

vol=ScanImageTiffReader(str(tif_paths[0])).data()
channel1 = vol[0::2, :, :]  # Select every other frame starting from index 0
channel2 = vol[1::2, :, :] 

plt.plot(np.ravel(channel2))
plt.show()
threshold = 200

stim_start_frame = np.where(channel2 > threshold)[0][0]
stim_start_y = np.where(channel2 > threshold)[1][0]
stim_start_x = np.where(channel2 > threshold)[2][0]

stim_end_frame = np.where(channel2 > threshold)[0][-1]
stim_end_y = np.where(channel2 > threshold)[1][-1]
stim_end_x = np.where(channel2 > threshold)[2][-1]

plt.imshow(channel2[stim_start_frame], cmap='gray')
plt.scatter(x=stim_start_x, y=stim_start_y, color='red')
plt.show()

plt.imshow(channel2[stim_end_frame], cmap='gray')
plt.scatter(x=stim_end_x, y=stim_end_y, color='red')
plt.show()

ts_pix_sum = np.sum(channel2, axis=(1,2))
plt.plot(ts_pix_sum)
plt.show()

np.max(ts_pix_sum)

ops = default_ops()
ops['nchannels'] = 2
ops['save_folder'] = str(analysis_dir)
ops['data_path'] = str(img_dir)

bad_frames = np.arange(stim_start_frame, stim_end_frame + 1)
pathlib.Path(img_dir, 'bad_frames.npy')
np.save(pathlib.Path(analysis_dir, 'bad_frames.npy'), bad_frames)

with open('stim_coordinates.json', 'r') as file: 
    stim_data = json.load(file)

obj_resolution = stim_data['objective_resolution']
rois = stim_data['rois']

stim_angles = np.array([roi['scanfields']['centerXY'] for roi in rois if roi['scanfields']['centerXY'] != [0,0]])

stim_coordinates = stim_angles * obj_resolution
ones = np.ones((stim_coordinates.shape[0], 1))
stim_coordinates = np.round(np.hstack((stim_coordinates, ones)))

# stim_coordinates = [roi['scanfields']['centerXY'] + [1] for roi in rois if roi['scanfields']['centerXY'] != [0,0]]