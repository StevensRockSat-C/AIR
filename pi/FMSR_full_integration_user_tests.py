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
import sys
import os

from pathlib import Path
import adafruit_tca9548a
from adafruit_extended_bus import ExtendedI2C as I2C


sys.path.append(str(Path(__file__).parent.parent.absolute()))

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.valve import MockGPIO, Valve, MockValve #should be changed when we refactor it
from pi.MPRLS import PressureSensor, MPRLSFile, MockPressureSensorStatic , NovaPressureSensor
from pi.multiprint import MultiPrinterAbstract, MockMultiPrinter
from pi.RTC import RTC, RTCFile 
from pi.tank import Tank, TankState
from pi.collection import Collection

from pi.processes.process import Process, PlumbingState
from pi.processes.process_initial_pressure_check import InitialPressureCheck
from pi.processes.process_log_pressures import LogPressures
from pi.processes.process_sample_upwards import SampleUpwards
from pi.processes.process_swap_tanks import SwapTanks, TankState

VERSION = "2.0.0"

DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live

#GPIO_MODE = GPIO.BCM

VALVE_MAIN_PIN = 27        # Parker 11/25/26 Main Valve control pin
VALVE_DYNAMIC_PIN = 10
VALVE_STATIC_PIN = 22
VALVE_1_PIN = 9            # First tank control pin
VALVE_2_PIN = 17           # Second tank control pin
#VALVE_3_PIN =             # Third tank control pin    not needed due to only having two tanks
#VALVE_MANIFOLD = 27            
GSWITCH_PIN = 23            # G-switch input pin

# Logs initialization
mprint = MockMultiPrinter()
output_log_name = str(time.time()) + '_output.txt'
output_log = open(output_log_name, 'x')
output_pressures = open(str(time.time()) + '_pressures.csv', 'x')
mprint.w("Time (ms),T+ (ms),Pressure Canister (hPa),Pressure Bleed (hPa),Pressure Valve 1 (hPa),Pressure Valve 2 (hPa),Pressure Valve 3 (hPa)", output_pressures) # Set up our CSV headers
log_pres = LogPressures()

# RTC and i2c bus initialization   
i2c = I2C(1)    # Use i2c bus #1
time.sleep(2)   # To ensure that the i2c bus is correctly set up  
rtc = RTCFile(time.time())

try:
    multiplex = adafruit_tca9548a.TCA9548A(i2c)
    
except:
   # mprint.p("COULD NOT CONNECT TO MULTIPLEXER!! Time: " + str(timeMS()) + " ms", output_log)
   print("uh oh")


# Valve initialization
valve1 = Valve(VALVE_1_PIN, "A")
valve2 = Valve(VALVE_2_PIN, "B")
#valve_manifold = Valve(VALVE_3_PIN, "C")
valve_dynamic = Valve(VALVE_DYNAMIC_PIN, "Dynamic_valve")
valve_static = Valve(VALVE_STATIC_PIN, "Static_valve")
valve_main = Valve(VALVE_MAIN_PIN, "Main_valve")


# Pressure sensor initialization
pr_sensor_t1 = NovaPressureSensor(multiplex[3]) #what should the channel be?
pr_sensor_t2 = NovaPressureSensor(multiplex[2])
#pr_sensor_t3 = NovaPressureSensor()
pr_sensor_canister = MockPressureSensorStatic(1.4)
pr_sensor_manifold = NovaPressureSensor(multiplex[1])


log_pres.set_pressure_sensors([pr_sensor_t1, pr_sensor_t2])


# Tank initialization
sample_tank_1 = Tank(valve1, pr_sensor_t1)
sample_tank_2 = Tank(valve2, pr_sensor_t2)
#sample_tank_3 = Tank(valve3, pr_sensor_t3)
tanks = [sample_tank_1, sample_tank_2]

# Collection initialization
collection_1 = Collection(  num = 1,        #this is a string in the class diagram
                            up_start_time = 1700, #MS
                            bleed_duration = 5,
                            up_driving_pressure = 1270.44,
                            up_final_stagnation_pressure = 1300,
                            choke_pressure = 1.89,
                            up_duration = 156.29,
                            #up_duration = 10,
                            #tank = sample_tank_1 
                        )

# collection_2 = Collection( num = 2,         #this is a string in the class diagram
#                             up_start_time = 19000,
#                             bleed_duration = 5,
#                             up_driving_pressure = 1270.44,
#                             up_final_stagnation_pressure = 1300,
#                             choke_pressure = 2.23,
#                             up_duration = 170.57,
#                             #tank = sample_tank_2 
#                         )
    
# collection_3 = Collection(  num = 3,         #this is a string in the class diagram
#                             up_start_time = 21000,
#                             bleed_duration = 5,
#                             up_driving_pressure = 1270.44,
#                             up_final_stagnation_pressure = 1300,
#                             choke_pressure = 1.93,
#                             up_duration = 175.27,
#                             #tank = sample_tank_3 
#                         )

collections = [collection_1]


# Setup process
Process.multiprint = mprint
Process.rtc = rtc
Process.output_log = output_log
Process.output_pressures = output_pressures
Process.is_ready()

initial_pressure_check = InitialPressureCheck()
initial_pressure_check.set_log_pressures(log_pres)
initial_pressure_check.set_tanks(tanks)
initial_pressure_check.set_manifold_pressure_sensor(pr_sensor_manifold)
initial_pressure_check.set_main_valve(valve_main)


initial_pressure_check.run()

for tank in tanks:
    print(tank.valve.name, tank.state)

# Swap tanks setup and run
swap_tanks = SwapTanks()
swap_tanks.set_tanks(tanks)
swap_tanks.set_collections(collections)

swap_tanks.run()

# Sample upwards setup and run
sample_upwards = SampleUpwards()
sample_upwards.set_log_pressures(log_pres)
sample_upwards.set_collections(collections)
sample_upwards.set_main_valve(valve_main)
sample_upwards.set_dynamic_valve(valve_dynamic)
sample_upwards.set_static_valve(valve_static)
sample_upwards.set_manifold_pressure_sensor(pr_sensor_manifold)

sample_upwards.run()

output_log.close()
output_pressures.close()