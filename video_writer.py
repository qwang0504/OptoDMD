import cv2
from numpy.typing import NDArray
import subprocess
import numpy as np
from abc import ABC

# TODO maybe add a multiprocessing queue

class VideoWriter(ABC):
    def write_frame(self, image: NDArray) -> None:
        pass

    def close(self) -> None:
        pass

# video writer opencv
class OpenCV_VideoWriter(VideoWriter):

    def __init__(
            self, 
            height: int, 
            width: int, 
            fps: int = 25, 
            filename: str = 'output.avi',
            fourcc: str = 'XVID'
        ) -> None:
        
        self.height = height
        self.width = width
        self.fps = fps
        self.filename = filename
        self.fourcc = cv2.VideoWriter_fourcc(*fourcc)
        self.color = True
        # self.write_file = cv2.VideoWriter(filename, self.fourcc, fps, (width, height), color)
        self.write_file = None

    # def start_writing(self, ready):
    #     if ready:
    #         self.writer = cv2.VideoWriter(self.filename, self.fourcc, self.fps, (self.width, self.height), self.color)

    def write_frame(self, image: NDArray) -> None:
        if len(image.shape) == 2:
            image = np.dstack((image,image,image))
        self.write_file.write(image)

    def close(self) -> None:
        self.write_file.release()




# video writer ffmpeg
class FFMPEG_VideoWriter(VideoWriter):

    def write_frame(self, image: NDArray) -> None:
        # requires RGB images
        if len(image.shape) == 2:
            image = np.dstack((image,image,image))
        self.ffmpeg_process.stdin.write(image.astype(np.uint8).tobytes())

    def close(self) -> None:
        self.ffmpeg_process.stdin.flush()
        self.ffmpeg_process.stdin.close()
        self.ffmpeg_process.wait()

class FFMPEG_VideoWriter_GPU(FFMPEG_VideoWriter):
    # To check which encoders are available, use:
    # ffmpeg -encoders
    #
    # To check which profiles and presets are available for a given encoder use:
    # ffmpeg -h encoder=h264_nvenc

    def __init__(
            self, 
            height: int, 
            width: int, 
            fps: int = 25, 
            q: int = 23,
            filename: str = 'output.avi',
            codec: str = 'h264_nvenc',
            profile: str = 'baseline',
            preset: str = 'p2'
        ) -> None:
        
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner", 
            "-loglevel", "error",
            "-y",  # Overwrite output file if it exists
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-r", str(fps),  # Frames per second
            "-s", f"{width}x{height}",  # Specify image size
            "-i", "-",  # Input from pipe
            "-c:v", codec, 
            "-profile:v", profile,
            "-preset", preset, 
            "-cq:v", str(q),
            "-pix_fmt", "yuv420p",  # Pixel format (required for compatibility)
            filename,
        ]
        self.ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        
# video writer ffmpeg
class FFMPEG_VideoWriter_CPU(FFMPEG_VideoWriter):
    # To check which encoders are available, use:
    # ffmpeg -encoders
    #
    # To check which profiles and presets are available for a given encoder use:
    # ffmpeg -h encoder=h264

    def __init__(
            self, 
            height: int, 
            width: int, 
            fps: int = 25, 
            q: int = 23,
            filename: str = 'output.avi',
            codec: str = 'h264',
            profile: str = 'baseline',
            preset: str = 'veryfast'
        ) -> None:
        
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner", 
            "-loglevel", "error",
            "-y",  # Overwrite output file if it exists
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-r", str(fps),  # Frames per second
            "-s", f"{width}x{height}",  # Specify image size
            "-i", "-",  # Input from pipe
            "-c:v", codec, 
            "-profile:v", profile,
            "-preset", preset, 
            "-crf", str(q),
            "-pix_fmt", "yuv420p",  # Pixel format (required for compatibility)
            filename,
        ]
        self.ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)