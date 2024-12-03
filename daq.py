# for Arduino, you can use pyFirmata 
# https://pyfirmata.readthedocs.io/en/latest/ 

# LabJack Documentation can be found here:
# https://github.com/labjack/LabJackPython/blob/master/Examples/workingWithModbus.py
# https://labjack.com/pages/support?doc=%2Fsoftware-driver%2Fdirect-modbus-tcp%2Fud-modbus-old-deprecated%2F
# https://files.labjack.com/datasheets/LabJack-U3-Datasheet.pdf

# TODO National Instruments ?

import u3
from pyfirmata import Arduino
from typing import Protocol
import time

class DigitalAnalogIO(Protocol):

    def digitalRead(self, channel: int) -> float:
        ...

    def digitalWrite(self, channel: int, val: bool):
        ...

    def pwm(self, channel: int, duty_cycle: float, frequency: float) -> None:
        ...
        
    def analogRead(self, channel: int) -> float:
        ...

    def analogWrite(self, channel: int, val: float) -> None:
        ...

    def close(self) -> None:
        ...

# NOTE can't use arduino to control PWM freq
class myArduino:

    # PWM frequency is around 490Hz on most pins, 
    # and 980Hz on pin 5 and 6

    def __init__(self, board_id: str) -> None:
        self.device = Arduino(board_id)

    def digitalRead(self, channel: int) -> float:
        pin = self.device.get_pin(f'd:{channel}:i')       
        val = pin.read()  
        self.device.taken['digital'][channel] = False
        return val

    def digitalWrite(self, channel: int, val: bool):
        pin = self.device.get_pin(f'd:{channel}:o')
        pin.write(val)
        self.device.taken['digital'][channel] = False

    def pwm(self, channel: int, duty_cycle: float, frequency: float) -> None:
        # frequency is ignored
        pin = self.device.get_pin(f'd:{channel}:p')
        pin.write(duty_cycle)
        self.device.taken['digital'][channel] = False
        
    def analogRead(self, channel: int) -> float:
        pin = self.device.get_pin(f'a:{channel}:i')
        val = pin.read()
        self.device.taken['analog'][channel] = False
        return val

    def analogWrite(self, channel: int, val: float) -> None:
        # Can not do analog write, the arduino does not have a DAC
        print("""The arduino does not have a DAC, no analog writing. 
              Consider hooking a capacitor on a PWM output instead""")

    def close(self) -> None:
        self.device.exit()

