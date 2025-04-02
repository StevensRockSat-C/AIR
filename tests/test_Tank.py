import warnings
import pytest
import sys
sys.path.append('../')
from pi.tank import Tank, TankState

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
            pass
        
        def _get_pressure(self):
            return 50
        
        def _set_pressure(self, value):
            pass
        
        def _del_pressure(self):
            pass
        
        pressure = property(
            fget=_get_pressure,
            fset=_set_pressure,
            fdel=_del_pressure,
            doc="The pressure of the Pressure Sensor or -1 if it cannot be accessed"
        )
    
    return MockMPRLS()

def test_tank_initialization(mock_mprls):
    """Test that a tank initializes correctly with a valve and a  pressure sensor."""
    valve = MockValve(10, "test_valve")
    tank = Tank(valve, mock_mprls)

    assert tank.valve == valve
    assert tank.mprls == mock_mprls
    assert tank.state == TankState.UNKNOWN

def test_tank_initialization_no_mprls(mock_mprls):
    """Assure that a tank will not initialize if no pressure sensor is provided."""
    valve = MockValve(10, "test_valve")
    with pytest.raises(TypeError):
        tank = Tank(valve)

def test_tank_read_pressure(mock_mprls):
    """Test that a tank reads pressure correctly."""
    valve = MockValve(10, "test_valve")
    tank = Tank(valve, mock_mprls)

    assert tank.mprls.pressure == 50

def test_tank_open_close(mock_mprls):
    """Test opening and closing a tank's valve."""
    valve = MockValve(10, "test_valve")
    tank = Tank(valve, mock_mprls)

    tank.open()
    assert tank.valve.state == "OPEN"  # Ensure valve is open

    tank.close()
    assert tank.valve.state == "CLOSED"  # Ensure valve is closed

def test_tank_pressure_sensor_property(mock_mprls):
    """Test the pressure sensor property of a tank."""
    valve = MockValve(10, "test_valve")
    tank = Tank(valve, mock_mprls)

    assert tank.mprls == mock_mprls

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(Warning):
            tank.mprls = mock_mprls

