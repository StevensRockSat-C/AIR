import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.tank import Tank, TankState
from pi.processes.process import Process
from pi.MPRLS import PressureSensor
from pi.valve import Valve

class InitialPressureCheck(Process):

    def __init__(self):
        self.tanks: list[Tank] = []
        self.manifold_pressure: PressureSensor
        self.main_valve: Valve
        self.p_unsafe = 900 # hPa
        self.p_crit = 1050  # hPa

    def set_tanks(self, tanks: list[Tank]):
        self.tanks = tanks

    def set_manifold_pressure_sensor(self, pressure_sensor: PressureSensor):
        self.manifold_pressure = pressure_sensor

    def set_main_valve(self, main_valve: Valve):
        self.main_valve = main_valve

    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for Initial Pressure Check!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for Initial Pressure Check!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if self.tanks is None:
            Process.get_multiprint().pform("Tanks not set for Initial Pressure Check! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Tanks not set for Initial Pressure Check!")
            return False
        if self.manifold_pressure is None:
            Process.get_multiprint().pform("Manifold Pressure Sensor not set for Initial Pressure Check! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Manifold Pressure Sensor not set for Initial Pressure Check!")
            return False
        if self.main_valve is None:
            Process.get_multiprint().pform("Main Valve not set for Initial Pressure Check! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Main Valve not set for Initial Pressure Check!")
            return False
        return True

    def execute(self):
        Process.get_multiprint().pform("Performing Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
    
        for tank in self.tanks:
            if tank.mprls.cant_connect or tank.mprls.pressure == -1:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " cannot be determined! Marked it UNREACHABLE.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.state = TankState.UNREACHABLE
                continue
            
            tank_pressure = tank.mprls.triple_pressure
            if tank_pressure > self.p_unsafe:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is atmospheric (" + str(tank_pressure) + " hPa). Marked it UNSAFE.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.state = TankState.UNSAFE
                continue
            else:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is " + str(tank_pressure) + ". Marked it READY.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.state = TankState.READY

        if tank.mprls.cant_connect or tank.mprls.pressure == -1:
            pass

    def cleanup(self):
        Process.get_multiprint().pform("Finished Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())


