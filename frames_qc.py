import numpy as np
import matplotlib.pyplot as plt

dtype = [('index', int), ('timestamp', np.float64)]

cam = np.loadtxt('cam_frames_AQ_200.txt', delimiter=',', dtype=dtype)
sink = np.loadtxt('sink_frames_AQ_200.txt', delimiter=',', dtype=dtype)

plt.plot(np.diff(cam['timestamp']))
plt.plot(np.diff(sink['timestamp']))
plt.show()

print(np.where(np.diff(cam['index']) > 1))
print(np.where(np.diff(sink['index']) > 1))

np.diff(cam['timestamp'])

np.diff(cam['timestamp']).round(5)
plt.plot(np.diff(cam['timestamp']).round(6))
plt.show()