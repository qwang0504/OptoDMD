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
import json
from daq import LabJackU3LV_hl
from LED import LEDWidget, LEDD1B
from DMD import DMD
from DrawMasks import DrawPolyMask, DrawPolyMaskOpto, DrawPolyMaskOptoDMD
from Microscope import ImageSender, ScanImage
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThreadPool

# TODO: check arrayqueue length
# TODO: PWM duty cycle not precise
# TODO: termination methods
# TODO: close sockets cleanly
# TODO: implement "reverse" PWM for PMT gating

if __name__ == "__main__":

    height = 488
    width = 648

    PROTOCOL = "tcp://"
    HOST = "localhost"
    SI_FRAMES_PORT = 5002
    SI_TRIGGER_PORT = 6002

    # dmd settings
    SCREEN_DMD = 2
    # main screen: 0, right vertical screen: 1, DMD: 2
    DMD_HEIGHT = 1140
    DMD_WIDTH = 912

    # labjack settingss
    PWM_CHANNEL = 6
    PMT_GATING_CHANNEL = 2
    
    # calibration file
    transformations = np.tile(np.eye(3), (3,3,1,1))
    try:
        with open('calibration_3x/calibration.json', 'r') as f:
            calibration = json.load(f)

        # 0: cam, 1: dmd, 2: twop
        transformations[0,1] = np.asarray(calibration["cam_to_dmd"])
        transformations[0,2] = np.asarray(calibration["cam_to_twop"])
        transformations[1,0] = np.asarray(calibration["dmd_to_cam"])
        transformations[1,2] = np.asarray(calibration["dmd_to_twop"])
        transformations[2,0] = np.asarray(calibration["twop_to_cam"])
        transformations[2,1] = np.asarray(calibration["twop_to_dmd"])
    except:
        print("calibration couldn't be loaded, defaulting to identity")

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

    # Communication with ScanImage
    scan_image = ScanImage(PROTOCOL, HOST, SI_FRAMES_PORT)
    twop_sender = ImageSender(scan_image)
    thread_pool = QThreadPool()
    thread_pool.start(twop_sender)

    # Control LEDs
    daio = LabJackU3LV_hl()
    led = LEDD1B(daio, pwm_channel=PWM_CHANNEL, name = "475 nm") 
    led_widget = LEDWidget(led_drivers=[led])
    led_widget.show()

    # Control DMD
    dmd_widget = DMD(screen_num=SCREEN_DMD)

    cam_drawer = DrawPolyMask(np.zeros((512,512)))
    dmd_drawer = DrawPolyMask(np.zeros((DMD_HEIGHT,DMD_WIDTH)))
    twop_drawer = DrawPolyMask(np.zeros((512,512)))

    cam_mask = DrawPolyMaskOpto(cam_drawer)
    dmd_mask = DrawPolyMaskOptoDMD(dmd_drawer)
    twop_mask = DrawPolyMaskOpto(twop_drawer)

    masks = MaskManager([cam_mask, dmd_mask, twop_mask], ["Camera", "DMD", "Two Photon"], transformations)
    masks.show()

    stim_manager = StimManager(mask_manager=masks, led_driver=led)
    stim_manager.show()

    
    camera_widget = CameraWidget(front_pipe_gui=front_pipe_gui,
                                 display_buffer=display_buffer,
                                 save_buffer=save_buffer,
                                 sentinel_array=sentinel,
                                 protocol=PROTOCOL,
                                 host=HOST,
                                 port=SI_TRIGGER_PORT)

    # Connect signals and slots
    twop_sender.scan_image.image_ready.connect(twop_mask.set_image)
    dmd_mask.DMD_update.connect(dmd_widget.update_image)
    masks.mask_expose.connect(dmd_mask.expose)
    stim_manager.mask_expose.connect(dmd_mask.expose)
    masks.clear_dmd.connect(dmd_mask.clear)
    camera_widget.fish_folder_generated.connect(stim_manager.set_fish_folder)
    # camera_widget.terminate_pressed.connect(stim_manager.stop)
    camera_widget.zmq_trigger.connect(stim_manager.start)
    # stim_manager.stim_started.connect(twop_sender.pause)
    stim_manager.stim_number_set.connect(camera_widget.set_stim_number)
    stim_manager.trial_index_set.connect(camera_widget.set_trial_index)
    stim_manager.trial_started.connect(camera_widget.start_recording)
    stim_manager.trial_ended.connect(camera_widget.stop_recording)

    camera_widget.show()

    app.exec()

    twop_sender.stop()

    camera_process.join()
    relay_process.join()
    save_process.join()