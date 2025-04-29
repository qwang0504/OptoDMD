class FrameWriter(QRunnable):

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera

        self.recording_started = False
        self.keepgoing = True

        self.height = int(self.camera.get_height())
        self.width = int(self.camera.get_width())
        self.writer = OpenCV_VideoWriter(height=self.height, width=self.width)
    
    # def start_acquisition(self):
    #     self.acquisition_started = True

    def start_recording(self):
        self.recording_started = True
        self.camera.start_acquisition()
        self.writer.start_writing(self.recording_started)

    def stop_recording(self):
        self.recording_started = False
        self.camera.stop_acquisition()

    def terminate(self):
        self.keepgoing = False

    def set_filename(self, filename):
        self.writer.filename = filename + '.avi'

    def set_fps(self, fps):
        self.writer.fps = fps
        
    def set_fourcc(self, fourcc):
        self.writer.fourcc = cv2.VideoWriter_fourcc(*fourcc)

    def run(self):
        while self.keepgoing:
            if self.recording_started and self.writer.writer is not None:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    self.writer.write_frame(frame.image)
        self.writer.close()

class FrameWriterSingle(QRunnable):

    def __init__(self, camera: Camera, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.camera = camera

        self.recording_started = False
        self.keepgoing = True

    # def start_acquisition(self):
    #     self.acquisition_started = True

    def start_recording(self):
        self.recording_started = True
        self.camera.start_acquisition()

    def stop_recording(self):
        self.recording_started = False
        self.camera.stop_acquisition()

    def terminate(self):
        self.keepgoing = False

    def set_filename(self, filename):
        self.filename = 'test/' + filename 

    def set_fps(self, fps):
        self.fps = fps
        
    def set_fourcc(self, fourcc):
        self.fourcc = cv2.VideoWriter_fourcc(*fourcc)

    def run(self):
        idx = 0
        while self.keepgoing:
            if self.recording_started:
                frame = self.camera.get_frame()
                if frame.image is not None:
                    cv2.imwrite(self.filename + str(idx) + '.tiff', frame.img)
                    idx += 1
