import sys
import os
from warnings import warn
from typing import Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.processes.process import Process
from pi.processes.process_log_pressures import LogPressures
from pi.valve import Valve
from pi.MPRLS import TemperatureSensor, PressureTemperatureSensor

class VentHotAir(Process):

    def __init__(self):
        self.log_pressures: LogPressures = None
        self.dpv_temperature_sensor: Union[TemperatureSensor, PressureTemperatureSensor] = None
        self.all_valves: list[Valve] = []
        self.main_valve: Valve = None
        self.static_valve: Valve = None

        self.t_VENT: int = 5000 # (milliseconds) The maximum amount of time to vent the line filled with hot gas for
        self.T_VENT_TARGET: int = 380 # (Kelvin) The target temperature to lower to when venting
        
        # Variables for tracking temperature change
        self.temp_history: list[tuple[float, int]] = []  # List of (temperature, timestamp) pairs
        self.TEMP_CHANGE_THRESHOLD: float = 5.0  # (Kelvin per second) How much the temperature must increase for us to abort
        self.TEMP_COMPARISON_INTERVAL: int = 500  # (milliseconds) How much time over which to check for temperature changes. Still happens as often as the sensor can be read from.
        self.OLD_DATA_BUFFER_TIME: int = 250 # (milliseconds) How much extra time to keep the temperature data in memory past the TEMP_COMPARISON_INTERVAL

    def set_log_pressures(self, log_pressures_process: LogPressures):
        self.log_pressures = log_pressures_process

    def set_all_valves(self, all_valves: list[Valve]):
        """
        Provide all valves to VentHotAir to allow for assurance when handling

        Parameters
        ----------
        all_valves : list[Valve]
            All valves on the payload.

        Returns
        -------
        None.

        """
        self.all_valves = all_valves

    def set_main_valve(self, main_valve: Valve):
        self.main_valve = main_valve

    def set_static_valve(self, static_valve: Valve):
        self.static_valve = static_valve

    def set_dpv_temperature_sensor(self, dpv_temperature_sensor: Union[TemperatureSensor, PressureTemperatureSensor]):
        self.dpv_temperature_sensor = dpv_temperature_sensor

    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for VentHotAir!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for VentHotAir!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing VentHotAir.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if not self.log_pressures:
            Process.get_multiprint().pform("LogPressures not set for VentHotAir! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("LogPressures not set for VentHotAir!")
            return False
        if not self.all_valves:
            Process.get_multiprint().pform("All Valves not set for VentHotAir! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("All Valves not set for VentHotAir!")
            return False
        if not self.main_valve:
            Process.get_multiprint().pform("Main Valve not set for VentHotAir! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Main Valve not set for VentHotAir!")
            return False
        if not self.static_valve:
            Process.get_multiprint().pform("Static Valve not set for VentHotAir! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Static Valve not set for VentHotAir!")
            return False
        if not self.dpv_temperature_sensor:
            Process.get_multiprint().pform("DPV Temperature Sensor not set for VentHotAir! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("DPV Temperature Sensor not set for VentHotAir!")
            return False
        
        Process.get_multiprint().pform("We are " + 
                                        ("" if self.log_pressures.get_temp_thresh_reached() else "NOT ") + 
                                        "here because TEMP_THRESH_REACHED!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        
        return True

    def execute(self):
        for valve in self.all_valves:
            valve.close()
            Process.get_multiprint().pform("Valve " + valve.name + " closed.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        Process.get_multiprint().pform("Finished closing valves.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

        self.main_valve.open()
        self.static_valve.open()
        Process.get_multiprint().pform(f"Opened Main Valve and Static Valve.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

        vent_start_time = Process.get_rtc().getTPlusMS()
        while Process.get_rtc().getTPlusMS() < (vent_start_time + self.t_VENT): #t_vent time passed?
            self.log_pressures.run()

            current_dpv_temp = self.dpv_temperature_sensor.triple_temperature
            if current_dpv_temp <= 0: # If it's an invalid reading
                continue

            if current_dpv_temp < self.T_VENT_TARGET:
                Process.get_multiprint().pform(f"DPV Temperature ({current_dpv_temp}K) is less than VENT_TARGET ({self.T_VENT_TARGET}K). Finished Venting.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                break
            
            # Add current reading to history
            current_time = Process.get_rtc().getTPlusMS()
            self.temp_history.append((current_dpv_temp, current_time))
            
            # Remove old readings (much older than our comparison interval)
            old_data_cutoff_time = current_time - self.TEMP_COMPARISON_INTERVAL - self.OLD_DATA_BUFFER_TIME
            self.temp_history = [(temp, time) for temp, time in self.temp_history if time > (old_data_cutoff_time)]

            # Create temporary list without those younger than cutoff time. We're left with samples from TEMP_COMPARISON_INTERVAL -> TEMP_COMPARISON_INTERVAL + OLD_DATA_BUFFER_TIME
            new_data_cutoff_time = current_time - self.TEMP_COMPARISON_INTERVAL
            temporary_temperature_hist = [(temp, time) for temp, time in self.temp_history if time <= new_data_cutoff_time]
            
            # Only compare if we have a reading from at least 0.5s ago
            if len(temporary_temperature_hist) < 2:
                continue
            
            # Get the latest reading after the cutoff_time
            old_temp, old_time = temporary_temperature_hist[-1]
            time_diff_seconds = (current_time - old_time) / 1000.0  # Convert ms to seconds
            temp_change_rate = (current_dpv_temp - old_temp) / time_diff_seconds

            if temp_change_rate > self.TEMP_CHANGE_THRESHOLD:
                Process.get_multiprint().pform(f"Temperature is increasing ({old_temp:.1f}K -> {current_dpv_temp:.1f}K over {time_diff_seconds}s = {temp_change_rate:.2f}K/s)! Aborting Venting!", 
                                                current_time, Process.get_output_log())
                break
        
        self.main_valve.close()
        self.static_valve.close()
        Process.get_multiprint().pform(f"Closed Main Valve and Static Valve.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

    def cleanup(self):
        Process.get_multiprint().pform("Finished VentHotAir.", Process.get_rtc().getTPlusMS(), Process.get_output_log())