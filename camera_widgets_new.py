# TODO record to file ?

from PyQt5.QtCore import QTimer, pyqtSignal, QRunnable, QThreadPool, QObject
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit
from qt_widgets import LabeledDoubleSpinBox, LabeledSliderDoubleSpinBox, NDarray_to_QPixmap
from camera_tools import Camera, Frame
import numpy as np
from video_writer import OpenCV_VideoWriter
import cv2 

# TODO show camera FPS, display FPS, and camera statistics in status bar
# TODO subclass CameraWidget for camera with specifi controls

class FrameSignal(QObject):
    image_ready = pyqtSignal(np.ndarray)
    
# TODO do the same using a MP_Queue/RingBuffer/ZMQ instead
class FrameSender(QRunnable):

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera
        self.signal = FrameSignal()
        self.acquisition_started = False
        self.keepgoing = True

    def start_acquisition(self):
        self.acquisition_started = True

    def stop_acquisition(self):
        self.acquisition_started = False

    def terminate(self):
        self.keepgoing = False

    def run(self):
        while self.keepgoing:
            if self.acquisition_started:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    self.signal.image_ready.emit(frame.image)


class FrameRecorder(QRunnable):

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera

        self.recording_started = False
        self.keepgoing = True

        self.height = int(self.camera.get_height())
        self.width = int(self.camera.get_width())
        self.recorder = OpenCV_VideoWriter(height=self.height, width=self.width)
    
    # def start_acquisition(self):
    #     self.acquisition_started = True

    def start_recording(self):
        self.recording_started = True
        self.camera.start_acquisition()
        self.recorder.start_writing(self.recording_started)

    def stop_acquisition(self):
        self.acquisition_started = False

    def terminate(self):
        self.keepgoing = False

    def set_filename(self, filename):
        self.recorder.filename = filename + '.avi'

    def set_fps(self, fps):
        self.recorder.fps = fps
        
    def set_fourcc(self, fourcc):
        self.recorder.fourcc = cv2.VideoWriter_fourcc(*fourcc)

    def run(self):
        while self.keepgoing:
            if self.recording_started and self.recorder.writer is not None:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    self.recorder.write_frame(frame.image)
        self.recorder.close()


