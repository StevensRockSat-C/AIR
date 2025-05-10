from warnings import warn
from typing import Final, Literal

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

try:
    import RPi.GPIO as GPIO
except ImportError:
    warn("Using mock GPIO for valve!")
    
    class MockGPIO:
        """Mock GPIO for non-Raspberry Pi environments (testing)."""
        
        BOARD: Final = 10
        BCM: Final = 11
        OUT: Final = 0
        IN: Final = 1
        HIGH: Literal[1] = 1
        LOW: Literal[0] = 0

        @classmethod
        def setmode(cls, mode):
            cls._mode = mode

        @classmethod
        def getmode(cls):
            return cls._mode

        @classmethod
        def setup(cls, pin, mode):
            pass

        @classmethod
        def output(cls, pin, state):
            pass

        @classmethod
        def cleanup(cls):
            cls._mode = None

    GPIO = MockGPIO()  # Replace RPi.GPIO with mock

class Valve:
    """Everything related to a valve."""

    _instances: list = []  # Track all instances for cleanup
    _gpio_mode: Literal[10, 11] = GPIO.BCM

    def __init__(self, pin: int, name: str):
        """
        Initialize the Valve object.

        Parameters
        ----------
        pin : int
            The GPIO pin number.
        name : str
            Name of the valve.
        gpio_mode : int, optional
            GPIO mode (BCM or BOARD). The default is GPIO.BCM.

        Returns
        -------
        None.

        """
        self.pin: int = pin
        self.name: str = name

        # Set GPIO mode, if it hasn't been already
        if GPIO.getmode() != Valve._gpio_mode:
            GPIO.setmode(Valve._gpio_mode)

        duplicate_name = next((valve.name for valve in Valve._instances if valve.pin == self.pin), None)
        if not any(valve.pin == self.pin for valve in Valve._instances):
            GPIO.setup(self.pin, GPIO.OUT)  # Set the pin to output mode
            Valve._instances.append(self)
        else:
            warn(f"Valve with pin {self.pin} ({duplicate_name}) already exists!")

    def open(self):
        """Pull the valve pin HIGH (open the valve)."""
        GPIO.output(self.pin, GPIO.HIGH)

    def close(self):
        """Pull the valve pin LOW (close the valve)."""
        GPIO.output(self.pin, GPIO.LOW)

    @classmethod
    def cleanup_all(cls):
        """Cleanup all GPIO resources and reset the state."""
        for valve in cls._instances:
            valve.close()  # Ensure valves are closed
        GPIO.cleanup()
        cls._instances.clear()
