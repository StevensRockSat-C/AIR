import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.processes.process import Process, PlumbingState
from pi.processes.process_log_pressures import LogPressures
from pi.collection import Collection
from pi.tank import TankState
from pi.valve import Valve

class SampleUpwards(Process):

    def __init__(self):
        self.collections: list[Collection] = []
        self.log_pressures: LogPressures
        self.main_valve: Valve
        self.dynamic_valve: Valve

    def set_log_pressures(self, log_pressures_process: LogPressures):
        self.log_pressures = log_pressures_process

    def set_collections(self, collections: list[Collection]):
        self.collections = collections
        
    def set_main_valve(self, main_valve: Valve):
        self.main_valve = main_valve

    def set_dynamic_valve(self, dynamic_valve: Valve):
        self.dynamic_valve = dynamic_valve
        
    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for Sample Upwards!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for Sample Upwards!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if not self.log_pressures:
            Process.get_multiprint().pform("LogPressures not set for Sample Upwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("LogPressures not set for Sample Upwards!")
            return False
        if not self.collections:
            Process.get_multiprint().pform("Collections not set for Sample Upwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Collections not set for Sample Upwards!")
            return False
        if not self.main_valve:
            Process.get_multiprint().pform("Main Valve not set for Sample Upwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Main Valve not set for Sample Upwards!")
            return False
        if not self.dynamic_valve:
            Process.get_multiprint().pform("Dynamic Valve not set for Sample Upwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Dynamic Valve not set for Sample Upwards!")
            return False
        return True

    def execute(self):
        Process.get_multiprint().pform("Performing Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

        for c in self.collections:

            if c.tank.state == TankState.LAST_RESORT: # c.tank.status LAST_RESORT? Yes
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} for Collection {c.num} is {c.tank.state}! Waiting to test for efficacy at T+{c.up_start_time - c.bleed_duration}s", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                # TODO: More stuff from right-side of the diagram
                
            elif c.tank.state != TankState.READY: # Is c.tank.status READY? No
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} for Collection {c.num} is {c.tank.state}! Will not sample this Collection!", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                continue

            elif Process.get_plumbing_state() != PlumbingState.READY: # Process. get_plumbing_state READY? No
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} for Collection {c.num} is {c.tank.state}, but the plumbing is {Process.get_plumbing_state()}. Will not sample this Collection!", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                continue

            else: # Process.get_plumbing_state READY? Yes
                Process.get_multiprint().pform(f"Waiting for Collection {c.num} at T+{c.up_start_time}s with {c.bleed_duration}s of bleed", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                while Process.get_rtc().getTPlusMS() < (c.up_start_time - c.bleed_duration): # Reached collection's time (c.up_start_time - c.bleed_duration)?
                    self.log_pressures.run()

            Process.get_multiprint().pform(f"Beginning Collection {c.num}", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
            # TODO: Sample lmao

    
    def cleanup(self):
        Process.get_multiprint().pform("Finished Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())