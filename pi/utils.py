"""
Small utility functions for main.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

from pi.processes.process import Process

from warnings import warn
import time
from typing import Final, Literal

try:
    import RPi.GPIO as GPIO
except ImportError:
    warn("Using mock GPIO for utils!")
    
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
        def remove_event_detect(cls, channel: int):
            pass

        @classmethod
        def cleanup(cls):
            cls._mode = None

    GPIO = MockGPIO()  # Replace RPi.GPIO with mock

def timeMS():
    """Get system time to MS."""
    return round(time.time()*1000)

# TODO: HOLY FUCK MAKE SURE THIS WORKS WITH LIMITS!
def gswitch_callback(channel, GSWITCH_PIN: int):
    """
    Handle the G-Switch input. This sets our reference T+0.

    Parameters
    ----------
    channel : int
        GPIO Pin.
    rtc : RTCWrappedSensor
        The RTC sensor instance
    mprint : MultiPrinter
        The printer instance for logging
    output_log : file
        The output log file
    GSWITCH_PIN : int
        The GPIO pin number for the G-switch

    Returns
    -------
    None.
    """

    t0 = timeMS()
    GPIO.remove_event_detect(GSWITCH_PIN)

    prior_t0 = Process.get_rtc().getT0MS()
    estimated_diff_ms = t0 - prior_t0

    if (estimated_diff_ms < -120000 or estimated_diff_ms > 5000): # Only accept between T-120s and T+5s
        if Process.can_log():
            Process.get_multiprint().pform("G-Switch input! Difference from RBF estimation: " + str(estimated_diff_ms) + " ms, which is too far off! We'll ignore it!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        return

    difference = Process.get_rtc().setEstT0(t0)
    if Process.can_log():
        Process.get_multiprint().pform("G-Switch input! New t0: " + str(t0) + " ms. Difference from RBF estimation: " + str(difference) + " ms", Process.get_rtc().getTPlusMS(), Process.get_output_log())