class CameraControl(QWidget):

    image_ready = pyqtSignal(np.ndarray)

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera

        self.sender = FrameSender(camera)
        # this is breaking encapsulation a bit 
        self.sender.signal.image_ready.connect(self.image_ready)
        self.thread_pool = QThreadPool()
        self.thread_pool.start(self.sender)

        self.recorder = FrameRecorder(camera)
        self.thread_pool_r = QThreadPool()
        self.thread_pool_r.start(self.recorder)

        self.acquisition_started = False
        self.controls = [
            'framerate', 
            'exposure', 
            'gain', 
            'offsetX', 
            'offsetY', 
            'height', 
            'width'
        ]
        
        self.declare_components()
        self.layout_components()

    # UI ---------------------------------------------------------
    
    def create_spinbox(self, attr: str):
        '''
        Creates spinbox with correct label, value, range and increment
        as specified by the camera object. Connects to relevant
        callback.
        WARNING This is compact but a bit terse and introduces dependencies
        in the code. 
        '''
        if attr in ['framerate', 'exposure', 'gain']:
            setattr(self, attr + '_spinbox', LabeledSliderDoubleSpinBox(self))
        else:
            setattr(self, attr + '_spinbox', LabeledDoubleSpinBox(self))
        spinbox = getattr(self, attr + '_spinbox')
        spinbox.setText(attr)
        
        value = getattr(self.camera, 'get_' + attr)()
        range = getattr(self.camera, 'get_' + attr + '_range')()
        increment = getattr(self.camera, 'get_' + attr + '_increment')()
        
        if (
            value is not None 
            and range is not None
            and increment is not None
        ):
            spinbox.setRange(range[0],range[1])
            spinbox.setSingleStep(increment)
            spinbox.setValue(value)
        else:
            spinbox.setDisabled(True)

        callback = getattr(self, 'set_' + attr)
        spinbox.valueChanged.connect(callback)

    def update_values(self):

        for attr in self.controls:
            spinbox = getattr(self, attr + '_spinbox')
            value = getattr(self.camera, 'get_' + attr)()
            range = getattr(self.camera, 'get_' + attr + '_range')()
            increment = getattr(self.camera, 'get_' + attr + '_increment')()

            if (
                value is not None 
                and range is not None
                and increment is not None
            ):
                spinbox.setRange(range[0],range[1])
                spinbox.setSingleStep(increment)
                spinbox.setValue(value)
            else:
                spinbox.setDisabled(True)

    def declare_components(self):

        # Basic camera controls ----------------------------------
         
        self.start_button = QPushButton(self)
        self.start_button.setText('start')
        self.start_button.clicked.connect(self.start_acquisition)

        self.stop_button = QPushButton(self)
        self.stop_button.setText('stop')
        self.stop_button.clicked.connect(self.stop_acquisition)

        self.record_button = QPushButton(self)
        self.record_button.setText('record')
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton(self)
        self.stop_record_button.setText('stop recording')
        self.stop_record_button.clicked.connect(self.stop_recording)

        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText('file_name.avi')
        self.file_name_input.textEdited.connect(self.set_filename)

        self.encoding_fps_input = QLineEdit(self)
        self.encoding_fps_input.setPlaceholderText('encoding fps in integers')
        self.encoding_fps_input.textEdited.connect(self.set_fps)

        self.fourcc_input = QLineEdit(self)
        self.fourcc_input.setPlaceholderText('fourcc code in capital letters')
        self.fourcc_input.textEdited.connect(self.set_fourcc)

        # controls 
        for c in self.controls:
            self.create_spinbox(c)

        # Region of interest ------------------------------------

        self.ROI_groupbox = QGroupBox('ROI:')

    def layout_components(self):

        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)
        layout_start_stop.addWidget(self.record_button)
        layout_start_stop.addWidget(self.stop_record_button)

        layout_frame = QVBoxLayout(self.ROI_groupbox)
        layout_frame.addStretch()
        layout_frame.addWidget(self.offsetX_spinbox)
        layout_frame.addWidget(self.offsetY_spinbox)
        layout_frame.addWidget(self.height_spinbox)
        layout_frame.addWidget(self.width_spinbox)
        layout_frame.addStretch()

        layout_controls = QVBoxLayout(self)
        layout_controls.addStretch()
        layout_controls.addWidget(self.exposure_spinbox)
        layout_controls.addWidget(self.gain_spinbox)
        layout_controls.addWidget(self.framerate_spinbox)
        layout_controls.addWidget(self.file_name_input)
        layout_controls.addWidget(self.encoding_fps_input)
        layout_controls.addWidget(self.fourcc_input)
        layout_controls.addWidget(self.ROI_groupbox)
        layout_controls.addLayout(layout_start_stop)
        layout_controls.addStretch()

    # Callbacks --------------------------------------------------------- 

    def closeEvent(self, event):
        self.sender.terminate()
        self.stop_acquisition()

    def start_acquisition(self):
        if not self.acquisition_started:
            self.camera.start_acquisition()
            self.sender.start_acquisition()
            self.acquisition_started = True
            
    def stop_acquisition(self):
        if self.acquisition_started:
            self.sender.stop_acquisition()
            self.camera.stop_acquisition()
            self.acquisition_started = False

    def start_recording(self):
        if not self.acquisition_started:
            self.camera.start_acquisition()
            self.recorder.start_acquisition()
            self.acquisition_started = True

    def stop_recording(self):
        self.recorder.terminate()
        self.stop_acquisition()

    def set_exposure(self):
        self.camera.set_exposure(self.exposure_spinbox.value())
        self.update_values()

    def set_gain(self):
        self.camera.set_gain(self.gain_spinbox.value())
        self.update_values()

    def set_framerate(self):
        self.camera.set_framerate(self.framerate_spinbox.value())
        self.update_values()

    def set_offsetX(self):
        self.camera.set_offsetX(int(self.offsetX_spinbox.value()))
        self.update_values()
    
    def set_offsetY(self):
        self.camera.set_offsetY(int(self.offsetY_spinbox.value()))
        self.update_values()

    def set_width(self):
        self.camera.set_width(int(self.width_spinbox.value()))
        self.update_values()

    def set_height(self):
        self.camera.set_height(int(self.height_spinbox.value()))
        self.update_values()