class LabJackU3LV:
    '''
    Use LabJack to read and write from a single pin at a time.
    Supports Analog input (FIOs) and output (DACs), digital
    input and output (FIOs), as well as PWM (FIOs). 

    The U3 has 2 timers (Timer0-Timer1) and 2 counters (Counter0-Counter1). 
    When any of these timers or counters are enabled, they take over an
    FIO/EIO line in sequence (Timer0, Timer1, Counter0, then Counter1), 
    starting with FIO0+TimerCounterPinOffset. 
    '''
  
    # Analog outputs (they can also do input, but I decided to ignore that)
    # 10 bit resolution
    # [0.04V, 4.95V]
    DAC0 = 5000
    DAC1 = 5002

    # Digital Input/Output
    # Registers correspond to DIO STATES (i.e. high=1, low=0)
    DIO0 = 6000
    DIO1 = 6001
    DIO2 = 6002
    DIO3 = 6003
    DIO4 = 6004
    DIO5 = 6005
    DIO6 = 6006
    DIO7 = 6007

    # 12 bits resolution
    # single-ended: [0V, 2.44V]
    # differential: [-2.44V, 2.44V] 
    # special: [0V, 3.6V] 
    AIN0 = 0
    AIN1 = 2
    AIN2 = 4
    AIN3 = 6
    AIN4 = 8
    AIN5 = 10
    AIN6 = 12
    AIN7 = 14

    # configure FIO as analog or digital
    # bitmask: 1=Analog, 0=digital
    FIO_ANALOG = 50590

    channels = {
        'AnalogInput': [AIN0,AIN1,AIN2,AIN3,AIN4,AIN5,AIN6,AIN7],
        'AnalogOutput': [DAC0,DAC1],
        'DigitalInputOutput': [DIO0,DIO1,DIO2,DIO3,DIO4,DIO5,DIO6,DIO7]
    }

    TIMER_CLOCK_BASE = 7000
    TIMER_CLOCK_DIVISOR = 7002
    NUM_TIMER_ENABLED = 50501
    TIMER_PIN_OFFSET = 50500
    TIMER_CONFIG = 7100
    TIMER_MODE_16BIT = 0
    TIMER_MODE_8BIT = 1

    CLOCK: int = 48 # I'm only using the 48MHz clock with divisors enabled 
        
    def __init__(self) -> None:
        
        self.device = u3.U3()

    def analogWrite(self, channel: int, val: float) -> None: 
        self.device.writeRegister(self.NUM_TIMER_ENABLED, 0)
        self.device.writeRegister(self.channels['AnalogOutput'][channel], val)

    def analogRead(self, channel: int) -> float:
        self.device.writeRegister(self.NUM_TIMER_ENABLED, 0)
        self.device.writeRegister(self.FIO_ANALOG, channel**2) # set channel as analog
        return self.device.readRegister(self.channels['AnalogInput'][channel])
    
    def digitalWrite(self, channel: int, val: bool):
        self.device.writeRegister(self.NUM_TIMER_ENABLED, 0) #ensure no timer enabled first?
        self.device.writeRegister(self.FIO_ANALOG, 0) # set channel as digital
        #writing state of channel --> defaults direction to output! 
        self.device.writeRegister(self.channels['DigitalInputOutput'][channel], val) 

    def digitalRead(self, channel: int) -> float:
        self.device.writeRegister(self.NUM_TIMER_ENABLED, 0)
        self.device.writeRegister(self.FIO_ANALOG, 0) # set channel as digital
        return self.device.readRegister(self.channels['DigitalInputOutput'][channel])
   
    def pwm(self, channel: int = 4, duty_cycle: float = 0.5, frequency: float = 732.42) -> None:

        if not (0 <= duty_cycle <= 1):
            raise ValueError('duty_cycle should be between 0 and 1')

        if frequency > 187_500:
            raise ValueError('max frequency at 48MHz is 187_500 Hz')
        elif frequency < 2.861:
            raise ValueError('min frequency at 48MHz is 2.861 Hz')
         
        if frequency > 732.42:
            timer_mode = self.TIMER_MODE_8BIT
            div = 2**8
        else:
            timer_mode = self.TIMER_MODE_16BIT
            div = 2**16

        # make sure digital value is 0
        self.digitalWrite(channel,0)

        if duty_cycle == 0:
            # PWM can't fully turn off. Use digital write instead
            # and return
            return
        
        # divisor should be in the range 0-255, 0 corresponds to a divisor of 256
        timer_clock_divisor = int( (self.CLOCK * 1e6)/(frequency * div) )
        if timer_clock_divisor == 256: timer_clock_divisor = 0 
        
        # enable Timer0 
        self.device.writeRegister(self.NUM_TIMER_ENABLED, 1)

        # set the timer clock to 48 MHz with divisor (correspond to register value of 6)
        self.device.writeRegister(self.TIMER_CLOCK_BASE, 6)

        # set divisor
        self.device.writeRegister(self.TIMER_CLOCK_DIVISOR, timer_clock_divisor)

        # Pin offset (FIO) 
        self.device.writeRegister(self.TIMER_PIN_OFFSET, channel) 

        # 16 bit value for duty cycle
        value = int(65535*(1-duty_cycle))

        # Configure the timer for 16-bit PWM
        self.device.writeRegister(self.TIMER_CONFIG, [timer_mode, value]) 

    def close(self) -> None:
        self.device.close()


