import pytest
import sys
sys.path.append('../')
from pi.tank import Tank

class MockValve:
    """Mock Valve class to fully isolate Tank tests."""
    def __init__(self, pin, name):
        self.pin = pin
        self.name = name
        self.state = "CLOSED"

    def open(self):
        self.state = "OPEN"

    def close(self):
        self.state = "CLOSED"

@pytest.fixture
def mock_mprls(monkeypatch):
    """Mock the MPRLS class."""
    class MockMPRLS:
        def __init__(self):
            self.pressure = 50  # Default pressure 50 kPa
        
        def read_pressure(self):
            return self.pressure
    
    return MockMPRLS()

def test_tank_initialization(mock_mprls):
    """Test that a tank initializes correctly with a valve and an optional pressure sensor."""
    valve = MockValve(10, "test_valve")
    tank = Tank(valve, mock_mprls)

    assert tank.valve == valve
    assert tank.mprls == mock_mprls
    assert tank.sampled is False
    assert tank.dead is False

def test_tank_open_close():
    """Test opening and closing a tank's valve."""
    valve = MockValve(10, "test_valve")
    tank = Tank(valve)

    tank.open()
    assert tank.valve.state == "OPEN"  # Ensure valve is open

    tank.close()
    assert tank.valve.state == "CLOSED"  # Ensure valve is closed
