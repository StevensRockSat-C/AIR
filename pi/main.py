"""
This is the script for the Main Raspberry Pi, written by Anthony Ford.

This does the following:
    Uses MultiPrint for filewriting
    Pulls the valves low at boot
    Connects to ALL i2c devices
        Can handle any i2c device not connecting (in terms of not crashing)
    Gets RTC time
        Keeps track of T+
    Logs pressures
    Sample collections
    Use the flowchart to build error handling
        A protocol for if pressures are not right
            or if otherwise bad things happening
    Adjust procedures if an MRPLS cannot connect

This STILL NEEDS TO DO:
    CONTINUALLY log vibration data
"""

# Communications
from RPi import GPIO

class Collection:
    """
    Everything related to a collection timing. All provided times are in ms.
    
    Parameters
    ----------
    num: The indicie of this collection
    
    up_start_time: The T+ that this collection should happen if sampling on the way up
    down_start_time: The T+ that this collection should happen if sampling on the way up
    
    up_duration: The time that the valves should remain open for the upwards collection
    down_duration: The time that the valves should remain open for downwards collection
    bleed_duration: How long we should bleed the lines for before collecting this sample
    
    up_driving_pressure: The hPa we expect this tank to get on the way up
    down_driving_pressure: The hPa we expect this tank to get on the way down
    
    upwards_bleed: Whether this collection needs to be bled on the way up
    
    tank: The tank asociated with this collection period
    mprls: The MPRLS asociated with this collection period
    """
    
    def __init__(self, num,
                 up_start_time, down_start_time,
                 bleed_duration,
                 up_driving_pressure, down_driving_pressure,
                 upwards_bleed,
                 up_duration=100, down_duration=100,
                 tank = None,
                 mprls = None):
        self.num = str(num)
        self.up_start_time = up_start_time
        self.down_start_time = down_start_time
        self.up_duration = up_duration
        self.down_duration = down_duration
        self.bleed_duration = bleed_duration
        self.up_driving_pressure = up_driving_pressure
        self.down_driving_pressure = down_driving_pressure
        self.upwards_bleed = upwards_bleed
        self.tank = tank
        self.mprls = mprls
        self.sampled = False
        self.sample_upwards = True  # Set to False if this tank needs to be sampled on the way down
        self.sampled_count = 0      # The number of times we've tried to sample

# ---- SETTINGS ----
VERSION = "1.3.1"

DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live

GPIO_MODE = GPIO.BCM
VALVE_MAIN_PIN = 27         # Parker 11/25/26 Main Valve control pin
VALVE_BLEED_PIN = 22        # ASCO Bleed Valve control pin
VALVE_1_PIN = 24            # First tank control pin
VALVE_2_PIN = 25            # Second tank control pin
VALVE_3_PIN = 18            # Third tank control pin
GSWITCH_PIN = 23            # G-switch input pin
"""
VALVE_MAIN_PIN = 13 (BOARD) -> 27 (BCM)
VALVE_BLEED_PIN = 15 (BOARD) -> 22 (BCM)
VALVE_1_PIN = 18 (BOARD) -> 24 (BCM)
VALVE_2_PIN = 22 (BOARD) -> 25 (BCM)
VALVE_3_PIN = 12 (BOARD) -> 18 (BCM)
"""

# Setup our Colleciton objects. Numbers from SampleTiming.xlsx in the drive. All durations are going to be the minimum actuation time
collection_1 = Collection(num=1, up_start_time=40305, down_start_time=290000, bleed_duration=1, 
                          up_driving_pressure=1270.44, down_driving_pressure=998.20, upwards_bleed=False)
collection_2 = Collection(num=2, up_start_time=70000, down_start_time=255000, bleed_duration=5, 
                          up_driving_pressure=753.43, down_driving_pressure=545.52, upwards_bleed=True)
collection_3 = Collection(num=3, up_start_time=90000, down_start_time=230000, bleed_duration=36,  
                          up_driving_pressure=490.13, down_driving_pressure=329.96, upwards_bleed=True)

