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
    Prevent bleeding if proper conditions cannot be validated
"""
import time
from RPi import GPIO
from adafruit_extended_bus import ExtendedI2C as I2C

from MPRLS import PressureSensor, NovaPressureSensor
from multiprint import MultiPrinterAbstract, MultiPrinter
from RTC import RTC, RTCWrappedSensor
from tank import Tank, TankState
from valve import Valve
from collection import Collection

from processes.process import Process, PlumbingState
from processes.process_initial_pressure_check import InitialPressureCheck
from processes.process_log_pressures import LogPressures
from processes.process_sample_upwards import SampleUpwards
from processes.process_swap_tanks import SwapTanks, TankState

VERSION = "2.0.0"

DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live

GPIO_MODE = GPIO.BCM
VALVE_MAIN_PIN = 11         # Parker 11/25/26 Main Valve control pin
VALVE_DYNAMIC_PIN = 13
VALVE_STATIC_PIN = 12
VALVE_1_PIN = 15            # First tank control pin
VALVE_2_PIN = 6             # Second tank control pin
VALVE_3_PIN = 18            # Third tank control pin    not needed due to only having two tanks
GSWITCH_PIN = 23            # G-switch input pin
GPIO_PIN = 22               # Unsure if we need this?

# Logs initialization
mprint = MultiPrinter()
output_log = open(str(time.time()) + '_output.txt', 'x')
output_pressures = open(str(time.time()) + '_pressures.csv', 'x')
mprint.w("Time (ms),T+ (ms),Pressure Canister (hPa),Pressure Bleed (hPa),Pressure Valve 1 (hPa),Pressure Valve 2 (hPa),Pressure Valve 3 (hPa)", output_pressures) # Set up our CSV headers

# RTC and i2c bus initialization   
i2c = I2C(1)    # Use i2c bus #1
time.sleep(2)   # To ensure that the i2c bus is correctly set up   
start_time = time.time()
rtc = RTCWrappedSensor(start_time)    #what is the correct input for this?

# Valve initialization
valve1 = Valve(VALVE_1_PIN, "Tank_1_valve")
valve2 = Valve(VALVE_2_PIN, "Tank_2_valve")
valve3 = Valve(VALVE_3_PIN, "Tank_3_valve")
valve_dynamic = Valve(VALVE_DYNAMIC_PIN, "Dynamic_valve")
valve_static = Valve(VALVE_STATIC_PIN, "Static_valve")
valve_main = Valve(VALVE_MAIN_PIN, "Main_valve")

# Pressure sensor initialization
pr_sensor_t1 = NovaPressureSensor(0x28) #what should the channel be?
pr_sensor_t2 = NovaPressureSensor(0x28)
pr_sensor_t3 = NovaPressureSensor(0x28)
pr_sensor_canister = NovaPressureSensor(0x28)
pr_sensor_manifold = NovaPressureSensor(0x28)

# Tank initialization
sample_tank_1 = Tank(valve1, pr_sensor_t1)
sample_tank_2 = Tank(valve2, pr_sensor_t2)
sample_tank_3 = Tank(valve3, pr_sensor_t3)
tanks = [sample_tank_1, sample_tank_2, sample_tank_3]

# Collection initialization
collection_1 = Collection(  num = 1,        #this is a string in the class diagram
                            up_start_time = 40305,
                            bleed_duration = 5,
                            up_driving_pressure = 1270.44,
                            up_final_stagnation_pressure = 1300,
                            choke_pressure = 1.89,
                            up_duration = 156.29,
                            #tank = sample_tank_1 
                        )

collection_2 = Collection( num = 2,         #this is a string in the class diagram
                            up_start_time = 19000,
                            bleed_duration = 5,
                            up_driving_pressure = 1270.44,
                            up_final_stagnation_pressure = 1300,
                            choke_pressure = 2.23,
                            up_duration = 170.57,
                            #tank = sample_tank_2 
                        )
    
collection_3 = Collection( num = 3,         #this is a string in the class diagram
                            up_start_time = 21000,
                            bleed_duration = 5,
                            up_driving_pressure = 1270.44,
                            up_final_stagnation_pressure = 1300,
                            choke_pressure = 1.93,
                            up_duration = 175.27,
                            #tank = sample_tank_3 
                        )

collections = [collection_1, collection_2, collection_3]

# Setup Process
Process.set_multiprint(mprint)
Process.set_rtc(rtc)
Process.set_output_log(output_log)
Process.set_output_pressures(output_pressures)

# Initial pressure check setup and run
initial_pressure_check = InitialPressureCheck()
initial_pressure_check.set_tanks(tanks)
initial_pressure_check.set_manifold_pressure_sensor(pr_sensor_manifold)
initial_pressure_check.set_main_valve(valve_main)

initial_pressure_check.run()

# Swap tanks setup and run
swap_tanks = SwapTanks()
swap_tanks.set_tanks(tanks)
swap_tanks.set_collections(collections)

swap_tanks.run()

# Sample upwards setup and run
sample_upwards = SampleUpwards()
logPres = LogPressures()
sample_upwards.set_log_pressures(logPres)
sample_upwards.set_collections(collections)
sample_upwards.set_main_valve(valve_main)
sample_upwards.set_dynamic_valve(valve_dynamic)
sample_upwards.set_static_valve(valve_static)
sample_upwards.set_manifold_pressure_sensor(pr_sensor_manifold)

sample_upwards.run()