class LabJackU3LV_new:

    def __init__(self) -> None:
        self.device = u3.U3()
        self.clock_freq = 48

    def digitalRead(self, channel: int) -> int:
        self.device.configIO(NumberOfTimersEnabled=0)
        #configure analog / digital with bitmask 
        self.device.configIO(FIOAnalog=0) #all digital 
        return self.device.getFeedback(u3.BitStateRead(channel))[0] #output is a list [1] or [0]

    def digitalWrite(self, channel: int, state: bool): #high=1, low=0
        self.device.configIO(NumberOfTimersEnabled=0)
        #configure analog / digital with bitmask 
        self.device.configIO(FIOAnalog=0) #all digital 
        self.device.getFeedback(u3.BitStateWrite(channel, state)) #defaults all to output 

    def analogRead(self, channel: int) -> float:
        self.device.configIO(NumberOfTimersEnabled=0)        
        self.device.configIO(FIOAnalog=2**channel) #convert channel to analog 
        #check if this formula is right!! 
        return self.device.getAIN(channel) #output is a float

    def analogWrite(self, channel: int, val: float, bit: int):
        self.device.configIO(NumberOfTimersEnabled=0)
        if bit == 1: #8-bit = 1
            if channel==0:
                DAC_VALUE = self.device.voltageToDACBits(val, dacNumber = 0, is16Bits = False)
                self.device.getFeedback(u3.DAC0_8(Value=DAC_VALUE))
            else:
                DAC_VALUE = self.device.voltageToDACBits(val, dacNumber = 1, is16Bits = False)
                self.device.getFeedback(u3.DAC1_8(Value=DAC_VALUE))
        elif bit == 0: #16-bit = 0
            if channel==0:
                DAC_VALUE = self.device.voltageToDACBits(val, dacNumber = 0, is16Bits = True)
                self.device.getFeedback(u3.DAC0_16(Value=DAC_VALUE))
            else:
                DAC_VALUE = self.device.voltageToDACBits(val, dacNumber = 1, is16Bits = True)
                self.device.getFeedback(u3.DAC1_16(Value=DAC_VALUE))
        #DAC channels! 0 or 1 for DAC0 or DAC1, bits for 8-bit or 16-bits 
        # self.device.writeRegister(self.channels['AnalogOutput'][channel], val)

    def pwm(self, channel: int, duty_cycle: float, frequency: float) -> None:
        
        if not (0 <= duty_cycle <= 1):
            raise ValueError('duty_cycle should be between 0 and 1')

        if frequency > 187_500:
            raise ValueError('max frequency at 48MHz is 187_500 Hz')
        elif frequency < 2.861:
            raise ValueError('min frequency at 48MHz is 2.861 Hz')
         
        if frequency > 732.42:
            timer_mode = 1 #8-bit = mode 1
            div = 2**8
        else:
            timer_mode = 0 #16-bit = mode 0
            div = 2**16

        # make sure digital value is 0
        self.digitalWrite(channel,0)
        # why is this necessary? make sure that the channel isn't already sending a signal?

        if duty_cycle == 0:
            # PWM can't fully turn off. Use digital write instead
            # and return
            return
        
        # divisor should be in the range 0-255, 0 corresponds to a divisor of 256
        timer_clock_divisor = int( (self.clock_freq * 1e6)/(frequency * div) ) #48 MHz / (frequency * divisor)
        
        if timer_clock_divisor == 256: 
            timer_clock_divisor = 0 
        
        # enable Timer0, set pin offset
        self.device.configIO(NumberOfTimersEnabled=1, TimerCounterPinOffset=channel)

        # set the timer clock to 48 MHz with divisor (correspond to value of 6 with reference to section 2.9)
        self.device.configTimerClock(TimerClockBase=6, TimerClockDivisor=timer_clock_divisor)

        # 16-bit value for duty cycle
        value = int(65535*(1-duty_cycle))

        # Configure the timer for 16-bit PWM
        time_start_pwm = time.time()
        self.device.getFeedback(u3.TimerConfig(timer=0, TimerMode=timer_mode, Value=value))
        print('start_pwm: ', time_start_pwm)

    def close(self) -> None:
        self.device.close()

    

    #digital direction (1 or 0)
    #if output, high or low state (1 or 0)

# import u3
# import time
# import numpy as np
# d = u3.U3()
# d.configIO()
# d.configIO(FIOAnalog=0)

# # d.configIO(NumberOfTimersEnabled=0, TimerCounterPinOffset=5)

# d.configIO(NumberOfTimersEnabled=1, TimerCounterPinOffset=5)

# # d.configIO(FIOAnalog=15)
# d.configTimerClock(TimerClockBase=3, TimerClockDivisor=256)
# d.getFeedback(u3.TimerConfig(timer = 0, TimerMode = 1, Value = 40000))

# d.getFeedback(u3.BitStateRead(5))
# d.getFeedback(u3.BitStateWrite(5, 0))
# d.getFeedback(u3.Timer0Config(0, 40000))

# #Timer modes
# # 0 = 16-bit PWM
# # 1 = 8-bit PWM
# # refer to p. 24-25 / Section 2.9.1

# #values passed indicate %time spent LOW
# #48 MHz with divisors (ClockBase = 6)
# #16-bit range: 2.861 - 732.42
# #8-bit range: 732.422 - 187500


# duration = 10
# bits = []
# start = time.time()
# while time.time() < start + duration: 
#     bits.append(d.getFeedback(u3.BitStateRead(5))[0])

# sum([i==0 for i in bits ])/len(bits) 
# 40000/65536

# len(np.where(np.diff(bits) > 0)[0])/duration

# d.getFeedback(u3.DAC0_16(30000))


# DAC0_VALUE = d.voltageToDACBits(4, dacNumber = 0, is16Bits = False)
# d.getFeedback(u3.DAC0_8(DAC0_VALUE))
# #make AIN1 analog input 
# channel=1
# d.configIO(FIOAnalog=2**channel) 
# ain0bits = d.getFeedback(u3.AIN(1))

# d.getAIN(1)

# import matplotlib.pyplot as plt

# duration = 60
# bits = []
# start = time.time()
# while time.time() < start + duration: 
#     bits.append(d.getAIN(1))

# plt.plot(bits)
# plt.show()

# plt.close()