import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.tank import Tank
from pi.processes.process import Process

class InitialPressureCheck(Process):

    def __init__(self):
        self.tanks: list[Tank] = []

    def set_tanks(self, tanks: list[Tank]):
        self.tanks = tanks

    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for Initial Pressure Check!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for Initial Pressure Check!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if self.initialize():
            self.execute()
            self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if self.tanks is None:
            warn("Tanks not set for Initial Pressure Check!")
            return False
        return True

    def execute(self):
        Process.get_multiprint().pform("Performing Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
    
        for tank in self.tanks:
            if tank.mprls.cant_connect or tank.mprls.pressure == -1:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " cannot be determined! Marked it as dead", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.dead = True
                continue
            tank_pressure = tank.mprls.triple_pressure
            if tank_pressure > 900:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is atmospheric (" + str(tank_pressure) + " hPa). Marked it as dead", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.dead = True
            else:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is " + str(tank_pressure) + ". All good.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

    def cleanup(self):
        Process.get_multiprint().pform("Finished Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())


