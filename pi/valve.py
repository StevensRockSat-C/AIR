from RPi import GPIO

class Valve:
    """Everything related to a valve."""

    _instances = []  # Track all instances for cleanup

    def __init__(self, pin: int, name: str, gpio_mode=GPIO.BCM):
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
        self.pin = pin
        self.name = name

        # Set GPIO mode, if it hasn't been already
        if GPIO.getmode() != gpio_mode:
            GPIO.setmode(gpio_mode)

        GPIO.setup(self.pin, GPIO.OUT)  # Set the pin to output mode
        Valve._instances.append(self)

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
