import zmq
import numpy as np
from numpy.typing import NDArray
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QObject
from PyQt5.QtWidgets import QLabel,  QWidget
from qt_widgets import NDarray_to_QPixmap
from image_tools import im2uint8
import time

# TODO: Pause is not working 

def deserialize(message: str) -> NDArray:
    '''deserialize string into numpy array'''

    data = [r.split(',') for r in message.split(';')]
    return np.array(data, dtype = np.float32)

class ScanImage(QObject):

    image_ready = pyqtSignal(np.ndarray)

    def __init__(self, protocol: str, host: str, port: int, *args, **kwargs) -> None:

        super().__init__(*args, **kwargs)

        self.context = zmq.Context()

        # get images from scanimage
        address_image = protocol + host + ":" + str(port)
        self.socket_image = self.context.socket(zmq.PULL)
        self.socket_image.connect(address_image)
    
    def get_image(self) -> np.ndarray:
        message = self.socket_image.recv()
        image = deserialize(message.decode())
        image = np.clip(image,0,1)
        return image

class ImageSender(QRunnable):

    def __init__(self, scan_image: ScanImage, *args, **kwargs):

        super().__init__(*args, **kwargs)
        
        self.scan_image = scan_image
        self.keepgoing = True
        # self.is_paused = False
    
    def stop(self):
        self.keepgoing = False
    
    # def pause(self):
    #     self.is_paused = True

    def run(self):
        while self.keepgoing:
            # if self.is_paused:
            #     time.sleep(1)
            #     continue
            image = self.scan_image.get_image()
            self.scan_image.image_ready.emit(image)

class TwoPhoton(QWidget):

    def __init__(self, sender: ImageSender, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.sender = sender
        self.sender.scan_image.image_ready.connect(self.display)
        self.thread_pool = QThreadPool()
        self.thread_pool.start(sender)

        self.twop_image = QLabel(self)
        self.twop_image.setFixedWidth(512)
        self.twop_image.setFixedHeight(512)

    @pyqtSlot(np.ndarray)
    def display(self, image: NDArray):
        image = im2uint8(image)
        self.twop_image.setPixmap(NDarray_to_QPixmap(image))
        self.update()

    def closeEvent(self, event):
        self.sender.stop()
