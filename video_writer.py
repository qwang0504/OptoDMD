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
            # filename: str = 'output.mp4',
            filename: str = 'output.avi',
            # fourcc: str = 'X264'
            fourcc: str = 'XVID'
        ) -> None:
        
        self.height = height
        self.width = width
        self.fps = fps
        self.filename = filename
        self.fourcc = cv2.VideoWriter_fourcc(*fourcc)
        isColor = False
        self.writer = cv2.VideoWriter(filename, self.fourcc, fps, (width, height), isColor)

    def write_frame(self, image: NDArray) -> None:
        if len(image.shape) == 2:
            image = np.dstack((image,image,image))
        self.writer.write(image)

    def close(self) -> None:
        self.writer.release()


class FFMPEG_VideoWriter_GPU(VideoWriter):
    # To check which encoders are available, use:
    # ffmpeg -encoders
    #
    # To check which profiles and presets are available for a given encoder use:
    # ffmpeg -h encoder=h264_nvenc

    SUPPORTED_VIDEO_CODECS = ['h264_nvenc', 'hevc_nvenc']
    SUPPORTED_PRESETS = ['p1','p2','p3','p4','p5','p6','p7']
    SUPPORTED_PROFILES = ['main']
    PIX_FMT = 'yuv420p'

    def __init__(
            self, 
            height: int, 
            width: int, 
            fps: int = 25, 
            q: int = 23,
            filename: str = 'output.mp4',
            codec: str = 'h264_nvenc',
            profile: str = 'main',
            preset: str = 'p2'
        ) -> None:

        if not codec in self.SUPPORTED_VIDEO_CODECS:
            raise ValueError(f'wrong video_codec type, supported codecs are: {self.SUPPORTED_VIDEO_CODECS}') 

        ffmpeg_cmd_prefix = [
            "ffmpeg",
            "-hide_banner", 
            "-loglevel", "error",
            "-y",  # Overwrite output file if it exists
            "-f", "rawvideo",
            "-pix_fmt", self.PIX_FMT,
            "-r", str(fps),  # Frames per second
            "-s", f"{width}x{height}",  # Specify image size
            "-i", "-",  # Input from pipe
            "-c:v", codec 
        ]

        ffmpeg_cmd_suffix = [filename]
        
        ffmpeg_cmd_options = []
        if (codec == 'h264_nvenc') or (codec == 'hevc_nvenc'):

            if not profile in self.SUPPORTED_PROFILES:
                raise ValueError(f'wrong profile, supported profile are: {self.SUPPORTED_PROFILES}') 

            if not preset in self.SUPPORTED_PRESETS:
                raise ValueError(f'wrong preset, supported preset are: {self.SUPPORTED_PRESETS}') 

            if not (0 <= q <= 51):
                raise ValueError(f'q should be between 0 and 51') 
            
            ffmpeg_cmd_options = [
                "-profile:v", profile,
                "-preset", preset, 
                "-cq:v", str(q),
                "-pix_fmt", "yuv420p",  # Pixel format (required for compatibility)
            ]
        else:
            pass

        ffmpeg_cmd = ffmpeg_cmd_prefix + ffmpeg_cmd_options + ffmpeg_cmd_suffix
        self.ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    
    def write_frame(self, image: NDArray) -> None:
        # accepts grayscale or RGB images

        # converts to yuv420p before sending through the pipe
        # (faster than writing full fat RGB to the pipe)
        if len(image.shape) == 2:
            image = np.dstack((image,image,image))
        image_yuv420 = cv2.cvtColor(image, cv2.COLOR_RGB2YUV_I420) 

        self.ffmpeg_process.stdin.write(image_yuv420.tobytes())

    def close(self) -> None:
        self.ffmpeg_process.stdin.flush()
        self.ffmpeg_process.stdin.close()
        self.ffmpeg_process.wait()

