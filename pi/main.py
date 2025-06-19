"""
This is the script for the Main Raspberry Pi, written by Anthony Ford and Nerissa Lundquist.

This does the following:
    Uses MultiPrint for filewriting
    Pulls the valves low at boot
    Connects to ALL i2c devices
        Can handle any i2c device not connecting (in terms of not crashing)
    Adjust procedures if any sensors cannot connect
    Gets RTC time
        Keeps track of T+
    Logs pressures
    Sample collections
    Implements all UML Activity Diagrams to build error handling
    Adheres to all requirements of the 2024-25 Stevens RockSat-C program
"""

# Communications & Paths
from RPi import GPIO
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))  

from pi.collection import Collection

# ------------------------------ SETTINGS ------------------------------
VERSION = "skeleton.2025.6.19"

DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live
EXPECTED_POWER_ON_T_PLUS = -180000  # T-3 minute activation

GPIO_MODE = GPIO.BCM
VALVE_MAIN_PIN = 17         # ASCO Main Valve control pin. 11 (BOARD) -> 17 (BCM)
VALVE_DYNAMIC_PIN = 27      # ASCO Dynamic Pressure Valve control pin. 13 (BOARD) -> 27 (BCM)
VALVE_STATIC_PIN = 18       # ASCO Static Pressure Valve control pin. 12 (BOARD) -> 18 (BCM)
VALVE_1_PIN = 24            # ASCO First tank control pin. Due to PCB issue, using 17 (BOARD) -> 24 (BCM)
VALVE_2_PIN = 23            # ASCO Second tank control pin. 16 (BOARD) -> 23 (BCM)
GSWITCH_PIN = 25            # G-switch input pin

# Setup our Colleciton objects. All durations are going to be the minimum actuation time
collection_1 = Collection(num = 1, # THESE NUMBERS EXTRACTED FROM THE OVERLEAF DOCUMENTATION (6/1/2025)
                          up_start_time = 16400,
                          bleed_duration = 696, 
                          up_driving_pressure = 3290,
                          up_final_stagnation_pressure = 910,
                          choke_pressure = 1840,
                          up_duration = 593
                          )
collection_dummy = Collection(num = 2,
                          up_start_time = 0,
                          bleed_duration = 0,
                          up_driving_pressure = 0,
                          up_final_stagnation_pressure = 0,
                          choke_pressure = 0,
                          up_duration = 0
                          )
# ----------------------------------------------------------------------

collections = [collection_1, collection_dummy]

from pi.processes.process import Process

import time
from pi.utils import timeMS

FIRST_ON_MS = timeMS() # Record the very first moment we are running the script
TIME_LAUNCH_MS = -1

# System control, like file writing
import os
from pi.multiprint import MultiPrinter

mprint = MultiPrinter()

output_log = open(str(time.time()) + '_output.txt', 'x') # Our main output file will be named as ${time}_output.txt
output_pressures = open(str(time.time()) + '_pressures.csv', 'x') # Our pressure output file will be named as ${time}_pressures.csv

Process.set_multiprint(mprint)
Process.set_output_log(output_log)
Process.set_output_pressures(output_pressures)

mprint.p("time & sys imported, files open. Time: " + str(timeMS()) + " ms\tFirst script on: " + str(FIRST_ON_MS) + " ms", output_log)
mprint.p("Version " + str(VERSION) + ". Time: " + str(timeMS()) + " ms", output_log)

mprint.w("Time (ms),T+ (ms),Pressure Manifold (hPa),Pressure Tank 1 (hPa),Pressure Tank 2 (hPa),Pressure Canister (hPa),", output_pressures) # Set up our CSV headers



# Hardware & Sensors
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_tca9548a
from pi.RTC import RTCWrappedSensor  # Our home-built Realtime Clock lib
from pi.valve import Valve
from pi.tank import Tank
from pi.MPRLS import MPRLSWrappedSensor, NovaPressureSensor, MCP9600Thermocouple
from tests.test_MPRLS import DummyI2CChannel # For stand-in sensors before defining them.

# Init GPIO
#   We do this before connecting to i2c devices because we want to make sure our valves are closed!
GPIO.setmode(GPIO_MODE)      # Use some made up BS numbers
#GPIO.setmode(GPIO.BOARD)    # Use the board's physical pin numbers

