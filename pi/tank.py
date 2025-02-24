import sys
import os

# Allow execution from 'pi' directory
if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.valve import Valve
from pi.MPRLS import MPRLS

class Tank:
    """
    Represents a single tank, controlling its valve and pressure sensor.
    
    Attributes
    ----------
        valve (Valve): The valve controlling the tank.
        mprls (MPRLS, optional): The pressure sensor for the tank.
        sampled (bool): Indicates if the tank has been sampled.
        dead (bool): Indicates if the tank is non-functional.
    """

    def __init__(self, valve: Valve, mprls: MPRLS = None):
        """
        Initialize the tank.

        Parameters
        ----------
        valve : Valve
            The valve associated with this tank.
        mprls : MPRLS, optional
            The pressure sensor. The default is None.

        Returns
        -------
        None.

        """
        self.valve = valve
        self.mprls = mprls  # Optional, set to None if not provided
        self.sampled = False
        self.dead = False  # Set dynamically if the tank reaches 100 kPa

    def open(self):
        """Open the valve to allow flow."""
        self.valve.open()

    def close(self):
        """Close the valve to stop flow."""
        self.valve.close()