collections = [collection_1, collection_2, collection_3]



class Valve:
    """
    Everything related to a valve.
    
    pin: The BCM pin of the valve
    """
    
    def __init__(self, pin, name):
        self.pin = pin
        self.name = name
        GPIO.setup(self.pin, GPIO.OUT) # Set the pin to the output
        
    def open(self):
        """Pull the valve pin HIGH."""
        GPIO.output(self.pin, GPIO.HIGH)
        
    
    def close(self):
        """Pull the valve pin LOW."""
        GPIO.output(self.pin, GPIO.LOW)

class Tank:
    """
    Everything related to a single tank.
    
    valve: The Valve object
    collection: The sample collection object
    """
    
    def __init__(self, valve):
        self.valve = valve
        self.pressure = -1
        self.sampled = False
        self.dead = False   # Set to True if we believe this tank can't hold a sample, i.e. the pressure in the tank is 100 kPa
        
    def open(self):
        self.valve.open()
        
    def close(self):
        self.valve.close()


class WrapMPRLS:
    """
    Wrap the MPRLS library to prevent misreads.
    
    multiplexerLine: The multiplexed i2c line. If not specified, this object will become dormant
    """
    
    def __init__(self, multiplexerLine=False):
        self.cantConnect = False
        self.mprls = False
        
        if not multiplexerLine: # No multiplexer defined, therefore this is a blank object
            self.cantConnect = True
            return
        
        try:
            self.mprls = adafruit_mprls.MPRLS(multiplexerLine, psi_min=0, psi_max=25)
        except:
            self.cantConnect = True
        
    def _get_pressure(self):
        if self.cantConnect: return -1
        return self.mprls.pressure

    def _set_pressure(self, value):
        pass

    def _del_pressure(self):
        pass
        
    """
        Acts as a wrapper for the pressure property of the standard MPRLS
    """
    pressure = property(
        fget=_get_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The pressure of the MPRLS or -1 if we can't connect to it"
    )


class PressuresOBJ:
    """Gather pressure information nicely."""
    
    def __init__(self, time_MS, TPlus_MS,
                 canister_pressure, bleed_pressure, tank_1_pressure, tank_2_pressure, tank_3_pressure):
        self.time_MS = time_MS
        self.TPlus_MS = TPlus_MS
        self.canister_pressure = canister_pressure
        self.bleed_pressure = bleed_pressure
        self.tank_1_pressure = tank_1_pressure
        self.tank_2_pressure = tank_2_pressure
        self.tank_3_pressure = tank_3_pressure


import time

def timeMS():
    """Get system time to MS."""
    return round(time.time()*1000)

FIRST_ON_MS = timeMS() # Record the very first moment we are running the script
TIME_LAUNCH_MS = -1

# System control, like file writing
import os
from multiprint import MultiPrinter

mprint = MultiPrinter()

output_log = open(str(time.time()) + '_output.txt', 'x') # Our main output file will be named as ${time}_output.txt
output_pressures = open(str(time.time()) + '_pressures.csv', 'x') # Our pressure output file will be named as ${time}_pressures.csv

mprint.p("time & sys imported, files open. Time: " + str(timeMS()) + " ms\tFirst script on: " + str(FIRST_ON_MS) + " ms", output_log)
mprint.p("Version " + str(VERSION) + ". Time: " + str(timeMS()) + " ms", output_log)
mprint.w("Time (ms),T+ (ms),Pressure Canister (hPa),Pressure Bleed (hPa),Pressure Valve 1 (hPa),Pressure Valve 2 (hPa),Pressure Valve 3 (hPa)", output_pressures) # Set up our CSV headers

# Sensors
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_tca9548a
import adafruit_mprls
from daqHatWrapper import WrapDAQHAT
import threading # Threading the vibration data
from RTC import RTC  # Our home-built Realtime Clock lib

