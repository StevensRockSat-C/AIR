'''
An implementation of the DS3231 RTC for T+ caculation
'''

import time
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_ds3231

class RTC:
    
    def __init__(self, i2c):
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
            self.ready = False
            
    def setRef(self, ref):
        """
        ref:    Estimated T0 in MS
        Set the estimated T0 time if the RTC can't be found
        """
        self.ref = ref
            
    def isReady(self):
        """
        Return whether the sensor is ready
        """
        return self.ready
        
    def getT0(self):
        """
        Returns the internal time of t0 in seconds
        AKA, what the DEVICE's date and time was at t0
        """
        if !self.ready:
            return round(self.ref / 1000)
        return round(self.t0 / 1000)
        
    def getT0MS(self):
        """
        Returns the internal time of t0 in ms
        AKA, what the DEVICE's date and time was at t0
        """
        if !self.ready:
            return self.ref
        return self.t0

    def getTPlus(self):
        """
        Get the time since launch in seconds
        Returns -1 if not ready
        """
        if !self.ready:
            return round(time.time() - round(self.ref / 1000))
        return round(time.time() - round(self.t0 / 1000))

    def getTPlusMS(self):
        """
        Get the time since launch in milliseconds
        Returns -1 if not ready
        """
        if !self.ready:
            return round(time.time()*1000) - self.ref
        return round(time.time()*1000) - self.t0