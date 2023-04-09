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
        Sample collections
        A protocol for handling the Secondary Pi
        A protocol for handling the Jetson
        A protocol for if pressures are not right

"""


# SETTINGS
PORT = "/dev/serial0"       # Serial Port
BAUD_RATE = 115200          # Serial baud rate

DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live

MAIN_VALVE = 13             # Parker 11/25/26 Main Valve control pin
BLEED_VALVE = 15            # ASCO Bleed Valve control pin
VALVE_1 = 19                # First tank control pin
VALVE_2 = 21                # Second tank control pin
VALVE_3 = 23                # Third tank control pin


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
import multiprint

mprint = MultiPrinter()

output_log = open(str(time.time()) + '_output.txt', 'x') # Our main output file will be named as $time_output.txt
output_pressures = open(str(time.time()) + '_pressures.csv', 'x') # Our main output file will be named as $time_output.txt

mprint.p("time & sys imported, files open. Time: " + str(timeMS()) + " ms\tFirst script on: " + str(FIRST_ON_MS) + " ms", output_log)
mprint.w("Time (ms),T+ (ms),Pressure Canister (hPa),Pressure Valve 1 (hpa),Pressure Valve 2 (hPa),Pressure Valve 3 (hpa)", output_pressures) # Set up our CSV headers

# Communications
import serial
import RPi.GPIO as GPIO

# Sensors
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_ds3231
import adafruit_tca9548a
import adafruit_mprls
import RTC  # Our home-built Realtime Clock lib

# Init i2c
i2c = I2C(1)    # Use i2c bus #1
time.sleep(2)   # Needed to ensure i2c is properly initialized
mprint.p("i2c initialized. Time: " + str(timeMS()) + " ms", output_log)

# Init GPIO
#   We do this before connecting to i2c devices because we want to make sure our valves are closed!
GPIO.setmode(GPIO.BOARD)    # Use the board's physical pin numbers

GPIO.setup(MAIN_VALVE, GPIO.OUT)
GPIO.setup(BLEED_VALVE, GPIO.OUT)
GPIO.setup(VALVE_1, GPIO.OUT)
GPIO.setup(VALVE_2, GPIO.OUT)
GPIO.setup(VALVE_3, GPIO.OUT)

# Pull all the gates low
GPIO.output(MAIN_VALVE, GPIO.LOW)
GPIO.output(BLEED_VALVE, GPIO.LOW)
GPIO.output(VALVE_1, GPIO.LOW)
GPIO.output(VALVE_2, GPIO.LOW)
GPIO.output(VALVE_3, GPIO.LOW)
mprint.p("Valves pulled LOW. Time: " + str(timeMS()) + " ms", output_log)

# Connect to i2c devices
multiplex = adafruit_tca9548a.TCA9548A(i2c)
mprint.p("Multiplexer connected. Time: " + str(timeMS()) + " ms", output_log)

mprls_canister = adafruit_mprls.MPRLS(multiplex[0], psi_min=0, psi_max=25)
mprls_tank_1 = adafruit_mprls.MPRLS(multiplex[1], psi_min=0, psi_max=25)
mprls_tank_2 = adafruit_mprls.MPRLS(multiplex[2], psi_min=0, psi_max=25)
mprls_tank_3 = adafruit_mprls.MPRLS(multiplex[3], psi_min=0, psi_max=25)
mprint.p("MPRLS' connected. Time: " + str(timeMS()) + " ms", output_log)

rtc = RTC(i2c)

# Establish our T0
time_try_rtc = timeMS()
while (rtc.isReady() == False) && (time_try_rtc - 3000 < timeMS()): # Wait for up to 3 seconds for RTC.
    pass

if rtc.isReady():

    TIME_LAUNCH_MS = rtc.getT0MS()
    
    mprint.pform("Got RTC after " + str(timeMS() - time_try_rtc) + " ms\tT0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)
    
else:   # Bruh. No RTC on the line. Guess that's it.

    TIME_LAUNCH_MS = FIRST_ON_MS - DEFAULT_BOOT_TIME   # We'll assume 35 seconds in, based on lab testing.
    rtc.setRef(TIME_LAUNCH_MS)
    
    mprint.p("NO RTC!! Going to assume it's 35 seconds past launch", output_log)
    mprint.pform("T0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)

# Get our first pressure readings
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

logPressures()

# Open the serial port to the Secondary Pi
PI_ser = serial.Serial(PORT, BAUD_RATE)

# Send the string "Hello world"
PI_ser.write(b"Hello world")


# FUN BITS HERE

"""
    I believe there's a way better method of scheduling events. This is just a placeholder!
"""
# FIRST SAMPLE AT 40.305s
while rtc.getPlusMS() < 40305:
    pass
mprint.pform("MAIN_VALVE and BLEED_VALVE pulled HIGH", rtc.getTPlusMS(), output_log)
GPIO.output(MAIN_VALVE, GPIO.HIGH)
GPIO.output(BLEED_VALVE, GPIO.HIGH)



# Close the serial port
PI_ser.close()

# Close the output files
output_log.close()
output_pressures.close()

# Shutdown the system (No going back!)
os.system("shutdown now")