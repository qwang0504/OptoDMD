import numpy as np
from stimulation import StimManager
from LED import LEDDriver

class Metadata:
    def __init__(
            self, 
            stim_manager: StimManager, 
            *args, 
            **kwargs
            ):
        self.stim_manager = stim_manager 
    
    
    # def generate_id(self):
        #date, fish number

    #genotype, age, condition
    #mask exposed, pulse start, pulse end, duration 
    #fps, exposure, gain, encoding 

    #write json with id

    



