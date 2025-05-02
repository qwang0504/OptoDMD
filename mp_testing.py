import sys
from multiprocessing import Process, Pipe, Event
from arrayqueues import ArrayQueue
from ipc_tools import ModifiableRingBuffer
from mp_display import CameraWidget
from mp_msg_relay import MessageRelay
from camera_tools import XimeaCamera
from functools import partial
from mp_cam_process import CameraProcess
from mp_save_process import SaveProcess
from DrawMasks import MaskManager
from stimulation import StimManager
from LED import LEDD1B
from metadata import Metadata
import numpy as np
from PyQt5.QtWidgets import QApplication


if __name__ == "__main__":

    height = 488
    width = 648

    front_pipe_cam, back_pipe_cam = Pipe()
    front_pipe_save, back_pipe_save = Pipe()
    front_pipe_gui, back_pipe_gui = Pipe()

    start_event = Event()
    terminate_event = Event()

    display_buffer = ArrayQueue(200)
    save_buffer = ArrayQueue(200)

    # create empty structured array as sentinel 
    empty_img = np.zeros((height, width), dtype=np.uint8)
    sentinel = np.array((0, 0, empty_img),
                        dtype = np.dtype([
                            ('index', int), 
                            ('timestamp', np.float32),
                            ('image', empty_img.dtype, empty_img.shape)
                            ]))

    camera_constructor = partial(XimeaCamera, dev_id=0)

    camera_process = CameraProcess(back_pipe_cam=back_pipe_cam,
                                   camera_constructor=camera_constructor,
                                   display_buffer=display_buffer,
                                   save_buffer=save_buffer,
                                   start_event=start_event,
                                   terminate_event=terminate_event)
    
    relay_process = MessageRelay(back_pipe_gui=back_pipe_gui,
                                 front_pipe_cam=front_pipe_cam,
                                 front_pipe_save=front_pipe_save,
                                 start_event=start_event,
                                 terminate_event=terminate_event)
    
    save_process = SaveProcess(back_pipe_save=back_pipe_save,
                               save_buffer=save_buffer,
                               start_event=start_event,
                               terminate_event=terminate_event)

    camera_process.start()
    relay_process.start()
    save_process.start()

    app = QApplication(sys.argv)
    
    camera_widget = CameraWidget(front_pipe_gui=front_pipe_gui,
                                 display_buffer=display_buffer,
                                 save_buffer=save_buffer,
                                 sentinel_array=sentinel)
    
    stim_manager = StimManager()
    metadata = Metadata()

    # Connect signals and slots
    camera_widget.terminate_pressed.connect(stim_manager.stop)
    stim_manager.stim_number_set.connect(camera_widget.set_stim_number)
    stim_manager.trial_index_set.connect(camera_widget.set_trial_index)
    stim_manager.trial_started.connect(camera_widget.start_recording)
    stim_manager.trial_ended.connect(camera_widget.stop_recording)

    stim_manager.launch_metadata.connect(metadata.initialise_widget)

    camera_widget.show()

    app.exec()

    camera_process.join()
    relay_process.join()
    save_process.join()