# Init GPIO
#   We do this before connecting to i2c devices because we want to make sure our valves are closed!
GPIO.setmode(GPIO_MODE)      # Use some made up BS numbers
#GPIO.setmode(GPIO.BOARD)    # Use the board's physical pin numbers

valve_main = Valve(VALVE_MAIN_PIN, "main")
valve_bleed = Valve(VALVE_BLEED_PIN, "bleed")
valve_1 = Valve(VALVE_1_PIN, "1")
valve_2 = Valve(VALVE_2_PIN, "2")
valve_3 = Valve(VALVE_3_PIN, "3")

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

# Create blank objects
mprls_canister = WrapMPRLS()
mprls_bleed = WrapMPRLS()
mprls_tank_1 = WrapMPRLS()
mprls_tank_2 = WrapMPRLS()
mprls_tank_3 = WrapMPRLS()

if multiplex != False:
    # Canister MPRLS
    mprls_canister = WrapMPRLS(multiplexerLine=multiplex[0])
    if mprls_canister.cantConnect:
        mprint.p("COULD NOT CONNECT TO CANISTER MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    # Bleed Tank MPRLS
    mprls_bleed = WrapMPRLS(multiplexerLine=multiplex[1])
    if mprls_bleed.cantConnect:
        mprint.p("COULD NOT CONNECT TO BLEED MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    # Tank 1 MPRLS
    mprls_tank_1 = WrapMPRLS(multiplexerLine=multiplex[2])
    if mprls_tank_1.cantConnect:
        mprint.p("COULD NOT CONNECT TO TANK 1 MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    # Tank 2 MPRLS
    mprls_tank_2 = WrapMPRLS(multiplexerLine=multiplex[3])
    if mprls_tank_2.cantConnect:
        mprint.p("COULD NOT CONNECT TO TANK 2 MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    # Tank 3 MPRLS
    mprls_tank_3 = WrapMPRLS(multiplexerLine=multiplex[4])
    if mprls_tank_3.cantConnect:
        mprint.p("COULD NOT CONNECT TO TANK 3 MPRLS!! Time: " + str(timeMS()) + " ms", output_log)
    
    mprint.p("MPRLS' connected. Time: " + str(timeMS()) + " ms", output_log)
else:
    mprint.p("NOT CONNECTING TO THE MPRLS because there's no multiplexer on the line!!", output_log)

# Connect to the RTC
rtc = RTC(i2c)

# Establish our T0
time_try_rtc = timeMS()
while (not rtc.isReady()) and (time_try_rtc + 3000 > timeMS()): # Wait for up to 3 seconds for RTC.
    pass

if rtc.isReady():

    TIME_LAUNCH_MS = rtc.getT0MS()
    
    mprint.pform("Got RTC after " + str(timeMS() - time_try_rtc) + " ms\tT0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)
    
else:   # Bruh. No RTC on the line. Guess that's it.

    TIME_LAUNCH_MS = FIRST_ON_MS - DEFAULT_BOOT_TIME + 60000 # We'll assume 35 seconds in, based on lab testing. Add 60 seconds from 1.SYS.1 Early Activation
    rtc.setRef(TIME_LAUNCH_MS)
    
    mprint.p("NO RTC!! Going to assume it's 35 seconds past T-60", output_log)
    mprint.pform("T0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)


# Initialize the daqHat and begin collecting data
daqhat = WrapDAQHAT(mprint, output_log)
def collectVibrationData():
    """
    Begin collecting vibration data via a thread.

    Returns
    -------
    None.

    """
    global stop_vibration_thread   # Called True at the end of the script
    if stop_vibration_thread: return

    threading.Timer(0.2, collectVibrationData).start() # Re-call the thread #shouldn't this be AFTER you read from the buffer?
    overrun = daqhat.read_buffer_write_file(rtc.getTPlusMS())
    if overrun: mprint.pform("Overrun on buffer!", rtc.getTPlusMS(), output_log)

# Start the data collection in a separate thread
stop_vibration_thread = False
vibration_collection_thread = threading.Thread(target=collectVibrationData)
vibration_collection_thread.daemon = True  # Set the thread as a daemon so it automatically stops when the main thread exits
vibration_collection_thread.start()

def logPressures():
    """
    Get the pressures from every MPRLS and logs them to the CSV output.
    
    Returns a Pressure object with the pressure and time info:
            System Time (ms),
            T+ (ms),
            Canister Pressure (hpa),
            Bleed Pressure (hpa),
            Tank 1 Pressure (hpa),
            Tank 2 Pressure (hpa),
            Tank 3 Pressure (hpa)
    """
    pressures = PressuresOBJ(timeMS(), rtc.getTPlusMS(), mprls_canister.pressure, mprls_bleed.pressure, mprls_tank_1.pressure, mprls_tank_2.pressure, mprls_tank_3.pressure)
    mprint.p(str(pressures.time_MS) + "," + str(pressures.TPlus_MS) + "," + str(pressures.canister_pressure) + "," + str(pressures.bleed_pressure) + "," + str(pressures.tank_1_pressure) + "," + str(pressures.tank_2_pressure) + "," + str(pressures.tank_3_pressure), output_pressures)
    return pressures

# Get our first pressure readings
logPressures()

def gswitch_callback(channel):
    """
    Handle the G-Switch input. This sets our reference T+0.

    Parameters
    ----------
    channel : int
        GPIO Pin.

    Returns
    -------
    None.

    """
    t0 = timeMS()
    GPIO.remove_event_detect(GSWITCH_PIN)
    difference = rtc.setRef(t0)
    mprint.pform("G-Switch input! New t0: " + str(t0) + " ms. Difference from RBF estimation: " + str(difference) + " ms", rtc.getTPlusMS(), output_log)
    
# Setup the G-Switch listener
GPIO.setup(GSWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(GSWITCH_PIN, GPIO.FALLING,
                      callback=gswitch_callback, bouncetime=10)

# Setup our Tank objects
tank_1 = Tank(valve_1)
tank_2 = Tank(valve_2)
tank_3 = Tank(valve_3)
tank_bleed = Tank(valve_bleed)

# Connect the Tanks and MPRLS to their respective collection periods
collection_1.tank = tank_1
collection_2.tank = tank_2
collection_3.tank = tank_3
collection_1.mprls = mprls_tank_1
collection_2.mprls = mprls_tank_2
collection_3.mprls = mprls_tank_3


# FUN BITS HERE

def equalizeTanks():
    """Asseses the pressures of the tanks and makes necessary adjustments."""

    mprint.pform("Checking the pressures in the tanks for equalization...", rtc.getTPlusMS(), output_log)
    
    pressures = logPressures()
    
    if (mprls_tank_3.cantConnect == True or mprls_tank_2.cantConnect == True) and mprls_tank_1.cantConnect == True: # Not enough pressure information to equalize the tanks
        mprint.pform("Can't connect to two or more of the MPRLS, so we will not attempt to equalize the tanks. Connections - MPRLS3: " + str(not mprls_tank_3.cantConnect) + " MPRLS2: " + str(not mprls_tank_2.cantConnect) + " MPRLS1: " + str(not mprls_tank_1.cantConnect), rtc.getTPlusMS(), output_log)
        return False
    
    if (pressures.tank_3_pressure > collection_3.up_driving_pressure * 0.9) and not tank_3.sampled:  # If the pressure in the 3rd tank is too big...
        mprint.pform("Pressure in Tank 3 is too large for collection! - " + str(pressures.tank_3_pressure) + " hPa", rtc.getTPlusMS(), output_log)
        
        if pressures.tank_3_pressure < 900: # If the tank is holding *some* sort of vacuum, just not a good one...
            mprint.pform("Pressure in Tank 3 is below atmospheric", rtc.getTPlusMS(), output_log)
            
            if not mprls_tank_1.cantConnect and (pressures.tank_3_pressure + pressures.tank_1_pressure) / 2 < collection_3.up_driving_pressure * 0.9: # Let's equalize tank 1 and tank 3
                mprint.pform("Pressure in Tank 3 can be equalized with Tank 1. Let's do that", rtc.getTPlusMS(), output_log)
                valve_1.open()
                valve_3.open()
                mprint.pform("VALVE_1 and VALVE_3 pulled HIGH", rtc.getTPlusMS(), output_log)
                time.sleep(0.1)
                valve_3.close()
                valve_1.close()
                mprint.pform("VALVE_1 and VALVE_3 pulled LOW", rtc.getTPlusMS(), output_log)
            elif not mprls_tank_2.cantConnect and (pressures.tank_3_pressure + pressures.tank_2_pressure) / 2 < collection_3.up_driving_pressure * 0.9:
                mprint.pform("Pressure in Tank 3 can be equalized with Tank 2. Let's do that", rtc.getTPlusMS(), output_log)
                valve_2.open()
                valve_3.open()
                mprint.pform("VALVE_2 and VALVE_3 pulled HIGH", rtc.getTPlusMS(), output_log)
                time.sleep(0.1)
                valve_3.close()
                valve_2.close()
                mprint.pform("VALVE_2 and VALVE_3 pulled LOW", rtc.getTPlusMS(), output_log)
            else:
                mprint.pform("Pressure in Tank 3 can't be equalized. We'll sample it on the way down", rtc.getTPlusMS(), output_log)
                collection_3.sample_upwards = False
        else: # Tank lost everything in the 5 days we waited. Mark it as dead
            mprint.pform("Pressure in Tank 3 is atmospheric. Marked it as dead", rtc.getTPlusMS(), output_log)
            tank_3.dead = True
            collection_3.sample_upwards = False
            
    if (pressures.tank_2_pressure > collection_2.up_driving_pressure * 0.9) and not tank_2.sampled:  # If the pressure in the 2nd tank is too big...
        mprint.pform("Pressure in Tank 2 is too large for collection! - " + str(pressures.tank_2_pressure) + " hPa", rtc.getTPlusMS(), output_log)
        
        if pressures.tank_2_pressure < 900: # If the tank is holding *some* sort of vacuum, just not a good one...
            mprint.pform("Pressure in Tank 2 is below atmospheric", rtc.getTPlusMS(), output_log)
            
            if not mprls_tank_1.cantConnect and (pressures.tank_2_pressure + pressures.tank_1_pressure) / 2 < collection_2.up_driving_pressure * 0.9: # Let's equalize tank 1 and tank 2
                mprint.pform("Pressure in Tank 2 can be equalized with Tank 1. Let's do that", rtc.getTPlusMS(), output_log)    
                valve_1.open()
                valve_2.open()
                mprint.pform("VALVE_1 and VALVE_2 pulled HIGH", rtc.getTPlusMS(), output_log)
                time.sleep(0.1)
                valve_2.close()
                valve_1.close()
                mprint.pform("VALVE_1 and VALVE_2 pulled LOW", rtc.getTPlusMS(), output_log)
            else: # Can't equalize the tank, so we'll grab this sample on the way down
                mprint.pform("Pressure in Tank 2 can't be equalized. We'll sample it on the way down", rtc.getTPlusMS(), output_log)
                collection_2.sample_upwards = False
        else: # Tank lost everything in the 5 days we waited. Mark it as dead
            mprint.pform("Pressure in Tank 2 is atmospheric. Marked it as dead", rtc.getTPlusMS(), output_log)
            tank_2.dead = True
            collection_2.sample_upwards = False
    
    return True
    
equalizeTanks()


"""
    Upwards sampling management
"""
for collection in collections:
    if collection.sample_upwards:
        while True:
            collection.sampled_count += 1
            mprint.pform("Waiting for sample collection " + collection.num + " at " + str(collection.up_start_time) + " ms. Try #" + str(collection.sampled_count), rtc.getTPlusMS(), output_log)
            while rtc.getTPlusMS() < collection.up_start_time:
                logPressures()
            
            if collection.upwards_bleed:
                mprint.pform("Checking bleed tank pressure for sample collection " + str(collection.num), rtc.getTPlusMS(), output_log)
                temp_bleed_pressure = mprls_bleed.pressure
                if mprls_bleed.cantConnect or temp_bleed_pressure > collection.up_driving_pressure: # There's no way in hell we're bleeding off this thing. 
                    mprint.pform("!! Sample collection " + str(collection.num) + 
                                 " requires a full bleed for a driving pressure of " + str(collection.up_driving_pressure) + 
                                 " hPa, but our bleed tank is at " + str(temp_bleed_pressure) + 
                                 " hPa. Thus, we'll opt to sample this on the way down!", rtc.getTPlusMS(), output_log)
                    collection.sample_upwards = False     # Mark this collection for sampling on the way down
                    break
                else:
                    mprint.pform("Sample collection " + str(collection.num) + " requires a full bleed for a driving pressure of " + str(collection.up_driving_pressure) + 
                                 " hPa, which is greater than the bleed tank pressure of " + str(temp_bleed_pressure) + " hPa.", rtc.getTPlusMS(), output_log)
                    
                mprint.pform("Beginning outside bleed for sample collection " + collection.num, rtc.getTPlusMS(), output_log)
                valve_main.open()
                mprint.pform("VALVE_MAIN pulled HIGH", rtc.getTPlusMS(), output_log)
                time.sleep(0.1)
                valve_main.close()
                mprint.pform("VALVE_MAIN pulled LOW", rtc.getTPlusMS(), output_log)
                
                mprint.pform("Beginning inside bleed for sample collection " + collection.num, rtc.getTPlusMS(), output_log)
                tank_bleed.open()
                mprint.pform("VALVE_BLEED pulled HIGH", rtc.getTPlusMS(), output_log)
                sample_bleed_starttime = rtc.getTPlusMS()
                while rtc.getTPlusMS() - sample_bleed_starttime < collection.bleed_duration + 50:    # +50ms, just to ensure we get everything out
                    logPressures()
                tank_bleed.close()
                mprint.pform("VALVE_BLEED pulled LOW", rtc.getTPlusMS(), output_log)
            
            mprint.pform("Beginning sampling for sample collection " + collection.num, rtc.getTPlusMS(), output_log)
            valve_main.open()
            collection.tank.valve.open()
            mprint.pform("VALVE_MAIN and VALVE_" + collection.tank.valve.name + " pulled HIGH", rtc.getTPlusMS(), output_log)
            sample_starttime = rtc.getTPlusMS()
            while rtc.getTPlusMS() - sample_starttime < collection.up_duration:
                logPressures()
            valve_main.close()
            collection.tank.valve.close()
            mprint.pform("VALVE_MAIN and VALVE_" + collection.tank.valve.name + " pulled LOW", rtc.getTPlusMS(), output_log)
            
            logPressures()
            collection.tank.sampled = True
            collection.sampled = True
            pressure = collection.mprls.pressure
            
            if collection.mprls.cantConnect or pressure > collection.up_driving_pressure * 0.9 or collection.sampled_count >= 3:
                if not collection.mprls.cantConnect and pressure <= collection.up_driving_pressure * 0.9:
                    mprint.pform("Tank " + str(collection.tank.valve.name) + " pressure still too low! - " + str(pressure) + " hPa. We'll sample it on the way down", rtc.getTPlusMS(), output_log)
                    collection.sample_upwards = False     # Mark this collection for sampling on the way down
                else:
                    mprint.pform("Finished sampling Tank " + str(collection.tank.valve.name) + " - " + str(pressure) + " hPa", rtc.getTPlusMS(), output_log)
                break   # Terminate the loop once we get the correct pressure or we've sampled too many times
            mprint.pform("Tank " + str(collection.tank.valve.name) + " pressure still too low! - " + str(pressure), rtc.getTPlusMS(), output_log)
    else:
        mprint.pform("NOT sampling collection " + str(collection.num) + " on the way up. Instead, we'll sample it on the way down at " + str(collection.down_start_time) + " ms", rtc.getTPlusMS(), output_log)


"""
    Downwards sampling management
"""
all_good = True
for collection in collections:
    if not collection.sample_upwards: all_good = False

if not all_good:
    mprint.pform("1 or more collections did not occur successfully! We'll prep to take those samples on the way down", rtc.getTPlusMS(), output_log)
    
    any_dead = False
    for collection in collections:
        if collection.tank.dead: any_dead = True 
    
    if any_dead:
        mprint.pform("Waiting for dead-test at 160000 ms.", rtc.getTPlusMS(), output_log)
        while rtc.getTPlusMS() < 160000:
            logPressures()
        
        # The dead-test checks to see if the seal between the valve and the tank has been broken.
        mprint.pform("Performing dead-test", rtc.getTPlusMS(), output_log)
        for collection in collections:
            if collection.tank.dead:
                mprint.pform("Testing Tank " + collection.tank.valve.name, rtc.getTPlusMS(), output_log)
                
                start_canister_pressure = logPressures().canister_pressure
                mprint.pform("Starting canister pressure - " + str(start_canister_pressure) + " hPa", rtc.getTPlusMS(), output_log)
                
                valve_main.open()
                collection.tank.valve.open()
                mprint.pform("VALVE_MAIN and VALVE_" + collection.tank.valve.name + " pulled HIGH", rtc.getTPlusMS(), output_log)
                
                test_starttime = rtc.getTPlusMS()
                while rtc.getTPlusMS() - test_starttime < 1000: # Open the tank for 1 second
                    logPressures()
                
                valve_main.close()
                collection.tank.valve.close()
                mprint.pform("VALVE_MAIN and VALVE_" + collection.tank.valve.name + " pulled LOW", rtc.getTPlusMS(), output_log)
                
                end_canister_pressure = logPressures().canister_pressure
                mprint.pform("Ending canister pressure - " + str(end_canister_pressure) + " hPa", rtc.getTPlusMS(), output_log)
                # TODO: Can we get a real number for this? I'm just using 3 hPa based on the known STD of the sensors
                if start_canister_pressure - end_canister_pressure < 3: # We just leaked 3 hPa from the WHOLE FUCKING ROCKET in 1 second
                    mprint.pform("The difference of pressures of " + str(start_canister_pressure - end_canister_pressure) + " hPa is negligible. Marked Tank " + collection.tank.valve.name + " for use.", rtc.getTPlusMS(), output_log)
                    collection.tank.dead = False
                else:
                    mprint.pform("The difference of pressures of " + str(start_canister_pressure - end_canister_pressure) + " hPa is SIGNIFICANT! We will keep Tank " + collection.tank.valve.name + " marked as dead.", rtc.getTPlusMS(), output_log)
    
    mprint.pform("Waiting for apogee at 170000 ms.", rtc.getTPlusMS(), output_log)
    while rtc.getTPlusMS() < 170000:
        logPressures()
        
    mprint.pform("We're at the apogee!", rtc.getTPlusMS(), output_log)
    valve_main.open()
    valve_bleed.open()
    mprint.pform("VALVE_MAIN and VALVE_BLEED pulled HIGH", rtc.getTPlusMS(), output_log)
    
    for collection in collections:
        if not collection.sample_upwards:
            collection.tank.valve.open()
            collection.tank.sampled = False
            collection.sampled = False
            collection.sampled_count = 0
            mprint.pform("VALVE_" + collection.tank.valve.name + " pulled HIGH", rtc.getTPlusMS(), output_log)
        
    while rtc.getTPlusMS() < 175000:
        logPressures()
    
    valve_main.close()
    valve_bleed.close()
    valve_1.close()
    valve_2.close()
    valve_3.close()
    mprint.pform("ALL VALVES pulled LOW", rtc.getTPlusMS(), output_log)
    
    # Reverse the order of the collections because the highest collections are now first
    rev_collections = [None] * len(collections)
    i = len(collections) - 1
    f = 0
    while i >= 0:
        rev_collections[f] = collections[i]
        i-=1
        f+=1
    
    for collection in rev_collections:
        if not collection.sample_upwards and not collection.tank.dead:
            while True:
                collection.sampled_count += 1
                mprint.pform("Waiting for sample collection " + collection.num + " at " + str(collection.down_start_time) + " ms. Try #" + str(collection.sampled_count), rtc.getTPlusMS(), output_log)
                while rtc.getTPlusMS() < collection.down_start_time:
                    logPressures()
                
                # Is this bleed unnecessary?
                mprint.pform("Beginning inside bleed for sample collection " + collection.num, rtc.getTPlusMS(), output_log)
                tank_bleed.open()
                mprint.pform("VALVE_BLEED pulled HIGH", rtc.getTPlusMS(), output_log)
                sample_bleed_starttime = rtc.getTPlusMS()
                while rtc.getTPlusMS() - sample_bleed_starttime < collection.bleed_duration + 50:   # +50ms, just to ensure we get everything out
                    logPressures()
                tank_bleed.close()
                mprint.pform("VALVE_BLEED pulled LOW", rtc.getTPlusMS(), output_log)
                
                mprint.pform("Beginning sampling for sample collection " + collection.num, rtc.getTPlusMS(), output_log)
                valve_main.open()
                collection.tank.valve.open()
                mprint.pform("VALVE_MAIN and VALVE_" + collection.tank.valve.name + " pulled HIGH", rtc.getTPlusMS(), output_log)
                sample_starttime = rtc.getTPlusMS()
                while rtc.getTPlusMS() - sample_starttime < collection.down_duration:
                    logPressures()
                valve_main.close()
                collection.tank.valve.close()
                mprint.pform("VALVE_MAIN and VALVE_" + collection.tank.valve.name + " pulled LOW", rtc.getTPlusMS(), output_log)
                
                logPressures()
                collection.tank.sampled = True
                collection.sampled = True
                pressure = collection.mprls.pressure
                
                if collection.mprls.cantConnect or pressure > collection.down_driving_pressure * 0.9 or collection.sampled_count >= 3:
                    mprint.pform("Finished sampling Tank " + collection.tank.valve.name + " - " + str(pressure) + " hPa", rtc.getTPlusMS(), output_log)
                    break   # Terminate the loop once we get the correct pressure or we've sampled too many times
                mprint.pform("Tank " + collection.tank.valve.name + " pressure still too low! - " + str(pressure), rtc.getTPlusMS(), output_log)
                
        else:
            mprint.pform("NOT sampling collection " + collection.num + " on the way down", rtc.getTPlusMS(), output_log)

else:
    mprint.pform("We sampled everything on the way up sucessfully!", rtc.getTPlusMS(), output_log)


mprint.pform("Waiting for end of flight at 805000 ms.", rtc.getTPlusMS(), output_log)
while rtc.getTPlusMS() < 805000:
    continue

"""
    Clean everything up
"""
mprint.pform("Cleaning up the system.", rtc.getTPlusMS(), output_log)

# End the connection to the MCC128 (Vibration ADC)
stop_vibration_thread = True
vibration_collection_thread.join()
daqhat.close()
mprint.pform("Cleaned and closed the DAQHAT/MCC128.", rtc.getTPlusMS(), output_log)

# Close the GPIO setup
valve_main.close()
valve_bleed.close()
valve_1.close()
valve_2.close()
valve_3.close()
GPIO.cleanup()
mprint.pform("Cleaned up the GPIO", rtc.getTPlusMS(), output_log)

# Close the output files
mprint.pform("A mimir...", rtc.getTPlusMS(), output_log)
output_log.close()
output_pressures.close()

# Shutdown the system (No going back!)
os.system("shutdown now")