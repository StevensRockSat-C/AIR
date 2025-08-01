import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.absolute()))  

from pi.MPRLS import PressureSensor
from pi.tank import Tank, TankState

class Collection:
    """
    Represents a sample collection period.

    Attributes
    ----------
    num : int
        The index of this collection period.
    up_start_time : int
        The T+ timestamp (ms) when sampling should start on ascent.
    bleed_duration : int
        How long (ms) to bleed the lines before collecting.
    up_driving_pressure : float
        Expected pressure (hPa) in the manifold while sampling on ascent.
    up_final_stagnation_pressure : float
        Expected pressure (hPa) in the tank after sampling on ascent.
    choke_pressure : float
        The absolute maximum tank pressure (hPa) for choked flow to work on this sample.
    up_duration : int
        Duration (ms) to keep the valve open on ascent.
    tank : Tank, optional
        The associated tank (default: None).
    """

    def __init__(
        self, num: int,
        up_start_time: int,
        bleed_duration: int,
        up_driving_pressure: float,
        up_final_stagnation_pressure: float,
        choke_pressure: float,
        up_duration: int,
        tank: Tank = None
    ):
        """Initialize a Collection instance."""
        self.num = str(num)
        self.up_start_time = up_start_time
        self.bleed_duration = bleed_duration
        self.up_driving_pressure = up_driving_pressure
        self.up_final_stagnation_pressure = up_final_stagnation_pressure
        self.p_choke = choke_pressure
        self.up_duration = up_duration
        self.tank = tank
        self.sampled_count = 0  # Tracks how many times we've tried to sample
        
    @property
    def pressure_sensor(self) -> PressureSensor:
        """Dynamically retrieve the pressure sensor from the associated tank."""
        return self.tank.pressure_sensor if self.tank else None
    
    def associate_tank(self, tank: Tank):
        """
        Associate a tank and it's pressure sensor with this collection.

        Parameters
        ----------
        tank : Tank
            The tank for this collection.
        """
        self.tank = tank
    
    @property
    def sampled(self) -> bool:
        """
        Pass-through for the tank's sampled status.
        
        Returns
        -------
        True if, and only if, the tank state is SAMPLED
        """
        if self.tank and self.tank.state == TankState.SAMPLED:
            return True
        return False

    @classmethod
    def swap_tanks(cls, collection1: 'Collection', collection2: 'Collection'):
        """Swap the tanks between two collections."""
        tank1 = collection1.tank
        tank2 = collection2.tank
        collection1.tank = tank2
        collection2.tank = tank1

