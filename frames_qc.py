import numpy as np
import matplotlib.pyplot as plt

dtype = [('index', int), ('timestamp', np.float32)]

cam = np.loadtxt(r'E:/automation_test/20250530001/stim8/save_frames4.txt', delimiter=',', dtype=dtype)
save = np.loadtxt('save_frames_AQ_250.txt', delimiter=',', dtype=dtype)
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


### For 20250530001 stim8 
fps = 250

recorded_starts = np.array([68717632500.0, 87737010400.0, 106770563000.0, 125804177500.0])
recorded_ends =  np.array([69721312900.0, 88754982300.0, 107788668200.0, 126821537400.0])
recorded_durations = np.array([1003680400.0, 1017971900.0, 1018105200.0, 1017359900.0])

# trial 1
video_start = 65707332200
(((recorded_starts[0] - video_start) / 10**9)*fps).round() # = 753, observed = 743

# trial 2
video_start = 84719056100
(((recorded_starts[1] - video_start) / 10**9)*fps).round() # = 754, observed = 746

# trial 3
video_start = 103755815500
(((recorded_starts[2] - video_start) / 10**9)*fps).round() # = 754, observed = 746

# trial 4
video_start = 122780269100
(((recorded_starts[3] - video_start) / 10**9)*fps).round() # = 756, observed = 750


### For 20250530001 stim7
fps = 200

recorded_starts = np.array([349612291600.0, 368637185100.0, 387678755800.0, 406712208700.0, 425738110400.0, 444765503200.0])
recorded_ends = np.array([350116236700.0, 369147349700.0, 388187976600.0, 407221398300.0, 426250289000.0, 445270446000.0])
recorded_durations = np.array([503945100.0, 510164600.0, 509220800.0, 509189600.0, 512178600.0, 504942800.0])

# trial 1
video_start = 346609572200
(((recorded_starts[0] - video_start) / 10**9)*fps).round() # = 601, observed = 594

# trial 2
video_start = 365626992600
(((recorded_starts[1] - video_start) / 10**9)*fps).round() # = 602, observed = 596

# trial 3
video_start = 384661641300
(((recorded_starts[2] - video_start) / 10**9)*fps).round() # = 603, observed = 597

# trial 4
video_start = 403697737600
(((recorded_starts[3] - video_start) / 10**9)*fps).round() # = 603, observed = 598

# trial 5
video_start = 422720083800
(((recorded_starts[4] - video_start) / 10**9)*fps).round() # = 604, observed = 599

# trial 6
video_start = 441759247400
(((recorded_starts[5] - video_start) / 10**9)*fps).round() # = 601, observed = 596



### For 20250530001 stim6
fps = 200

recorded_starts = np.array([102373080300.0, 121417381300.0, 140450793200.0, 159484559400.0, 178517921500.0, 197551458800.0])
recorded_ends = np.array([103386369400.0, 122426544100.0, 141468583900.0, 160502279200.0, 179535769000.0, 198568800300.0])
recorded_durations = np.array([1013289100.0, 1009162800.0, 1017790700.0, 1017719800.0, 1017847500.0, 1017341500.0])

# trial 1
video_start = 99367103100
(((recorded_starts[0] - video_start) / 10**9)*fps).round() # = 601, observed = 595

# trial 2
video_start = 118399745100
(((recorded_starts[1] - video_start) / 10**9)*fps).round() # = 604, observed = 597

# trial 3
video_start = 137436608600
(((recorded_starts[2] - video_start) / 10**9)*fps).round() # = 603, observed = 596

# trial 4
video_start = 156468991800
(((recorded_starts[3] - video_start) / 10**9)*fps).round() # = 603, observed = 596

# trial 5
video_start = 175501518600
(((recorded_starts[4] - video_start) / 10**9)*fps).round() # = 603, observed = 598

# trial 6
video_start = 194540343400
(((recorded_starts[5] - video_start) / 10**9)*fps).round() # = 602, observed = 598


### over 12 trials at 200fps, ~29ms difference between observed and recorded i.e. 6 frames at 200fps 

