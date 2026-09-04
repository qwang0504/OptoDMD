from multiprocessing import Process, Pipe, Queue, connection, Event
import time
from queue import Empty
from arrayqueues import ArrayQueue
import zmq
from PyQt5.QtCore import QObject, pyqtSignal
# from ipc_tools import RingBuffer, Logger, ModifiableRingBuffer


class MessageRelay(Process):
    def __init__(self, 
                 back_pipe_gui: connection.Connection,
                 front_pipe_cam: connection.Connection,
                 front_pipe_save: connection.Connection,
                #  front_pipe_zmq: connection.Connection,
                 start_event,
                 terminate_event,
                 *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        self.back_pipe_gui = back_pipe_gui
        self.front_pipe_cam = front_pipe_cam
        self.front_pipe_save = front_pipe_save
        # self.front_pipe_zmq = front_pipe_zmq

        self.start_event = start_event
        self.terminate_event = terminate_event

        self.camera_process = None
        self.active = True

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        while self.active:
            # if self.front_pipe_zmq.poll(0):
            #     trigger = self.front_pipe_zmq.recv()
            #     print('trigger received by MessageRelay')

            msg = self.back_pipe_gui.recv()
            # print(f"Process: {self.name} received {msg}")
            
            if msg == 'start_acquisition': 
                self.front_pipe_cam.send('display')
                self.start_event.set()

            elif msg == 'stop_acquisition':
                self.start_event.clear()

            elif msg == 'start_recording':
                save_params = self.back_pipe_gui.recv()
                # print(f'save params from MessageRelay: {save_params}')
                self.front_pipe_save.send(save_params)
                self.front_pipe_cam.send(save_params)
                self.front_pipe_cam.send('save')
                self.start_event.set()

            elif msg == 'stop_recording':
                self.start_event.clear()                

            elif msg == 'terminate':
                self.terminate_event.set()
                self.front_pipe_cam.send('terminate')
                self.front_pipe_save.send('terminate')
                # self.start_event.set()
                # self.camera_process.join()
                self.active = False

            elif msg == 'init_params':
                init_params = self.front_pipe_cam.recv()
                self.back_pipe_gui.send(init_params)

            elif isinstance(msg, dict):
                self.front_pipe_cam.send(msg)
                updated_cam_params = self.front_pipe_cam.recv()
                # print(f"Process: {self.name} received {updated_cam_params}")
                if isinstance(updated_cam_params, dict):
                    self.back_pipe_gui.send(updated_cam_params)

        print('MessageRelay finished, exiting')



class ZMQ_signal(QObject):
    triggered = pyqtSignal()



class ZMQ_listener(Process):
    def __init__(self,
                 protocol: str,
                 host: str,
                 port: int,
                 back_pipe_zmq: connection.Connection,
                 timeout = None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.address = protocol + host + ":" + str(port)
        self.timeout = timeout
        self.signal = ZMQ_signal()

        self.active = True

    def setup(self):
        self.contex = zmq.Context.instance()
        self.socket = self.contex.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.socket.connect(self.address)
        print('Waiting for trigger...')

    def check(self):
        try:
            #timeout = 0, non-blocking check 
            if self.socket.poll(0): 
                ret = self.socket.recv()
                if ret:
                    print("trigger received")
                    self.signal.triggered.emit()
        except zmq.error.ZMQError:
            pass

    def check_blocking(self):
        try:
            if self.socket.poll(-1):
                ret = self.socket.recv()
                if ret:
                    print('trigger received')
                    self.signal.triggered.emit()
        
        except zmq.error.ZMQError:
            pass

    def run(self):
        print(f"Process: {self.name}, ID: {self.pid} is starting...")
        self.setup()
        while self.active:
            if self.timeout: 
                self.check_blocking()
            else: 
                self.check()

        print('ZMQ_listener finished, exiting')





        # self.init_videowriter()
        # print(f"Process: {self.name}, ID: {self.pid} is starting...")
        # # previous_qsize = -1
        # fd = open('sink_frames_AQ_200.txt', 'w')
        # # winmm = ctypes.WinDLL('winmm.dll')
        # # winmm.timeBeginPeriod(1)
        # while self.active:
        #     frame = self.buffer.get() #blocking
        #     if frame['image'].sum() > 0:
        #         # print(f"got frame number {frame['index']}")
        #         self.video_writer.write_frame(frame['image'])
        #         fd.write(f"{frame['index']}, {frame['timestamp']}\n")
        #         # current_qsize = self.buffer.qsize()
        #         # if current_qsize != previous_qsize:
        #         #     print(f"Sink buffer queue size: {self.buffer.qsize()}")
        #         #     previous_qsize = current_qsize
        #     else:
        #         fd.close()
        #         self.video_writer.close()
        #         self.active = False
        #     # winmm.timeEndPeriod(1)
        #     # break 

       


# if __name__ == "__main__":

#     width = 648
#     height = 488

#     # cam = camera_constructor()
#     # cam.start_acquisition()
#     # cam.set_exposure(1000)
#     # cam.set_framerate(200)
#     # t_prev = time.perf_counter()
#     # timestamp_prev = 0
#     # for i in range(100):
#     #     frame = cam.get_frame()
#     #     mod_buffer.put(frame)
#     #     t = time.perf_counter()
#     #     print(frame['index'], 1/(frame['timestamp']-timestamp_prev), 1/(t-t_prev))
#     #     t_prev = t
#     #     timestamp_prev = frame['timestamp']


#     empty_img = np.zeros((height, width), dtype=np.uint8)
#     sentinel = np.array((0, 0, empty_img),
#                         dtype = np.dtype([
#                             ('index', int), 
#                             ('timestamp', np.float32),
#                             ('image', empty_img.dtype, empty_img.shape)
#                             ]))

#     camera_constructor = partial(XimeaCamera, dev_id=0)
    
#     buffer = ArrayQueue(100)

#     # buffer = ModifiableRingBuffer(num_bytes=(width*height*500), 
#     #                               t_refresh=1e-3)

#     front_pipe, back_pipe = Pipe()
#     start_event = Event()
#     terminate_event = Event()

#     message_process = MessageRelay(back_pipe_gui=back_pipe,
#                                    start_event=start_event,
#                                    terminate_event=terminate_event,
#                                    camera_constructor=camera_constructor,
#                                    buffer=buffer,
#                                    sentinel=sentinel)
    

#     # winmm = ctypes.WinDLL('winmm.dll')
#     # winmm.timeBeginPeriod(1)

#     sink = SaveProcess(buffer=buffer)

#     message_process.start()
#     sink.start()

#     time.sleep(5)

#     front_pipe.send('start')
#     # time.sleep(5)

#     time.sleep(30)
#     front_pipe.send('stop')
#     time.sleep(2)
#     front_pipe.send('terminate')

#     message_process.join()
#     sink.join()

#     # winmm.timeEndPeriod(1)