class CameraControlRecording(QWidget):
    
    filename_ready = pyqtSignal(str)
    fps_ready = pyqtSignal(int)
    fourcc_ready = pyqtSignal(str)

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera
        
        self.acquisition_started = False

        self.recorder = FrameRecorder(camera)
        self.thread_pool = QThreadPool()
        self.thread_pool.start(self.recorder)

        self.filename_ready.connect(self.recorder.set_filename)
        self.fps_ready.connect(self.recorder.set_fps)
        self.fourcc_ready.connect(self.recorder.set_fourcc)

        self.declare_components()
        self.layout_components()

    def declare_components(self):

        self.record_button = QPushButton(self)
        self.record_button.setText('record')
        self.record_button.clicked.connect(self.start_recording)

        self.stop_record_button = QPushButton(self)
        self.stop_record_button.setText('stop recording')
        self.stop_record_button.clicked.connect(self.stop_recording)

        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText('file_name.avi')
        self.file_name_input.editingFinished.connect(self.set_filename)

        self.encoding_fps_input = QLineEdit(self)
        self.encoding_fps_input.setPlaceholderText('encoding fps in integers')
        self.encoding_fps_input.editingFinished.connect(self.set_fps)

        self.fourcc_input = QLineEdit(self)
        self.fourcc_input.setPlaceholderText('fourcc code in capital letters')
        self.fourcc_input.editingFinished.connect(self.set_fourcc)

    def layout_components(self):

        layout_record_start_stop = QHBoxLayout()
        layout_record_start_stop.addWidget(self.record_button)
        layout_record_start_stop.addWidget(self.stop_record_button)

        layout_controls = QVBoxLayout(self)
        layout_controls.addStretch()
        layout_controls.addWidget(self.file_name_input)
        layout_controls.addWidget(self.encoding_fps_input)
        layout_controls.addWidget(self.fourcc_input)
        layout_controls.addLayout(layout_record_start_stop)
        layout_controls.addStretch()

     # Callbacks --------------------------------------------------------- 

    def closeEvent(self, event):
        self.recorder.terminate()
        self.camera.stop_acquisition()

    def start_recording(self):
        if not self.acquisition_started:
            # self.camera.start_acquisition()
            self.recorder.start_recording()
            self.acquisition_started = True

    def stop_recording(self):
        if self.acquisition_started:
            self.recorder.terminate()
            # self.camera.stop_acquisition()
            self.acquisition_started = False

    def set_filename(self):
        filename = self.file_name_input.text()
        self.filename_ready.emit(filename)

    def set_fps(self):
        fps = int(self.encoding_fps_input.text())
        self.fps_ready.emit(fps)

    def set_fourcc(self):
        fourcc = self.fourcc_input.text()
        self.fourcc_ready.emit(fourcc)

class CameraPreview(QWidget):

    def __init__(self, camera_control: CameraControl, *args, **kwargs) -> None:
        
        super().__init__(*args, **kwargs)

        self.image_label = QLabel()

        self.camera_control = camera_control
        self.camera_control.image_ready.connect(self.update_image)

        layout = QHBoxLayout(self)
        layout.addWidget(self.image_label)
        layout.addWidget(self.camera_control)

    def update_image(self, image: np.ndarray):
        self.image_label.setPixmap(NDarray_to_QPixmap(image))
        


class CameraPreviewQ(QWidget): #make this qrunnable instead 
    
    def __init__(self, camera_control: CameraControl, *args, **kwargs) -> None:
        
        super().__init__(*args, **kwargs)

        self.image_label = QLabel()

        self.camera_control = camera_control
        self.camera_control.image_ready.connect(self.update_image)

        layout = QHBoxLayout(self)
        layout.addWidget(self.image_label)
        layout.addWidget(self.camera_control)

        # self.sender = sender
        # self.threadpool()
    
    def update_image(self, image: np.ndarray):
        self.image_label.setPixmap(NDarray_to_QPixmap(image))
        
    

