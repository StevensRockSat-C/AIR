import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.processes.process import Process, PlumbingState
from pi.processes.process_log_pressures import LogPressures
from pi.collection import Collection
from pi.tank import TankState
from pi.valve import Valve
from pi.MPRLS import PressureSensor

class SampleUpwards(Process):

    def __init__(self):
        self.collections: list[Collection] = []
        self.log_pressures: LogPressures = None
        self.main_valve: Valve = None
        self.dynamic_valve: Valve = None
        self.static_valve: Valve = None
        self.manifold_pressure_sensor: PressureSensor = None

        self.t_efficacy: float = 2000 # (milliseconds) Time for which to open the dynamic and main valves to measure driving pressure
        self.t_small: float = 100 # (milliseconds) The amount of time to 'test' the line to see if new sample is truly coming in, or if it was just stagnant pressure from the manifold
        self.delta_pressure_threshold: float = 50 # (hPa) The limit of change for which ΔP ≈ 0

    def set_log_pressures(self, log_pressures_process: LogPressures):
        self.log_pressures = log_pressures_process

    def set_collections(self, collections: list[Collection]):
        self.collections = collections
        
    def set_main_valve(self, main_valve: Valve):
        self.main_valve = main_valve

    def set_dynamic_valve(self, dynamic_valve: Valve):
        self.dynamic_valve = dynamic_valve

    def set_static_valve(self, static_valve: Valve):
        self.static_valve = static_valve

    def set_manifold_pressure_sensor(self, manifold_pressure_sensor: PressureSensor):
        self.manifold_pressure_sensor = manifold_pressure_sensor
        
    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for SampleUpwards!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for SampleUpwards!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if not self.log_pressures:
            Process.get_multiprint().pform("LogPressures not set for SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("LogPressures not set for SampleUpwards!")
            return False
        if not self.collections:
            Process.get_multiprint().pform("Collections not set for SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Collections not set for SampleUpwards!")
            return False
        if not self.main_valve:
            Process.get_multiprint().pform("Main Valve not set for SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Main Valve not set for SampleUpwards!")
            return False
        if not self.dynamic_valve:
            Process.get_multiprint().pform("Dynamic Valve not set for SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Dynamic Valve not set for SampleUpwards!")
            return False
        if not self.static_valve:
            Process.get_multiprint().pform("Static Valve not set for SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Static Valve not set for SampleUpwards!")
            return False
        if not self.manifold_pressure_sensor:
            Process.get_multiprint().pform("Manifold Pressure Sensor not set for SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Manifold Pressure Sensor not set for SampleUpwards!")
            return False
        
        if self.log_pressures.get_temp_thresh_reached():
            Process.get_multiprint().pform("Temp threshold was reached before SampleUpwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Temp threshold was reached before SampleUpwards!")
            return False

        return True

    def execute(self):
        Process.get_multiprint().pform("Performing Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

        for c in self.collections:

            if c.tank.state == TankState.LAST_RESORT: # c.tank.status LAST_RESORT? Yes
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} for Collection {c.num} is {c.tank.state}! Due to new constraints, we can not test for efficacy & therefore will not sample this Collection!", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                continue
                
            elif c.tank.state != TankState.READY: # Is c.tank.status READY? No
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} for Collection {c.num} is {c.tank.state}! Will not sample this Collection!", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                continue

            elif Process.get_plumbing_state() != PlumbingState.READY: # Process. get_plumbing_state READY? No
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} for Collection {c.num} is {c.tank.state}, but the plumbing is {Process.get_plumbing_state()}. Will not sample this Collection!", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                continue

            else: # Process.get_plumbing_state READY? Yes
                Process.get_multiprint().pform(f"Waiting for Collection {c.num} at T+{c.up_start_time}ms with {c.bleed_duration}ms of bleed", 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                LogPressures.set_currently_sampling(False)
                while Process.get_rtc().getTPlusMS() < (c.up_start_time - c.bleed_duration): # Reached collection's time (c.up_start_time - c.bleed_duration)?
                    self.log_pressures.run()
                    if self.log_pressures.get_temp_thresh_reached(): # Threshold hit?
                        Process.get_multiprint().pform(f"Temp threshold hit! Aborting SampleUpwards.", 
                                                    Process.get_rtc().getTPlusMS(), Process.get_output_log())
                        return

            Process.get_multiprint().pform(f"Beginning Collection {c.num}", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
           
            self._do_sample_collection(c)

            if c.tank.state == TankState.SAMPLED:
                Process.get_multiprint().pform(f"Collection {c.num} succeeded (Tank {c.tank.valve.name} {c.tank.state})!", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
            else:
                Process.get_multiprint().pform(f"Collection {c.num} failed (Tank {c.tank.valve.name} {c.tank.state})!", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
                
    def _do_sample_collection(self, c: Collection) -> None:
        Process.get_multiprint().pform(f"Bleeding for {c.bleed_duration}ms", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
        
        ### BLEED
        # Open VDynamic & VStatic
        self.dynamic_valve.open()
        self.static_valve.open()
        Process.get_multiprint().pform(f"Opened Dynamic Valve and Static Valve", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())

        bleed_start_time = Process.get_rtc().getTPlusMS()
        LogPressures.set_currently_sampling(False)
        while Process.get_rtc().getTPlusMS() < (bleed_start_time + c.bleed_duration): #b time passed?
            self.log_pressures.run()
            if self.log_pressures.get_temp_thresh_reached(): # Threshold hit?
                Process.get_multiprint().pform(f"Temp threshold hit! Aborting SampleUpwards.", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
                return
        del bleed_start_time    # Ensure this doesn't get accidentally reused

        self.static_valve.close() # Close VStatic
        Process.get_multiprint().pform(f"Closed Static Valve", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
        
        # Take reference tankx and manifold pressure
        pre_sample_tank_pressure: float = c.tank.mprls.triple_pressure
        pre_sample_manifold_pressure = self.manifold_pressure_sensor.triple_pressure
        Process.get_multiprint().pform(f"Post-bleed pressures: Tank {pre_sample_tank_pressure} hPa, Manifold {pre_sample_manifold_pressure} hPa", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
        
        ### SAMPLE
        while c.sampled_count < 3: # Careful, Icarus...
            c.sampled_count += 1
            Process.get_multiprint().pform(f"Sampling Collection {c.num} for {c.up_duration}ms. Try #{c.sampled_count}",
                                        Process.get_rtc().getTPlusMS(), Process.get_output_log())

            # Open VDynamic, Vmain & Vtankx
            self.dynamic_valve.open()
            self.main_valve.open()
            c.tank.open()
            Process.get_multiprint().pform(f"Opened Dynamic, Main, and Tank {c.tank.valve.name} Valve",
                                        Process.get_rtc().getTPlusMS(), Process.get_output_log())
            
            sample_start_time = Process.get_rtc().getTPlusMS()
            LogPressures.set_currently_sampling(True)
            while Process.get_rtc().getTPlusMS() < (sample_start_time + c.up_duration): #tc time passed?
                self.log_pressures.run()
                if self.log_pressures.get_temp_thresh_reached(): # Threshold hit?
                    Process.get_multiprint().pform(f"Temp threshold hit! Aborting SampleUpwards.", 
                                                Process.get_rtc().getTPlusMS(), Process.get_output_log())
                    c.tank.state = TankState.FAILED_SAMPLE
                    return

            # Close VDynamic, Vmain & Vtankx
            self.dynamic_valve.close()
            self.main_valve.close()
            c.tank.close()
            Process.get_multiprint().pform(f"Closed Dynamic, Main, and Tank {c.tank.valve.name} Valve",
                                        Process.get_rtc().getTPlusMS(), Process.get_output_log())
            
            post_sample_tank_pressure: float = c.tank.mprls.triple_pressure
            if post_sample_tank_pressure >= 0.95 * c.up_final_stagnation_pressure: # Ptank ≥ 95% of pc? (using triple pressure)
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({post_sample_tank_pressure} hPa) has met final stag pressure ({c.up_final_stagnation_pressure} hPa). Sampled successfully",
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
                c.tank.state = TankState.SAMPLED
                return
            
            Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({post_sample_tank_pressure} hPa) did NOT meet final stag pressure ({c.up_final_stagnation_pressure} hPa)!",
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
            
            if c.sampled_count >= 2: # Second Try?
                Process.get_multiprint().pform(f"This was the second try. Failed sample!",
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
                c.tank.state = TankState.FAILED_SAMPLE
                return
            
            if abs(post_sample_tank_pressure - pre_sample_tank_pressure) < self.delta_pressure_threshold or post_sample_tank_pressure == -1 or pre_sample_tank_pressure == -1: # ΔPtank ≈ 0? (using triple pressure) OR either pressure = -1
                post_sample_manifold_pressure: float = self.manifold_pressure_sensor.triple_pressure
                
                if abs(post_sample_manifold_pressure - pre_sample_manifold_pressure) < self.delta_pressure_threshold: # ΔPmanifold ≈ 0? (using triple pressure) (Yes (An upstream valve has failed) (valvex state unknown))
                    Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({pre_sample_tank_pressure} -> {post_sample_tank_pressure} hPa) and manifold pressure ({pre_sample_manifold_pressure} -> {post_sample_manifold_pressure} hPa) did not change significantly. There must be a main line failure!",
                                                Process.get_rtc().getTPlusMS(), Process.get_output_log())
                    Process.set_plumbing_state(PlumbingState.MAIN_LINE_FAILURE)
                else: # No (valvex has failed)
                    Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({pre_sample_tank_pressure} -> {post_sample_tank_pressure} hPa) did not change significantly but the manifold pressure did ({pre_sample_manifold_pressure} -> {post_sample_manifold_pressure} hPa). Valve for Tank {c.tank.valve.name} must have failed!",
                                                Process.get_rtc().getTPlusMS(), Process.get_output_log())
                    c.tank.state = TankState.FAILED_SAMPLE
                
                return
            
            # Take reference tank pressure
            pre_t_small_tank_pressure: float = c.tank.mprls.triple_pressure

            # Open VDynamic, Vmain & Vtankx
            self.dynamic_valve.open()
            self.main_valve.open()
            c.tank.open()
            Process.get_multiprint().pform(f"Opened Dynamic, Main, and Tank {c.tank.valve.name} Valve for t_small test",
                                        Process.get_rtc().getTPlusMS(), Process.get_output_log())
            
            t_small_start_time = Process.get_rtc().getTPlusMS()
            LogPressures.set_currently_sampling(True)
            while Process.get_rtc().getTPlusMS() < (t_small_start_time + self.t_small): # tsmall time passed?
                self.log_pressures.run()
                if self.log_pressures.get_temp_thresh_reached(): # Threshold hit?
                    Process.get_multiprint().pform(f"Temp threshold hit! Aborting SampleUpwards.", 
                                                Process.get_rtc().getTPlusMS(), Process.get_output_log())
                    c.tank.state = TankState.FAILED_SAMPLE
                    return
            del t_small_start_time

            # Close VDynamic, Vmain & Vtankx
            self.dynamic_valve.close()
            self.main_valve.close()
            c.tank.close()
            Process.get_multiprint().pform(f"Closed Dynamic, Main, and Tank {c.tank.valve.name} Valve",
                                        Process.get_rtc().getTPlusMS(), Process.get_output_log())
            
            post_t_small_tank_pressure: float = c.tank.mprls.triple_pressure
            if abs(post_t_small_tank_pressure - pre_t_small_tank_pressure) < self.delta_pressure_threshold or post_t_small_tank_pressure == -1 or pre_t_small_tank_pressure == -1: # ΔPtank ≈ 0? (using triple pressure) OR either pressure = -1 Yes (Vacuum of tank was compromised, but questionable sample)
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({pre_t_small_tank_pressure} -> {post_t_small_tank_pressure} hPa) did not change significantly during t_small test. This means that the vacuum of Tank {c.tank.valve.name} was compromised, but the sample is questionable. Failed Sample!",
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
                c.tank.state = TankState.FAILED_SAMPLE
                return
            else: # ΔPtank ≈ 0? (using triple pressure) No (valve chain is open, math on tx was wrong)
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({pre_t_small_tank_pressure} -> {post_t_small_tank_pressure} hPa) changed significantly during t_small test. This means that the valve chain is open, but the math on collection duration was wrong",
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
                
                if post_t_small_tank_pressure >= 0.95 * c.up_final_stagnation_pressure: # Ptank ≥ 95% of pc? (using triple pressure) Yes (Reached desired pressure during tsmall test) 
                    Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({post_t_small_tank_pressure} hPa) has met final stag pressure ({c.up_final_stagnation_pressure} hPa) during t_small test. Sampled successfully",
                                                Process.get_rtc().getTPlusMS(), Process.get_output_log())
                    c.tank.state = TankState.SAMPLED
                    return
                
                Process.get_multiprint().pform(f"Tank {c.tank.valve.name} pressure ({post_t_small_tank_pressure} hPa) did NOT meet final stag pressure ({c.up_final_stagnation_pressure} hPa) during t_small test! Trying again",
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())

                
    def cleanup(self):
        Process.get_multiprint().pform("Finished Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        