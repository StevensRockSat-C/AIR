import warnings
import pytest
import sys
sys.path.append('../')
from pi.valve import Valve  # Import the Valve class

class MockGPIO:
    BCM = 11
    BOARD = 10
    OUT = 0
    HIGH = 1
    LOW = 0

    _mode = None
    _pin_states = {}
    
    @classmethod
    def setmode(cls, mode):
        cls._mode = mode

    @classmethod
    def getmode(cls):
        return cls._mode

    @classmethod
    def setup(cls, pin, mode):
        cls._pin_states[pin] = mode  # Store pin setup

    @classmethod
    def output(cls, pin, state):
        cls._pin_states[pin] = state  # Store pin state

    @classmethod
    def cleanup(cls):
        cls._mode = None
        cls._pin_states.clear()

@pytest.fixture
def mock_gpio(monkeypatch):
    """Monkeypatch the RPi.GPIO module."""
    
    import pi.valve as ValveClass
    monkeypatch.setattr(ValveClass, "GPIO", MockGPIO)
    return MockGPIO  # Return the mocked class for additional assertions

@pytest.fixture(autouse=True)
def cleanup_valves():
    """Cleanup all valves after tests."""
    Valve.cleanup_all()

def test_valve_initialization(mock_gpio):
    """Test that a valve initializes correctly and sets up GPIO."""
    valve = Valve(27, "test_valve")

    assert mock_gpio.getmode() == mock_gpio.BCM  # Default mode should be BCM
    assert mock_gpio._pin_states[27] == mock_gpio.OUT  # Pin should be set as output

def test_valve_open(mock_gpio):
    """Test opening the valve (setting GPIO pin HIGH)."""
    valve = Valve(27, "test_valve")
    valve.open()

    assert mock_gpio._pin_states[27] == mock_gpio.HIGH  # Ensure the pin is HIGH

def test_valve_close(mock_gpio):
    """Test closing the valve (setting GPIO pin LOW)."""
    valve = Valve(27, "test_valve")
    valve.close()

    assert mock_gpio._pin_states[27] == mock_gpio.LOW  # Ensure the pin is LOW

def test_valve_custom_gpio_mode(mock_gpio):
    """Test initializing a valve with a custom GPIO mode."""
    Valve._gpio_mode = mock_gpio.BOARD
    valve = Valve(27, "test_valve")

    assert mock_gpio.getmode() == mock_gpio.BOARD  # Check custom mode was set

def test_duplicate_valves(mock_gpio):
    """Test that duplicate valves are not created."""

    valve1 = Valve(27, "test_valve_1")
    valve2 = Valve(29, "test_valve_2") # Uh-oh, we miss-typed!

    with pytest.warns(UserWarning, match=r"Valve with pin 29 \(test_valve_2\) already exists!"):
        valve3 = Valve(29, "test_valve_3")

def test_valve_cleanup_all(mock_gpio):
    """Test cleanup of all valves."""
    valve1 = Valve(27, "valve1")
    valve2 = Valve(22, "valve2")

    # Store pin states before cleanup
    valve1.close()
    valve2.open()

    assert mock_gpio._pin_states[27] == mock_gpio.LOW
    assert mock_gpio._pin_states[22] == mock_gpio.HIGH

    # Now call cleanup
    Valve.cleanup_all()

    # Ensure cleanup reset everything
    assert mock_gpio.getmode() is None
    assert not mock_gpio._pin_states  # Should be empty

    # Test re-using the Valve class after cleanup
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        valve1 = Valve(27, "valve1")
        valve2 = Valve(22, "valve2")
        valve1.open()
        valve2.close()

    assert mock_gpio._pin_states[27] == mock_gpio.HIGH
    assert mock_gpio._pin_states[22] == mock_gpio.LOW
