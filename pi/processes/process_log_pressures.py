import os
from warnings import warn
from typing import Union

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pi.processes.process import Process
from pi.MPRLS import PressureSensor, TemperatureSensor, PressureTemperatureSensor

class LogPressures(Process):

    _temp_thresh_reached: bool = False
    _currently_sampling: bool = False
    T_ANYTIME: int = 470 # Kelvin
    T_SAMPLE: int = 400 # Kelvin
    _time_last_sampled = 0 #in ms
    _time_btw_temp_checks = 15 #in ms

    def __init__(self):
        self.dpv_temperature_sensor: Union[TemperatureSensor, PressureTemperatureSensor] = None
        self.pressure_temperature_sensors: list[PressureTemperatureSensor] = []
        self.canister_pressure_sensor: PressureSensor = None

    @classmethod
    def get_temp_thresh_reached(cls):
        return cls._temp_thresh_reached
    
    @classmethod
    def set_temp_thresh_reached(cls, reached: bool):
        if not cls._temp_thresh_reached and reached:
            if Process.can_log():
                Process.get_multiprint().pform("Temp threshold reached & set!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        cls._temp_thresh_reached = reached

    @classmethod
    def get_currently_sampling(cls):
        return cls._currently_sampling
    
    @classmethod
    def set_currently_sampling(cls, sampling: bool):
        cls._currently_sampling = sampling

    def set_canister_pressure_sensor(self, canister_pressure_sensor: PressureSensor):
        self.canister_pressure_sensor = canister_pressure_sensor

    def set_pressure_sensors(self, pressure_temperature_sensors: list[PressureTemperatureSensor]):
        self.pressure_temperature_sensors = pressure_temperature_sensors
        
    def set_dpv_temperature(self, dpv_temperature_sensor: TemperatureSensor):
        self.dpv_temperature_sensor = dpv_temperature_sensor

    def run(self) -> bool:
        #print(type(Process.get_multiprint()))
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
        if not self.pressure_temperature_sensors or len(self.pressure_temperature_sensors) <= 0:
            Process.get_multiprint().pform("Pressure Sensors not set for LogPressures!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Pressure Sensors not set for Log Pressures!")
            return False
        if not isinstance(self.dpv_temperature_sensor, (TemperatureSensor, PressureTemperatureSensor)):
            Process.get_multiprint().pform("DPV Temperature Sensor not set for LogPressures!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("DPV Temperature Sensor not set for Log Pressures!")
            return False
        if not isinstance(self.canister_pressure_sensor, PressureSensor):
            Process.get_multiprint().pform("Canister Pressure Sensor not set for LogPressures!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Canister Pressure Sensor not set for Log Pressures!")
            return False
        return True

    def execute(self):
        current_time = Process.get_rtc().getTPlusMS()
        output_pressures = str(current_time) + ","

        if LogPressures.get_temp_thresh_reached():
            for pressure_sensor in self.pressure_temperature_sensors:
                output_pressures += str(pressure_sensor.pressure) + ","
            
            output_pressures += str(self.canister_pressure_sensor.pressure) + ","

            Process.get_multiprint().p(output_pressures, Process.get_output_pressures())
            return

        tank_temperatures: list[float] = []
        
        for pressure_sensor in self.pressure_temperature_sensors:
            current_pressure, current_temperature = pressure_sensor.pressure_and_temp
            output_pressures += str(current_pressure) + ","
            tank_temperatures.append(current_temperature)
        
        output_pressures += str(self.canister_pressure_sensor.pressure) + ","
        
        Process.get_multiprint().p(output_pressures, Process.get_output_pressures())

        if current_time >= self._time_last_sampled + self._time_btw_temp_checks: 
            self._time_last_sampled = current_time
            dpv = self.dpv_temperature_sensor.temperature
            if dpv >= LogPressures.T_ANYTIME:
                Process.get_multiprint().pform("DPV Temperature may be over T_ANYTIME: " + str(dpv) + "K. Running triple check...", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                current_temperature = self.dpv_temperature_sensor.triple_temperature
                if current_temperature >= LogPressures.T_ANYTIME:
                    LogPressures.set_temp_thresh_reached(True)
                    Process.get_multiprint().pform("TEMP_THRESH_REACHED! DPV Temperature over T_ANYTIME: " + str(current_temperature) + "K, triple checked!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                    return
            
            target_temp = LogPressures.T_SAMPLE if LogPressures.get_currently_sampling() else LogPressures.T_ANYTIME
            if any(temperature >= target_temp for temperature in tank_temperatures):
                Process.get_multiprint().pform("A temperature sensor may be over " + ("T_SAMPLE" if LogPressures.get_currently_sampling() else "T_ANYTIME") + ": " + str(tank_temperatures) + "K. Running triple check...", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                for sensor in self.pressure_temperature_sensors:
                    current_temperature = sensor.triple_temperature
                    if current_temperature >= target_temp:
                        LogPressures.set_temp_thresh_reached(True)
                        Process.get_multiprint().pform("TEMP_THRESH_REACHED! A temperature sensor is over " + ("T_SAMPLE" if LogPressures.get_currently_sampling() else "T_ANYTIME") + ": " + str(current_temperature) + "K, triple checked!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                        return
        return

    def cleanup(self):
        pass