valve_main = Valve(VALVE_MAIN_PIN, "main")
valve_dynamic = Valve(VALVE_DYNAMIC_PIN, "dynamic")
valve_static = Valve(VALVE_STATIC_PIN, "static")
valve_1 = Valve(VALVE_1_PIN, "1")
valve_2 = Valve(VALVE_2_PIN, "2")

# Pull all the gates low
valve_main.close()
valve_dynamic.close()
valve_static.close()
valve_1.close()
valve_2.close()
mprint.p("Valves pulled LOW. Time: " + str(timeMS()) + " ms", output_log)

# Init i2c
i2c = I2C(1)    # Use i2c bus #1
time.sleep(2)   # Needed to ensure i2c is properly initialized
mprint.p("i2c initialized. Time: " + str(timeMS()) + " ms", output_log)

# Connect to i2c devices
# ----------------------------------------------------------------------
multiplex = False
try:
    multiplex = adafruit_tca9548a.TCA9548A(i2c)
    mprint.p("Multiplexer connected. Time: " + str(timeMS()) + " ms", output_log)
except:
    mprint.p("COULD NOT CONNECT TO MULTIPLEXER!! Time: " + str(timeMS()) + " ms", output_log)

# Create blank objects
mprls_canister = MPRLSWrappedSensor()
nova_manifold = NovaPressureSensor(DummyI2CChannel(-1))
nova_tank_1 = NovaPressureSensor(DummyI2CChannel(-1))
nova_tank_2 = NovaPressureSensor(DummyI2CChannel(-1))
dpv_temp_sensor = MCP9600Thermocouple(DummyI2CChannel(-1))

if multiplex != False:
    # Canister MPRLS
    mprls_canister = MPRLSWrappedSensor(multiplexer_line=multiplex[0])
    if mprls_canister.cant_connect:
        mprint.p("COULD NOT CONNECT TO CANISTER MPRLS!! Time: " + str(timeMS()) + " ms", output_log)

    # Manifold NOVA sensor
    nova_manifold = NovaPressureSensor(channel=multiplex[1], psi_max=100)
    if not nova_manifold.ready:
        mprint.p("COULD NOT CONNECT TO MANIFOLD NOVA SENSOR!! Time: " + str(timeMS()) + " ms", output_log)

    # Tank 1 NOVA sensor
    nova_tank_1 = NovaPressureSensor(channel=multiplex[2])
    if not nova_tank_1.ready:
        mprint.p("COULD NOT CONNECT TO TANK 1 NOVA SENSOR!! Time: " + str(timeMS()) + " ms", output_log)

    # Tank 2 NOVA sensor
    nova_tank_2 = NovaPressureSensor(channel=multiplex[3])
    if not nova_tank_2.ready:
        mprint.p("COULD NOT CONNECT TO TANK 2 NOVA SENSOR!! Time: " + str(timeMS()) + " ms", output_log)

    # DPV Thermocouple
    dpv_temp_sensor = MCP9600Thermocouple(multiplexer_channel=multiplex[4])
    if dpv_temp_sensor.cant_connect:
        mprint.p("COULD NOT CONNECT TO DPV THERMOCOUPLE!! Time: " + str(timeMS()) + " ms", output_log)
    
    mprint.p("Pressure & Temperature Sensors connected. Time: " + str(timeMS()) + " ms", output_log)
else:
    mprint.p("NOT CONNECTING TO THE I2C SENSORS because there's no multiplexer on the line!!. Time: " + str(timeMS()) + " ms", output_log)
# ----------------------------------------------------------------------

# Get our time bearings
# ----------------------------------------------------------------------
# Connect to the RTC
rtc = RTCWrappedSensor(i2c)

# Establish our T0
time_try_rtc = timeMS()
while (not rtc.isReady()) and (time_try_rtc + 3000 > timeMS()): # Wait for up to 3 seconds for RTC.
    pass