class CameraWidget(QWidget):
    # Old class with QTimer

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera
        self.acquisition_started = False
        self.controls = [
            'framerate', 
            'exposure', 
            'gain', 
            'offsetX', 
            'offsetY', 
            'height', 
            'width'
        ]
        
        self.declare_components()
        self.layout_components()
        self.set_timers()

    # UI ---------------------------------------------------------
    
    def create_spinbox(self, attr: str):
        '''
        Creates spinbox with correct label, value, range and increment
        as specified by the camera object. Connects to relevant
        callback.
        WARNING This is compact but a bit terse and introduces dependencies
        in the code. 
        '''
        if attr in ['framerate', 'exposure', 'gain']:
            setattr(self, attr + '_spinbox', LabeledSliderDoubleSpinBox(self))
        else:
            setattr(self, attr + '_spinbox', LabeledDoubleSpinBox(self))
        spinbox = getattr(self, attr + '_spinbox')
        spinbox.setText(attr)
        
        value = getattr(self.camera, 'get_' + attr)()
        range = getattr(self.camera, 'get_' + attr + '_range')()
        increment = getattr(self.camera, 'get_' + attr + '_increment')()
        
        if (
            value is not None 
            and range is not None
            and increment is not None
        ):
            spinbox.setRange(range[0],range[1])
            spinbox.setSingleStep(increment)
            spinbox.setValue(value)
        else:
            spinbox.setDisabled(True)

        callback = getattr(self, 'set_' + attr)
        spinbox.valueChanged.connect(callback)

    def update_values(self):

        for attr in self.controls:
            spinbox = getattr(self, attr + '_spinbox')
            value = getattr(self.camera, 'get_' + attr)()
            range = getattr(self.camera, 'get_' + attr + '_range')()
            increment = getattr(self.camera, 'get_' + attr + '_increment')()

            if (
                value is not None 
                and range is not None
                and increment is not None
            ):
                spinbox.setRange(range[0],range[1])
                spinbox.setSingleStep(increment)
                spinbox.setValue(value)
            else:
                spinbox.setDisabled(True)

    def declare_components(self):

        # Image --------------------------------------------------

        self.image_label = QLabel(self) 

        # Basic camera controls ----------------------------------
         
        self.start_button = QPushButton(self)
        self.start_button.setText('start')
        self.start_button.clicked.connect(self.start_acquisition)

        self.stop_button = QPushButton(self)
        self.stop_button.setText('stop')
        self.stop_button.clicked.connect(self.stop_acquisition)

        # controls 
        for c in self.controls:
            self.create_spinbox(c)

        # Region of interest ------------------------------------

        self.ROI_groupbox = QGroupBox('ROI:')

    def layout_components(self):

        layout_start_stop = QHBoxLayout()
        layout_start_stop.addWidget(self.start_button)
        layout_start_stop.addWidget(self.stop_button)

        layout_frame = QVBoxLayout(self.ROI_groupbox)
        layout_frame.addStretch()
        layout_frame.addWidget(self.offsetX_spinbox)
        layout_frame.addWidget(self.offsetY_spinbox)
        layout_frame.addWidget(self.height_spinbox)
        layout_frame.addWidget(self.width_spinbox)
        layout_frame.addStretch()

        layout_controls = QVBoxLayout()
        layout_controls.addStretch()
        layout_controls.addWidget(self.exposure_spinbox)
        layout_controls.addWidget(self.gain_spinbox)
        layout_controls.addWidget(self.framerate_spinbox)
        layout_controls.addWidget(self.ROI_groupbox)
        layout_controls.addLayout(layout_start_stop)
        layout_controls.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.addStretch()
        main_layout.addWidget(self.image_label)
        main_layout.addLayout(layout_controls)
        main_layout.addStretch()

    def set_timers(self):

        self.timer = QTimer()
        self.timer.timeout.connect(self.grab)
        self.timer.setInterval(33)
        self.timer.start()

    # Callbacks --------------------------------------------------------- 

    def closeEvent(self, event):
        self.stop_acquisition()

    def grab(self):
        # TODO this is probably not the right way to do it. First it is dictating
        # the FPS with the QT timer, and second it is consuming frames.
        # I should probably send frames from outside (with a queue or something)
        # and use the class only to control camera features.

        # NOTE I should be able to flush the queue when I change parameters.

        if self.acquisition_started:
            frame = self.camera.get_frame()
            self.image_label.setPixmap(NDarray_to_QPixmap(frame.image))

    def start_acquisition(self):
        if not self.acquisition_started:
            self.camera.start_acquisition()
            self.acquisition_started = True
            
    def stop_acquisition(self):
        if self.acquisition_started:
            self.camera.stop_acquisition()
            self.acquisition_started = False

    def set_exposure(self):
        self.camera.set_exposure(self.exposure_spinbox.value())
        self.update_values()

    def set_gain(self):
        self.camera.set_gain(self.gain_spinbox.value())
        self.update_values()

    def set_framerate(self):
        self.camera.set_framerate(self.framerate_spinbox.value())
        self.update_values()

    def set_offsetX(self):
        self.camera.set_offsetX(int(self.offsetX_spinbox.value()))
        self.update_values()
    
    def set_offsetY(self):
        self.camera.set_offsetY(int(self.offsetY_spinbox.value()))
        self.update_values()

    def set_width(self):
        self.camera.set_width(int(self.width_spinbox.value()))
        self.update_values()

    def set_height(self):
        self.camera.set_height(int(self.height_spinbox.value()))
        self.update_values()
