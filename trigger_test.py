from daq import LabJackU3LV_hl
from LED import LEDWidget, LEDD1B
import u3
import time

d = u3.U3()

configDict = d.configIO()
configDict
d.getFeedback(u3.BitDirRead(0))
d.getFeedback(u3.BitStateRead(0))

d.getFeedback(u3.BitDirWrite(0, 1))
d.getFeedback(u3.BitStateWrite(0, 0))

d.getFeedback(u3.BitStateRead(0))

d.getFeedback(u3.BitStateWrite(0, 1))
time.sleep(1)
d.getFeedback(u3.BitStateWrite(0, 0))