class FFMPEG_VideoWriter_CPU(VideoWriter):
    # To check which encoders are available, use:
    # ffmpeg -encoders
    #
    # To check which profiles and presets are available for a given encoder use:
    # ffmpeg -h encoder=h264

    SUPPORTED_VIDEO_CODECS = ['h264', 'hevc', 'mjpeg']
    SUPPORTED_PRESETS = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']
    SUPPORTED_PROFILES = ['main']
    PIX_FMT = 'yuv420p'

    def __init__(
            self, 
            height: int, 
            width: int, 
            fps: int = 25, 
            q: int = 23,
            filename: str = 'output.mp4',
            codec: str = 'h264',
            profile: str = 'main',
            preset: str = 'veryfast'
        ) -> None:

        # added code to make attributes available for metadata logging purposes
        self.height = height
        self.width = width
        self.fps = fps
        self.q = q
        self.filename = filename
        self.codec = codec
        self.profile = profile
        self.preset = preset

        if not codec in self.SUPPORTED_VIDEO_CODECS:
            raise ValueError(f'wrong codec, supported codecs are: {self.SUPPORTED_VIDEO_CODECS}') 
        
        ffmpeg_cmd_prefix = [
            "ffmpeg",
            "-hide_banner", 
            "-loglevel", "error",
            "-y",  # Overwrite output file if it exists
            "-f", "rawvideo",
            "-pix_fmt", self.PIX_FMT,
            "-r", str(fps),  # Frames per second
            "-s", f"{width}x{height}",  # Specify image size
            "-i", "-",  # Input from pipe
            "-c:v", codec 
        ]

        ffmpeg_cmd_suffix = [filename]

        ffmpeg_cmd_options = []
        if (codec == 'h264') or (codec == 'hevc'):

            if not profile in self.SUPPORTED_PROFILES:
                raise ValueError(f'wrong profile, supported profile are: {self.SUPPORTED_PROFILES}') 

            if not preset in self.SUPPORTED_PRESETS:
                raise ValueError(f'wrong preset, supported preset are: {self.SUPPORTED_PRESETS}') 

            if (codec == 'h264'):
                if not (-12 <= q <= 51):
                    raise ValueError(f'q should be between -12 and 51, default 23') 
                
            elif (codec == 'hevc'):
                if not (0 <= q <= 51):
                    raise ValueError(f'q should be between 0 and 51, default 28') 

            ffmpeg_cmd_options = [
                "-profile:v", profile,
                "-preset", preset, 
                "-crf", str(q),
                "-pix_fmt", "yuv420p",  # Pixel format (required for compatibility)
            ]

        elif codec == 'mjpeg':
            if not (2 <= q <= 31):
                raise ValueError(f'q should be between 2 and 31, default 5')
            
            ffmpeg_cmd_options = [
                "-q:v", str(q),
                "-pix_fmt", "yuvj420p",  # Full-range YUV
            ]

        else:
            pass

        ffmpeg_cmd = ffmpeg_cmd_prefix + ffmpeg_cmd_options + ffmpeg_cmd_suffix
        self.ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    def write_frame(self, image: NDArray) -> None:
        # accepts grayscale or RGB images

        # converts to yuv420p before sending through the pipe
        # (faster than writing full fat RGB to the pipe)
        if len(image.shape) == 2:
            image = np.dstack((image,image,image))
        image_yuv420 = cv2.cvtColor(image, cv2.COLOR_RGB2YUV_I420) 

        self.ffmpeg_process.stdin.write(image_yuv420.tobytes())

    def close(self) -> None:
        self.ffmpeg_process.stdin.flush()
        self.ffmpeg_process.stdin.close()
        self.ffmpeg_process.wait()

class FFMPEG_VideoWriter_CPU_Grayscale(FFMPEG_VideoWriter_CPU):
    # Write grayscale directly for max throughput. Only supported by 'h264' codec with profile 'high'.

    SUPPORTED_VIDEO_CODECS = ['h264']
    SUPPORTED_PRESETS = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']
    SUPPORTED_PROFILES = ['high']
    PIX_FMT = 'gray'

    def write_frame(self, image: NDArray) -> None:
        # requires grayscale images
        if len(image.shape) == 3:
            image = image[:,:,0]
        self.ffmpeg_process.stdin.write(image.tobytes())

class FFMPEG_VideoWriter_CPU_YUV420P(FFMPEG_VideoWriter_CPU):
    # Stripped down version for max througput. Expects YUV420P input

    def write_frame(self, image_yuv420p: NDArray) -> None:
        self.ffmpeg_process.stdin.write(image_yuv420p.tobytes())

class FFMPEG_VideoWriter_GPU_YUV420P(FFMPEG_VideoWriter_GPU):
    # Stripped down version for max througput. Expects YUV420P input

    def write_frame(self, image_yuv420p: NDArray) -> None:
        self.ffmpeg_process.stdin.write(image_yuv420p.tobytes())