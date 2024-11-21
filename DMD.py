from PyQt5.QtWidgets import QWidget, QLabel, QApplication
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap
from numpy.typing import NDArray
import numpy as np
from qt_widgets import NDarray_to_QPixmap
from image_tools import im2rgb, im2uint8
import cv2

class DMD(QWidget):

    def __init__ (self, screen_num: int = 0, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.screen_num = screen_num
        self.configure_screen()
        self.create_components()

    def configure_screen(self):
        
        self.app = QApplication.instance()
        self.screens_available = self.app.screens()
        self.screen = self.screens_available[self.screen_num]
        self.screen_width = self.screen.size().width()
        self.screen_height = self.screen.size().height()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint)
        self.setCursor(Qt.BlankCursor)
        self.showFullScreen()
        self.move(self.screen.geometry().topLeft())
        
    def create_components(self):

        pixmap = QPixmap(self.screen_width, self.screen_height)
        pixmap.fill(QColor('black'))

        self.img_label = QLabel(self)
        self.img_label.setPixmap(pixmap)
        self.img_label.setGeometry(0, 0, self.screen_width, self.screen_height)           
        self.img_label.show()

    @pyqtSlot(np.ndarray)
    def update_image(self, image: NDArray=None):
        # cv2.imshow('debug', image)
        # cv2.waitKey(0)
        # print('clicked')

        image = im2rgb(im2uint8(image))
        self.img_label.setPixmap(NDarray_to_QPixmap(image))     

class ImageSender(QWidget):

    send_image = pyqtSignal(np.ndarray)

    def __init__ (self, dmd_widget: DMD , *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.dmd_widget = dmd_widget

        self.send_image.connect(self.dmd_widget.update_image)

        self.timer = QTimer()
        self.timer.timeout.connect(self.loop)
        self.timer.setInterval(33)
        self.timer.start()
    
    def loop(self):
        image = np.random.randint(
            0, 255,
            [self.dmd_widget.screen_height, self.dmd_widget.screen_width], 
            np.uint8
        )

        self.send_image.emit(image)
