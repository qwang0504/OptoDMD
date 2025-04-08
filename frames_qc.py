import numpy as np
import matplotlib.pyplot as plt

dtype = [('index', int), ('timestamp', np.float32)]

cam = np.loadtxt('cam_frames_threads_AQ_highres_record_200_sentinel(4).txt', delimiter=',', dtype=dtype)
sink = np.loadtxt('record_frames_threads_AQ_highres_200_sentinel(4).txt', delimiter=',', dtype=dtype)

plt.plot(np.diff(cam['timestamp']))
plt.plot(np.diff(sink['timestamp']))
plt.show()

print(np.where(np.diff(cam['index']) > 1))
print(np.where(np.diff(sink['index']) > 1))

np.diff(cam['timestamp'])

np.diff(cam['timestamp']).round(5)
plt.plot(np.diff(cam['timestamp']).round(6))
plt.show()