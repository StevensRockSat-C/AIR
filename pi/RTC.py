'''
An implementation of the DS3231 RTC for T+ caculation
'''

import time
from abc import ABC, abstractmethod

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

try:
    import adafruit_ds3231
except (ImportError, ModuleNotFoundError) as e:
    adafruit_ds3231 = None

class RTC(ABC):
    """
    Abstract base class for RTC sensors.
    """
    
    @abstractmethod
    def isReady(self) -> bool:
        pass
    
    @abstractmethod
    def getT0(self) -> int:
        pass
    
    @abstractmethod
    def getT0MS(self) -> int:
        pass
    
    @abstractmethod
    def getTPlus(self) -> int:
        pass
    
    @abstractmethod
    def getTPlusMS(self) -> int:
        pass
    
    @abstractmethod
    def setEstT0(self, ref: int) -> int:
        pass

class RTCWrappedSensor(RTC):
    
    def __init__(self, i2c):
        """
        A wrapper for the DS3231 RTC for T0 tracking.
        TODO: Currently built for launch at T-60. Must be re-written for proper launch!

        Parameters
        ----------
        i2c : ExtendedI2C
            i2c bus.

        """
        self.ready = False
        
        try:
            self.ref = round(time.time()*1000) # This is only used if the RTC can't be found
            self.ds3231 = adafruit_ds3231.DS3231(i2c)
            self.rtcTime = self.ds3231.datetime
            self.now = round(time.time()*1000) # Get a fresh reference time
            self.t0 = self.now - (((self.rtcTime.tm_min * 60) + self.rtcTime.tm_sec) * 1000) # The oscillator should take an average of 2s to start and calibrate, from the datasheet. However, it seems it accounts for this interenally, so we WILL NOT add the 2 seconds ourselves.
            self.ready = True
        except:
            print("No RTC is on the i2c line?!")
            
    def setEstT0(self, ref):
        """
        Set the estimated T0 time if the RTC can't be found.
        
        ref:    Estimated T0 in MS
        
        Returns
        -------
        Difference of new and old t0
        """
        prior_t0 = self.t0
        self.ref = ref
        self.t0 = ref
        return self.t0 - prior_t0
            
    def isReady(self):
        """Query whether the sensor is ready."""
        return self.ready
        
    def getT0(self):
        """
        Retrieve the internal time of t0 in seconds.
        
        AKA, what the DEVICE's date and time was at t0
        """
        if not self.ready:
            return round(self.ref / 1000)
        return round(self.t0 / 1000)
        
    def getT0MS(self):
        """
        Retrieve the internal time of t0 in ms.
        
        AKA, what the DEVICE's date and time was at t0
        """
        if not self.ready:
            return self.ref
        return self.t0

    def getTPlus(self):
        """
        Get the time since launch in seconds.
        
        Returns approximate time if not ready
        """
        if not self.ready:
            return round(time.time() - round(self.ref / 1000))
        return round(time.time() - round(self.t0 / 1000))

    def getTPlusMS(self):
        """
        Get the time since launch in milliseconds.
        
        Returns approximate time if not ready
        """
        if not self.ready:
            return round(time.time()*1000) - self.ref
        return round(time.time()*1000) - self.t0
    
class RTCFile(RTC):
    """
    Simulates an RTC for testing purposes.
    """
    
    def __init__(self, start_time_ms: int):
        self.ref = start_time_ms
        self.t0 = start_time_ms
        self.ready = True
    
    def isReady(self) -> bool:
        return self.ready
    
    def getT0(self) -> int:
        return round(self.t0 / 1000)
    
    def getT0MS(self) -> int:
        return self.t0
    
    def getTPlus(self) -> int:
        return round(time.time() - round(self.t0 / 1000))
    
    def getTPlusMS(self) -> int:
        return round(time.time() * 1000) - self.t0
    
    def setEstT0(self, ref: int) -> int:
        prior_t0 = self.t0
        self.t0 = ref
        return self.t0 - prior_t0