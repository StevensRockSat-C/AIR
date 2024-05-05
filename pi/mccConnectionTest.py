from daqHatWrapper import WrapDAQHAT
import os
from multiprint import MultiPrinter
from adafruit_extended_bus import ExtendedI2C as I2C
from RTC import RTC
from time import sleep

i2c = I2C(1)  
mprint = MultiPrinter()
rtc = RTC(i2c)
output_log = open('_output.txt', 'w') # Our main output file will be named as ${time}_output.txt


daqhat = WrapDAQHAT(mprint, output_log)
timesTried=0
sleep(1)
while ((not daqhat.connected) and timesTried<5):
    daqhat = WrapDAQHAT(mprint, output_log)
    timesTried+=1
    print("tried", timesTried, " times.") 

mprint.pform("Attemping to read buffer data", rtc.getTPlusMS(), output_log)
overrun = daqhat.read_buffer_write_file(rtc.getT0MS())
