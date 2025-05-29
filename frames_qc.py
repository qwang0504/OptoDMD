import numpy as np
import matplotlib.pyplot as plt

dtype = [('index', int), ('timestamp', np.float32)]

cam = np.loadtxt(r'E:/automation_test/cam_frames_AQ_250_save_pwm_25Hz_video_start_time.txt', delimiter=',', dtype=dtype)
save = np.loadtxt(r'E:/automation_test/save_frames_AQ_250_pwm_25Hz_video_start_time.txt', delimiter=',', dtype=dtype)
display = np.loadtxt(r'E:/automation_test/cam_frames_AQ_250_display_ds_pwm_25Hz_video_start_time.txt', delimiter=',', dtype=dtype)
fps = 250

plt.plot(np.diff(cam['timestamp']))
plt.plot(np.diff(save['timestamp']))
plt.plot(np.diff(display['timestamp']))
plt.show()

print(np.where(np.diff(cam['index']) > 1))
print(np.where(np.diff(save['index']) > 1))

np.where(np.diff(cam['timestamp']).round(3) > (1/fps))
np.where(np.diff(save['timestamp']).round(3) > (1/fps))

np.diff(cam['timestamp']).round(5)
plt.plot(np.diff(cam['timestamp']).round(6))
plt.show()

# video_start = 162993693300

# start = 169938163300
# end = 170945475300
# end - start 
# ((start - video_start) / 10**9)*fps # = 1736, observed = 1728

# observed_start = np.array([1728, 3208, 4788, 18460, 19814, 22828, 25420])
# observed_end = np.array([1980, 3458, 5031, 18700, 20063, 23065, 25660])
# observed_end - observed_start 

# recorded_start = np.array([169938163300, 175857675300, 182177595300, 236866301000, 242281762200, 254337707400, 264705794400])
# recorded_end = np.array([170945475300, 176862112100, 183187194700, 237871028700, 243287748100, 255346272700, 265713817100])
# ((recorded_end - recorded_start)/ 10**9)*fps
# (((recorded_start - video_start) / 10**9)*fps).round() #only +8 frames difference vs observed


### For test_250_50DC_1s_25Hz
video_start = 53152175000
first_recorded = 57144199000
((first_recorded - video_start) / 10**9)*fps # = 998, observed = 989

observed_starts = np.array([989, 2831, 5019, 10765, 13473, 16522])
observed_ends = np.array([1238, 3080, 5270, 11017, 13723, 16765])
observed_ends - observed_starts

recorded_starts = np.array([57144199000, 64512046700, 73264127000, 96248109200, 107080394600, 119256470200])
recorded_ends = np.array([58148039400, 65514705900, 74273359200, 97256263800, 108090496900, 120266327300])
((recorded_ends - recorded_starts)/ 10**9)*fps

recorded_frames = np.round(((recorded_starts - video_start) / 10**9)*fps) #array([  998.,  2840.,  5028., 10774., 13482., 16526.])
recorded_frames - observed_starts #array([9., 9., 9., 9., 9., 4.])


### For test_250_50DC_1s_20Hz
video_start = 291912720500
first_recorded = 297769167000
((first_recorded - video_start) / 10**9)*fps # = 1464, observed = 1457

observed_starts = np.array([1457, 4501, 17199, 19911, 23451, 27423, 35997, 41168])
observed_ends = np.array([1704, 4753, 17448, 20163, 23697, 27670, 36243, 41420])
observed_ends - observed_starts

recorded_starts = np.array([297769167000, 309944609000, 360737337600, 371584711000, 385744699900, 401632738500, 435929531300, 456616869200])
recorded_ends = np.array([298776441900, 310951668300, 361740746300, 372593976400, 386752564100, 402642666900, 436936678200, 457620431000])
((recorded_ends - recorded_starts)/ 10**9)*fps

recorded_frames = np.round(((recorded_starts - video_start) / 10**9)*fps) #array([ 1464.,  4508., 17206., 19918., 23458., 27430., 36004., 41176.])
recorded_frames - observed_starts #array([7., 7., 7., 7., 7., 7., 7., 8.])


### For test_250_50DC_1s_25Hz_video_start_time
video_start = 66541236000
video_start_2 = 64687484200
first_recorded = 69238077600
((first_recorded - video_start) / 10**9)*fps # = 674, observed = 667
((first_recorded - video_start_2) / 10**9)*fps # = 1137, observed = 667 