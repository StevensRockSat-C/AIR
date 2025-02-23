import sys
import os

# Allow execution from 'pi' directory
if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
from pi.tank import Tank
from pi.MPRLS import MPRLS

class Collection:
    """
    Represents a sample collection period.

    Attributes
    ----------
    num : int
        The index of this collection period.
    up_start_time : int
        The T+ timestamp (ms) when sampling should start on ascent.
    down_start_time : int
        The T+ timestamp (ms) when sampling should start on descent.
    bleed_duration : int
        How long (ms) to bleed the lines before collecting.
    up_driving_pressure : float
        Expected pressure (hPa) in the tank on ascent.
    down_driving_pressure : float
        Expected pressure (hPa) in the tank on descent.
    upwards_bleed : bool
        Whether this collection requires bleeding when sampling on ascent.
    up_duration : int, optional
        Duration (ms) to keep the valve open on ascent (default: 100ms).
    down_duration : int, optional
        Duration (ms) to keep the valve open on descent (default: 100ms).
    tank : Tank, optional
        The associated tank (default: None).
    mprls : MPRLS, optional
        The associated MPRLS pressure sensor (default: None).
    """

    def __init__(
        self, num: int,
        up_start_time: int, down_start_time: int,
        bleed_duration: int,
        up_driving_pressure: float, down_driving_pressure: float,
        upwards_bleed: bool,
        up_duration: int = 100, down_duration: int = 100,
        tank: Tank = None, mprls: MPRLS = None
    ):
        """Initialize a Collection instance."""
        self.num = str(num)
        self.up_start_time = up_start_time
        self.down_start_time = down_start_time
        self.bleed_duration = bleed_duration
        self.up_driving_pressure = up_driving_pressure
        self.down_driving_pressure = down_driving_pressure
        self.upwards_bleed = upwards_bleed
        self.up_duration = up_duration
        self.down_duration = down_duration
        self.tank = tank
        self.mprls = mprls
        self.sampled = False
        self.sample_upwards = True  # Set to False if sampling on descent
        self.sampled_count = 0  # Tracks how many times we've tried to sample

    def associate_tank_and_sensor(self, tank: Tank, mprls: MPRLS):
        """
        Associate a tank and an MPRLS sensor with this collection.

        Parameters
        ----------
        tank : Tank
            The tank for this collection.
        mprls : MPRLS
            The MPRLS sensor for this collection.
        """
        self.tank = tank
        self.mprls = mprls