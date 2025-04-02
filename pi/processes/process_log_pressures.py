import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.processes.process import Process
from pi.MPRLS import PressureSensor

class LogPressures(Process):

    def __init__(self):
        self.pressure_sensors: list[PressureSensor] = []

    def set_pressure_sensors(self, pressure_sensors: list[PressureSensor]):
        self.pressure_sensors = pressure_sensors

    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for LogPressures!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for LogPressures!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        if self.pressure_sensors is None:
            Process.get_multiprint().pform("Pressure Sensors not set for LogPressures!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Pressure Sensors not set for Log Pressures!")
            return False
        return True

    def execute(self):
        output_pressures = str(Process.get_rtc().getTPlusMS()) + ","
        for pressure_sensor in self.pressure_sensors:
            output_pressures += str(pressure_sensor.pressure) + ","
        
        Process.get_multiprint().p(output_pressures, Process.get_output_pressures())

    def cleanup(self):
        pass