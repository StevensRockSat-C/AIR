import sys
import os
from enum import Enum
from warnings import warn

# Allow execution from 'pi' directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.valve import Valve
from pi.MPRLS import PressureSensor

class Tank:
    """
    Represents a single tank, controlling its valve and pressure sensor.
    
    Attributes
    ----------
        valve (Valve): The valve controlling the tank.
        mprls (PressureSensor, optional): The pressure sensor for the tank.
        sampled (bool): Indicates if the tank has been sampled.
        dead (bool): Indicates if the tank is non-functional.
    """

    def __init__(self, valve: Valve, pressure_sensor: PressureSensor):
        """
        Initialize the tank.

        Parameters
        ----------
        valve : Valve
            The valve associated with this tank.
        pressure_sensor : PressureSensor, optional
            The pressure sensor. The default is None.

        Returns
        -------
        None.

        """
        self.valve = valve
        self.pressure_sensor = pressure_sensor
        self.state = TankState.UNKNOWN

    def open(self):
        """Open the valve to allow flow."""
        self.valve.open()

    def close(self):
        """Close the valve to stop flow."""
        self.valve.close()

    def _get_pressure_sensor(self):
        """Get the pressure sensor object."""
        return self.pressure_sensor

    def _set_pressure_sensor(self, value):
        """A pressure sensor is permanently attached to a tank, so we cannot reset it."""
        warn("A pressure sensor is permanently attached to a tank, so we cannot reset it.")
        pass

    def _del_pressure_sensor(self):
        """A pressure sensor is permanently attached to a tank, so we cannot delete it."""
        pass

    mprls = property(
        fget=_get_pressure_sensor,
        fset=_set_pressure_sensor,
        fdel=_del_pressure_sensor,
        doc="The pressure sensor of the tank"
    )

class TankState(Enum):
    """
    An enumeration to represent the state at which a Tank is in.
    """
    UNKNOWN = 0
    UNSAFE = 1
    CRITICAL = 2
    UNREACHABLE = 3
    LAST_RESORT = 4
    READY = 5
    FAILED_SAMPLE = 6
    SAMPLED = 7