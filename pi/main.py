"""
    This is the script for the Main Raspberry Pi, written by Anthony Ford
    
    This does the following:
        Uses MultiPrint for filewriting
        Pulls the valves low at boot
        Connects to ALL i2c devices
        Gets RTC time
            Keeps track of T+
        Logs pressures

    This STILL NEEDS TO DO:
        Use the flowchart to build error handling
            A protocol for if pressures are not right
                or if otherwise bad things happening
        Sample collections
        A protocol for handling the Secondary Pi
        A protocol for handling the Jetson

"""

# Communications
import serial
import RPi.GPIO as GPIO

# SETTINGS
PORT = "/dev/serial0"       # Serial Port
BAUD_RATE = 115200          # Serial baud rate

DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live

GPIO_MODE = GPIO.BCM
VALVE_MAIN_PIN = 27         # Parker 11/25/26 Main Valve control pin
VALVE_BLEED_PIN = 22        # ASCO Bleed Valve control pin
VALVE_1_PIN = 10            # First tank control pin
VALVE_2_PIN = 9             # Second tank control pin
VALVE_3_PIN = 11            # Third tank control pin

"""
VALVE_MAIN_PIN = 13 (BOARD) -> 27 (BCM)
VALVE_BLEED_PIN = 15 (BOARD) -> 22 (BCM)
VALVE_1_PIN = 19 (BOARD) -> 10 (BCM)
VALVE_2_PIN = 21 (BOARD) -> 9 (BCM)
VALVE_3_PIN = 23 (BOARD) -> 11 (BCM)
"""

class Collection:

    """
        Everything related to a collection timing. All provided times are in ms
        
        up_start_time: The T+ that this collection should happen if sampling on the way up
        down_start_time: The T+ that this collection should happen if sampling on the way up
        up_duration: The time that the valves should remain open for the upwards collection
        down_duration: The time that the valves should remain open for downwards collection
    """
    
    def __init__(self, up_start_time, down_start_time, up_duration, down_duration, bleed_duration):
        self.up_start_time = up_start_time
        self.down_start_time = down_start_time
        self.up_duration = up_duration
        self.down_duration = down_duration
        self.bleed_duration = bleed_duration
        self.sampled = False
        self.sample_upwards = True  # Set to False if this tank needs to be sampled on the way down

class Valve:

    """
        Everything related to a valve
        
        pin: The BCM pin of the valve
    """
    
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(self.pin, GPIO.OUT) # Set the pin to the output
        
    """
        Pull the valve pin HIGH
    """
    def open(self):
        GPIO.output(self.pin, GPIO.HIGH)
        
    """
        Pull the valve pin LOW
    """
    def close(self):
        GPIO.output(self.pin, GPIO.LOW)

class Tank:

    """
        Everything related to a single tank
        
        valve: The Valve object
        collection: The sample collection object
    """
    
    def __init__(self, valve):
        self.valve = valve
        self.pressure = -1
        self.sampled = False
        self.dead = False           # Set to True if we believe this tank can't hold a sample, i.e. the pressure in the tank is 100 kPa
        
    def open(self):
        self.valve.open()
        
    def close(self):
        self.valve.close()

import time

def timeMS():
    """
    Returns system time to MS
    """
    return timeMS()

FIRST_ON_MS = timeMS() # Record the very first moment we are running the script
TIME_LAUNCH_MS = -1

# System control, like file writing
import sys
import os
from multiprint import MultiPrinter

mprint = MultiPrinter()

output_log = open(str(time.time()) + '_output.txt', 'x') # Our main output file will be named as $time_output.txt
output_pressures = open(str(time.time()) + '_pressures.csv', 'x') # Our main output file will be named as $time_output.txt

mprint.p("time & sys imported, files open. Time: " + str(timeMS()) + " ms\tFirst script on: " + str(FIRST_ON_MS) + " ms", output_log)
mprint.w("Time (ms),T+ (ms),Pressure Canister (hPa),Pressure Valve 1 (hpa),Pressure Valve 2 (hPa),Pressure Valve 3 (hpa)", output_pressures) # Set up our CSV headers

# Sensors
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_ds3231
import adafruit_tca9548a
import adafruit_mprls
import RTC  # Our home-built Realtime Clock lib

# Init GPIO
#   We do this before connecting to i2c devices because we want to make sure our valves are closed!
GPIO.setmode(GPIO_MODE)      # Use some made up BS numbers
#GPIO.setmode(GPIO.BOARD)    # Use the board's physical pin numbers

valve_main = Valve(VALVE_MAIN_PIN)
valve_bleed = Valve(VALVE_BLEED_PIN)
valve_1 = Valve(VALVE_1_PIN)
valve_2 = Valve(VALVE_2_PIN)
valve_3 = Valve(VALVE_3_PIN)

# Pull all the gates low
valve_main.close()
valve_bleed.close()
valve_1.close()
valve_2.close()
valve_3.close()
mprint.p("Valves pulled LOW. Time: " + str(timeMS()) + " ms", output_log)

# Init i2c
i2c = I2C(1)    # Use i2c bus #1
time.sleep(2)   # Needed to ensure i2c is properly initialized
mprint.p("i2c initialized. Time: " + str(timeMS()) + " ms", output_log)