if rtc.isReady():

    TIME_LAUNCH_MS = rtc.getT0MS()
    
    mprint.pform("Got RTC after " + str(timeMS() - time_try_rtc) + " ms\tT0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)
    
else:   # Bruh. No RTC on the line. Guess that's it.

    TIME_LAUNCH_MS = FIRST_ON_MS - DEFAULT_BOOT_TIME + EXPECTED_POWER_ON_T_PLUS # We'll assume 35 seconds in, based on lab testing. Add 180 seconds from 1.SYS.1 Early Activation
    rtc.setEstT0(TIME_LAUNCH_MS)
    
    mprint.p("NO RTC!! Going to assume it's 35 seconds past T-180s. Time: " + str(timeMS()) + " ms", output_log)
    mprint.pform("T0: " + str(TIME_LAUNCH_MS) + " ms", rtc.getTPlusMS(), output_log)

Process.set_rtc(rtc)
# ----------------------------------------------------------------------


# Get our first pressure readings through LogPressures
from pi.processes.process_log_pressures import LogPressures
log_pressures_process = LogPressures()
log_pressures_process.set_canister_pressure_sensor(mprls_canister)
log_pressures_process.set_dpv_temperature(dpv_temp_sensor)
log_pressures_process.set_pressure_sensors([nova_manifold, nova_tank_1, nova_tank_2])
log_pressures_process.run()

# Setup our Tank objects
tank_1 = Tank(valve_1, nova_tank_1)
tank_2 = Tank(valve_2, nova_tank_2)

# Connect the Tanks to their respective collection periods
collection_1.tank = tank_1
collection_dummy.tank = tank_2

# FUN BITS HERE
# Initial Pressure Check
# ----------------------------------------------------------------------
from pi.processes.process_initial_pressure_check import InitialPressureCheck
initial_pressure_check_process = InitialPressureCheck()
initial_pressure_check_process.set_tanks([tank_1, tank_2])
initial_pressure_check_process.set_log_pressures(log_pressures_process)
initial_pressure_check_process.set_main_valve(valve_main)
initial_pressure_check_process.set_manifold_pressure_sensor(nova_manifold)
initial_pressure_check_process.run()
# ----------------------------------------------------------------------

# Setup the G-Switch listener
# ----------------------------------------------------------------------
from pi.utils import gswitch_callback
GPIO.setup(GSWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(GSWITCH_PIN, GPIO.FALLING,
                      callback=lambda channel: gswitch_callback(channel, GSWITCH_PIN), 
                      bouncetime=500)
# ----------------------------------------------------------------------

# Swap Tanks
# ----------------------------------------------------------------------
from pi.processes.process_swap_tanks import SwapTanks
swap_tanks_process = SwapTanks()
swap_tanks_process.set_collections(collections)
swap_tanks_process.set_tanks([tank_1, tank_2])
swap_tanks_process.run()
# ----------------------------------------------------------------------

# Import Sample Upwards and Vent Hot Air before we run sample upwards so we don't wait for imports before running Vent Hot Air
from pi.processes.process_sample_upwards import SampleUpwards
from pi.processes.process_vent_hot_air import VentHotAir

# Sample Upwards
# ----------------------------------------------------------------------
sample_upwards_process = SampleUpwards()
sample_upwards_process.set_log_pressures(log_pressures_process)
sample_upwards_process.set_collections(collections)
sample_upwards_process.set_main_valve(valve_main)
sample_upwards_process.set_dynamic_valve(valve_dynamic)
sample_upwards_process.set_static_valve(valve_static)
sample_upwards_process.set_manifold_pressure_sensor(nova_manifold)
sample_upwards_process.run()
# ----------------------------------------------------------------------

# Vent Hot Air
# ----------------------------------------------------------------------
vent_hot_air_process = VentHotAir()
vent_hot_air_process.set_log_pressures(log_pressures_process)
vent_hot_air_process.set_all_valves([valve_main, valve_dynamic, valve_static, valve_1, valve_2])
vent_hot_air_process.set_dpv_temperature_sensor(dpv_temp_sensor)
vent_hot_air_process.set_main_valve(valve_main)
vent_hot_air_process.set_static_valve(valve_static)
vent_hot_air_process.run()
# ----------------------------------------------------------------------

# Clean everything up
# ----------------------------------------------------------------------
# Close the GPIO setup
Valve.cleanup_all()
mprint.pform("Cleaned up the GPIO", rtc.getTPlusMS(), output_log)

# Save the current time to the system
mprint.pform("Saving the current time to the system...", rtc.getTPlusMS(), output_log)
os.system("fake-hwclock save")
mprint.pform("Done saving current time.", rtc.getTPlusMS(), output_log)

# Close the output files
mprint.pform("A mimir...", rtc.getTPlusMS(), output_log)
output_log.close()
output_pressures.close()

# Shutdown the system (No going back!)
os.system("shutdown now")
# ----------------------------------------------------------------------