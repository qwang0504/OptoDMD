import numpy as np
import matplotlib.pyplot as plt

dtype = [('index', int), ('timestamp', np.float32)]

cam = np.loadtxt('cam_frames_AQ_250_display.txt', delimiter=',', dtype=dtype)
save = np.loadtxt(r'E:/automation_test/cam_frames_AQ_200_save.txt', delimiter=',', dtype=dtype)
display = np.loadtxt('cam_frames_AQ_250_display_ds.txt', delimiter=',', dtype=dtype)
fps = 200

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

video_start = 162993693300

start = 169938163300
end = 170945475300
end - start 
((start - video_start) / 10**9)*fps # = 1736, observed = 1728

observed_start = np.array([1728, 3208, 4788, 18460, 19814, 22828, 25420])
observed_end = np.array([1980, 3458, 5031, 18700, 20063, 23065, 25660])
observed_end - observed_start 

recorded_start = np.array([169938163300, 175857675300, 182177595300, 236866301000, 242281762200, 254337707400, 264705794400])
recorded_end = np.array([170945475300, 176862112100, 183187194700, 237871028700, 243287748100, 255346272700, 265713817100])
((recorded_end - recorded_start)/ 10**9)*fps
(((recorded_start - video_start) / 10**9)*fps).round() #only +8 frames difference vs observed