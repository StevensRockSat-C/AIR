import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.tank import Tank, TankState
from pi.collection import Collection
from pi.processes.process import Process

class SwapTanks(Process):

    def __init__(self):
        self.tanks: list[Tank] = []
        self.collections: list[Collection] = []

    def set_tanks(self, tanks: list[Tank]):
        self.tanks = tanks

    def set_collections(self, collections: list[Collection]):
        self.collections = collections

    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for SwapTanks!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for SwapTanks!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing SwapTanks.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if not self.tanks:
            warn("Tanks not set for SwapTanks!")
            Process.get_multiprint().pform("Tanks not set for SwapTanks! Aborting!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.collections:
            warn("Collections not set for SwapTanks!")
            Process.get_multiprint().pform("Collections not set for SwapTanks! Aborting!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if len(self.collections) != len(self.tanks):
            warn("Number of Tanks not equal to the number of Collections in SwapTanks!")
            Process.get_multiprint().pform("Number of Tanks not equal to the number of Collections in SwapTanks! Aborting!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        return True

    def execute(self):
        Process.get_multiprint().pform("Performing SwapTanks.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

        not_ready_tanks: list[Tank] = []
        last_resort_tanks: list[Tank] = []
        ready_tanks: list[Tank] = self.tanks

        # Move tanks into 3 different lists by state
        for tank in self.tanks:
            if tank.state != TankState.READY:
                ready_tanks.remove(tank)
                if tank.state == TankState.LAST_RESORT:
                    last_resort_tanks.append(tank)
                else:
                    not_ready_tanks.append(tank)

        # Sort ready tanks from least to greatest pressure
        ready_tanks.sort(key=lambda tank: tank.mprls.triple_pressure)

        for collection in self.collections:
            if last_resort_tanks: # Assign last resort tanks first
                collection.associate_tank(last_resort_tanks[0])
                Process.get_multiprint().pform("Assigned tank " + str(last_resort_tanks[0].valve.name) + " to Collection " + str(collection.num), 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                last_resort_tanks.remove(last_resort_tanks[0])
                continue
            if ready_tanks: # Then ready tanks
                collection.associate_tank(ready_tanks[0])
                Process.get_multiprint().pform("Assigned tank " + str(ready_tanks[0].valve.name) + " to Collection " + str(collection.num), 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                ready_tanks.remove(ready_tanks[0])
                continue
            if not_ready_tanks: # Then not ready tanks
                collection.associate_tank(not_ready_tanks[0])
                Process.get_multiprint().pform("Assigned tank " + str(not_ready_tanks[0].valve.name) + " to Collection " + str(collection.num), 
                                               Process.get_rtc().getTPlusMS(), Process.get_output_log())
                not_ready_tanks.remove(not_ready_tanks[0])
                continue
            
            # If we're here, no tank was assinged
            Process.get_multiprint().pform("Collection " + str(collection.num) + " doesn't have a tank?!", 
                                            Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Collection " + str(collection.num) + " doesn't have a tank?!")
        
    def cleanup(self):
        Process.get_multiprint().pform("Finished Initial Pressure Check.", Process.get_rtc().getTPlusMS(), Process.get_output_log())


