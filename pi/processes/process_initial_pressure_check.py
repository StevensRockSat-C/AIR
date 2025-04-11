import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.tank import Tank, TankState
from pi.processes.process import Process, PlumbingState
from pi.processes.process_log_pressures import LogPressures
from pi.MPRLS import PressureSensor
from pi.valve import Valve

class InitialPressureCheck(Process):

    def __init__(self):
        self.log_pressures: LogPressures = None
        self.tanks: list[Tank] = []
        self.manifold_pressure: PressureSensor = None
        self.main_valve: Valve = None
        self.p_unsafe = 900 # hPa
        self.p_crit = 1050  # hPa

    def set_log_pressures(self, log_pressures_process: LogPressures):
        self.log_pressures = log_pressures_process

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
        if self.log_pressures is None:
            Process.get_multiprint().pform("LogPressures not set for Initial Pressure Check! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("LogPressures not set for Initial Pressure Check!")
            return False
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
            
            if tank_pressure > self.p_crit:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is pressurized above atmospheric (" + str(tank_pressure) + " hPa). Marked it CRITICAL.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.state = TankState.CRITICAL
                continue

            if tank_pressure > self.p_unsafe:
                Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is atmospheric (" + str(tank_pressure) + " hPa). Marked it UNSAFE.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
                tank.state = TankState.UNSAFE
                continue
            
            Process.get_multiprint().pform("Pressure in Tank " + tank.valve.name + " is " + str(tank_pressure) + ". Marked it READY.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            tank.state = TankState.READY

        if self.manifold_pressure.triple_pressure != -1:
            Process.get_multiprint().pform("Manifold pressure sensor is accessible. Opening the main valve for 2 seconds.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            ref_manifold_pressure: float = self.manifold_pressure.triple_pressure # Record reference manifold pressrue
            self.main_valve.open()

            start_time = Process.rtc.getTPlusMS()
            while Process.rtc.getTPlusMS() < start_time + 2000: # Keep the main valve open for 2 seconds
                self.log_pressures.run()

            self.main_valve.close()
            Process.get_multiprint().pform("Closed main valve.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

            new_manifold_pressure: float = self.manifold_pressure.triple_pressure # Record new manifold pressrue
            delta_manifold_pressure = new_manifold_pressure - ref_manifold_pressure
            Process.get_multiprint().pform("Manifold pressure is " + str(new_manifold_pressure) + " hPa, from " + str(ref_manifold_pressure) + " hPa. Delta " + str(delta_manifold_pressure) + " hPa.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            
            if abs(delta_manifold_pressure) > 100:
                # TODO: Log here
                Process.set_plumbing_state(PlumbingState.MAIN_LINE_FAILURE)
            elif new_manifold_pressure > self.p_crit:
                # TODO: Log here
                Process.set_plumbing_state(PlumbingState.MAIN_LINE_FAILURE)
            else:
                Process.set_plumbing_state(PlumbingState.READY)
        
        else:
            Process.get_multiprint().pform("Manifold pressure sensor is offline! Assuming the plumbing state is READY.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            Process.set_plumbing_state(PlumbingState.READY)

        if Process.plumbing_state == PlumbingState.READY: #if everything is all good case
            number_of_ready_tanks = len(list(filter(lambda tank: tank.state == TankState.READY, self.tanks)))
            if number_of_ready_tanks == len(self.tanks):
                return #all tanks marked ready, and plumbing state marked ready

        # At least one tank t UNSAFE OR at least one tank t READY?
        matching_tanks: list[Tank] = []
        for tank in self.tanks:
            if tank.state == TankState.UNSAFE or tank.state == TankState.READY:
                matching_tanks.append(tank)
        if not matching_tanks: return

        # Of the matching tanks, set t.status of the lowest pressure tank to LAST_RESORT
        lowest_tank = min(
            (tank for tank in matching_tanks),
            key=lambda x: x.mprls.triple_pressure
        )
        lowest_tank.state = TankState.LAST_RESORT


    def cleanup(self):
        Process.get_multiprint().pform("Finished Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())


