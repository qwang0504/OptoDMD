import numpy as np
import matplotlib.pyplot as plt

dtype = [('index', int), ('timestamp', np.float32)]

cam = np.loadtxt('cam_frames_AQ_250_display.txt', delimiter=',', dtype=dtype)
save = np.loadtxt('save_frames_AQ_250.txt', delimiter=',', dtype=dtype)
display = np.loadtxt('cam_frames_AQ_250_display_ds.txt', delimiter=',', dtype=dtype)
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