# Connect to i2c devices
multiplex = False
try:
    multiplex = adafruit_tca9548a.TCA9548A(i2c)
    mprint.p("Multiplexer connected. Time: " + str(timeMS()) + " ms", output_log)
except:
    mprint.p("COULD NOT CONNECT TO MULTIPLEXER!! Time: " + str(timeMS()) + " ms", output_log)

mprls_canister = False
mprls_bleed = False
mprls_tank_1 = False
mprls_tank_2 = False
mprls_tank_3 = False

if multiplex != False:
    try: # Canister MPRLS
        mprls_canister = adafruit_mprls.MPRLS(multiplex[0], psi_min=0, psi_max=25)
    except:
        mprint.p("COULD NOT CONNECT TO CANISTER MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    try: # Bleed Tank MPRLS
        mprls_bleed = adafruit_mprls.MPRLS(multiplex[1], psi_min=0, psi_max=25)
    except:
        mprint.p("COULD NOT CONNECT TO BLEED MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    try: # Tank 1 MPRLS
        mprls_tank_1 = adafruit_mprls.MPRLS(multiplex[2], psi_min=0, psi_max=25)
    except:
        mprint.p("COULD NOT CONNECT TO TANK 1 MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    try: # Tank 2 MPRLS
        mprls_tank_2 = adafruit_mprls.MPRLS(multiplex[3], psi_min=0, psi_max=25)
    except:
        mprint.p("COULD NOT CONNECT TO TANK 2 MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    try: # Tank 3 MPRLS
        mprls_tank_3 = adafruit_mprls.MPRLS(multiplex[4], psi_min=0, psi_max=25)
    except:
        mprint.p("COULD NOT CONNECT TO TANK 3 MPRLS!! Time: " + str(timeMS()) + " ms", output_log)
    
    mprint.p("MPRLS' connected. Time: " + str(timeMS()) + " ms", output_log)
else:
    mprint.p("NOT CONNECTING TO THE MPRLS because there's no multiplexer on the line!!", output_log)

rtc = RTC(i2c)

# Establish our T0
time_try_rtc = timeMS()
while (rtc.isReady() == False) and (time_try_rtc - 3000 < timeMS()): # Wait for up to 3 seconds for RTC.
    pass

if rtc.isReady():

    TIME_LAUNCH_MS = rtc.getT0MS()
    
    mprint.pform("Got RTC after " + str(timeMS() - time_try_rtc) + " ms\tT0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)
    
else:   # Bruh. No RTC on the line. Guess that's it.

    TIME_LAUNCH_MS = FIRST_ON_MS - DEFAULT_BOOT_TIME   # We'll assume 35 seconds in, based on lab testing.
    rtc.setRef(TIME_LAUNCH_MS)
    
    mprint.p("NO RTC!! Going to assume it's 35 seconds past launch", output_log)
    mprint.pform("T0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)

# TODO: This needs to account for any MPRLSs that didn't get initialized!
def logPressures():
    """
    Get the pressures from every MPRLS and logs them to the CSV output
    Returns an array of time and pressures as follows:
        [
            System Time (ms),
            T+ (ms),
            Canister Pressure (hpa),
            Tank 1 Pressure (hpa),
            Tank 2 Pressure (hpa),
            Tank 3 Pressure (hpa)
        ]
    """
    pressures = [timeMS(), rtc.getTPlusMS(), mprls_canister.pressure, mprls_tank_1.pressure, mprls_tank_2.pressure, mprls_tank_3.pressure]
    mprint.p(str(pressures[0]) + "," + str(pressures[1]) + "," + str(pressures[2]) + "," + str(pressures[3]) + "," + str(pressures[4]) + "," + str(pressures[5]), output_pressures)
    return pressures

# Get our first pressure readings
logPressures()

# Open the serial port to the Secondary Pi
PI_ser = serial.Serial(PORT, BAUD_RATE)

# Send the string "Hello world"
PI_ser.write(b"Hello world")

# Setup our Tank objects
tank_1 = Tank(valve_1)
tank_2 = Tank(valve_2)
tank_3 = Tank(valve_3)
tank_bleed = Tank(valve_bleed)

# Setup our Colleciton objects
collection_1 = Collection(40305, 100, -1, -1, 95)
collection_2 = Collection(60000, 200, 290000, 200, 95)
collection_3 = Collection(80000, 300, 230000, 300, 95)


# FUN BITS HERE

"""
    There's a way better method of scheduling events. This is just a placeholder!
"""
# FIRST SAMPLE AT 40.305s
while rtc.getPlusMS() < collection_1.up_start_time:
    logPressures()
    time.sleep(0.1)
mprint.pform("VALVE_MAIN and VALVE_BLEED pulled HIGH", rtc.getTPlusMS(), output_log)
valve_main.open()
tank_bleed.open()
while rtc.getPlusMS() < 40400:
    logPressures()
    time.sleep(0.1)
tank_bleed.close()

# TODO: Probably have some sort of check with the pressure sensors to make sure we got a sample




# Close the GPIO setup
GPIO.cleanup()

# Close the serial port
PI_ser.close()

# Close the output files
output_log.close()
output_pressures.close()

# Shutdown the system (No going back!)
os.system("shutdown now")