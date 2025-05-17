import pytest
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

import tempfile
import os
import time
from pi.MPRLS import MPRLSFile, MPRLSWrappedSensor, MockPressureSensorStatic, NovaPressureSensor, MCP9600Thermocouple

# -----------------------------------------
# Tests for MPRLSWrappedSensor
# -----------------------------------------

def test_mprlswrappedsensor_no_multiplexer():
    """
    When no multiplexer_line is provided, the sensor should mark itself as unable to connect.
    """
    sensor = MPRLSWrappedSensor(multiplexer_line=None)
    assert sensor.cant_connect is True
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1

def test_mprlswrappedsensor_normal(monkeypatch):
    """
    Test normal operation by simulating a sensor that returns constant pressure.
    We override the adafruit_mprls.MPRLS class so that our DummyMPRLSSensor is used.
    """
    # Dummy adafruit mprls that simulates a working sensor returning constant 15.0.
    class DummyNormalAdafruitMPRLS:
        def __init__(self, multiplexer_line, psi_min, psi_max):
            self._pressures = [15.0, 15.0, 15.0]
            self._index = 0

        @property
        def pressure(self):
            try:
                value = self._pressures[self._index]
            except IndexError:
                value = self._pressures[-1]
            self._index += 1
            return value

    # Dummy module to stand in for adafruit_mprls.
    class DummyModule:
        MPRLS = DummyNormalAdafruitMPRLS

    # Patch the module-level adafruit_mprls variable so that __init__ can create our dummy sensor.
    import pi.MPRLS as mprls_module
    monkeypatch.setattr(mprls_module, "adafruit_mprls", DummyModule)

    dummy_line = object()  # any dummy multiplexer line
    sensor = MPRLSWrappedSensor(dummy_line)
    assert sensor.cant_connect is False
    assert sensor.ready is True
    # Single pressure reading should return 15.0.
    assert sensor.pressure == 15.0
    # Triple pressure reading calls the sensor three times, so the median of [15.0, 15.0, 15.0] is 15.0.
    assert sensor.triple_pressure == 15.0

def test_mprlswrappedsensor_exception(monkeypatch):
    """
    Simulate a sensor that always raises an exception on reading.
    Both _get_pressure and _get_triple_pressure should return -1.
    """
    # Dummy sensor that always fails when reading pressure.
    class DummyFailAdafruitMPRLS:
        def __init__(self, multiplexer_line, psi_min, psi_max):
            pass

        @property
        def pressure(self):
            raise Exception("Simulated sensor error")

    class DummyModule:
        # Return an instance of the failing sensor.
        MPRLS = lambda multiplexer_line, psi_min, psi_max: DummyFailAdafruitMPRLS(multiplexer_line, psi_min, psi_max)

    # Patch the module-level adafruit_mprls variable so that __init__ can create our dummy sensor.
    import pi.MPRLS as mprls_module
    monkeypatch.setattr(mprls_module, "adafruit_mprls", DummyModule)

    dummy_line = object()
    sensor = MPRLSWrappedSensor(dummy_line)
    # In case of exceptions, both single and triple readings should return -1.
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
    # We connected, but the sensor is raising errors
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_mprlswrappedsensor_partial(monkeypatch):
    """
    Simulate a sensor that returns a valid value on the first call, then fails on the second,
    and returns another valid value on the third call. The triple reading should compute the median
    over the valid readings.
    """
    class DummyRoughAdafruitMPRLS:
        def __init__(self, multiplexer_line, psi_min, psi_max):
            self._values = [15.0, "raise", 17.0]
            self._index = 0

        @property
        def pressure(self):
            val = self._values[self._index]
            self._index += 1
            if val == "raise":
                raise Exception("Simulated sensor error")
            return val

    class DummyModule:
        MPRLS = DummyRoughAdafruitMPRLS

    # Patch the module-level adafruit_mprls variable so that __init__ can create our dummy sensor.
    import pi.MPRLS as mprls_module
    monkeypatch.setattr(mprls_module, "adafruit_mprls", DummyModule)

    dummy_line = object()
    sensor = MPRLSWrappedSensor(dummy_line)
    # The triple reading collects pressures: 15.0, (skips error), 17.0.
    # The median of [15.0, 17.0] is (15.0+17.0)/2 = 16.0.
    assert sensor.triple_pressure == 16.0


def test_mprlswrappedsensor_no_lib(monkeypatch):
    """Simulate a sensor that has no library available."""

    dummy_line = object()
    sensor = MPRLSWrappedSensor(dummy_line)
    assert sensor.cant_connect == True

# -----------------------------------------
# Dummy I2C channel for NovaPressureSensor tests
# -----------------------------------------

class DummyI2CChannel:
    def __init__(self, raw_value):
        # raw_value is an integer that will be returned as the sensor's raw reading.
        self.raw_value = raw_value

    def readfrom_into(self, address, buf):
        # Fill the provided buffer with two bytes corresponding to raw_value.
        buf[0] = (self.raw_value >> 8) & 0xFF
        buf[1] = self.raw_value & 0xFF

    def try_lock(self):
        return True

    def unlock(self):
        pass

class DummyI2CFailChannel:
    def readfrom_into(self, address, buf):
        raise Exception("I2C read error")

# -----------------------------------------
# Tests for NovaPressureSensor
# -----------------------------------------

def test_nova_pressure_sensor_valid_small(monkeypatch):
    """
    Simulate a valid NovaPressureSensor reading.
    For a raw value of 1700, the conversion yields:
      pressure_psi = ((1700 - P_MIN) * (PSI_MAX - PSI_MIN) / (P_MAX - P_MIN)) + PSI_MIN
      hPa = pressure_psi * PSI_TO_HPA
    We check that _get_pressure returns approximately the expected value.
    """
    # Use a raw value chosen to produce a valid (<= 30) hPa reading.
    # For NovaPressureSensor, P_MIN = 1638, P_MAX = 14745.
    # With raw_value = 1700, pressure_psi = ((1700-1638)*30/(14745-1638))
    #   = (62*30/13107) ≈ 0.1419 psi, so hPa ≈ 0.1419 * 68.9476 ≈ 9.79.
    raw_value = 1700
    channel = DummyI2CChannel(raw_value)
    # Avoid actual sleep delays
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    # _get_pressure computes the conversion.
    expected_hpa = ((raw_value - sensor.P_MIN) * (sensor.PSI_MAX - sensor.PSI_MIN) / (sensor.P_MAX - sensor.P_MIN)) * sensor.PSI_TO_HPA
    pressure = sensor.pressure
    # Allow for a small floating-point tolerance.
    assert abs(pressure - expected_hpa) < 0.1
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_nova_pressure_sensor_valid_large(monkeypatch):
    """
    Simulate a valid NovaPressureSensor reading.
    For a raw value of 14000, the conversion yields:
      pressure_psi = ((14000 - P_MIN) * (PSI_MAX - PSI_MIN) / (P_MAX - P_MIN)) + PSI_MIN
      hPa = pressure_psi * PSI_TO_HPA
    We check that _get_pressure returns approximately the expected value.
    """
    # Use a raw value chosen to produce a valid (<= 30) hPa reading.
    # For NovaPressureSensor, P_MIN = 1638, P_MAX = 14745.
    # With raw_value = 14000, pressure_psi = ((14000-1638)*30/(14745-1638))
    #   = (12362*30/13107) ≈ 28.29 psi, so hPa ≈ 28.29 * 68.9476 ≈ 1946.
    raw_value = 14000
    channel = DummyI2CChannel(raw_value)
    # Avoid actual sleep delays
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    # _get_pressure computes the conversion.
    expected_hpa = ((raw_value - sensor.P_MIN) * (sensor.PSI_MAX - sensor.PSI_MIN) / (sensor.P_MAX - sensor.P_MIN)) * sensor.PSI_TO_HPA
    pressure = sensor.pressure
    # Allow for a small floating-point tolerance.
    assert abs(pressure - expected_hpa) < 0.1
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_nova_pressure_sensor_valid_top_edge(monkeypatch):
    """
    Simulate a NovaPressureSensor reading on the top edge of the valid range.
    """
    # Use a raw value chosen to produce a valid (<= 30) hPa reading.
    # For NovaPressureSensor, P_MIN = 1638, P_MAX = 14745.
    # With raw_value = 14745, pressure_psi = ((14745-1638)*30/(14745-1638))
    #   = (13107*30/13107) ≈ 30 psi, so hPa ≈ 30 * 68.9476 ≈ 2068.
    raw_value = 14745
    channel = DummyI2CChannel(raw_value)
    # Avoid actual sleep delays
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    # _get_pressure computes the conversion.
    expected_hpa = ((raw_value - sensor.P_MIN) * (sensor.PSI_MAX - sensor.PSI_MIN) / (sensor.P_MAX - sensor.P_MIN)) * sensor.PSI_TO_HPA
    pressure = sensor.pressure
    # Allow for a small floating-point tolerance.
    assert abs(pressure - expected_hpa) < 0.1
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_nova_pressure_sensor_valid_bottom_edge(monkeypatch):
    """
    Simulate a NovaPressureSensor reading on the bottom edge of the valid range.
    """
    # Use a raw value chosen to produce a valid (<= 30) hPa reading.
    # For NovaPressureSensor, P_MIN = 1638, P_MAX = 14745.
    # With raw_value = 1639, pressure_psi = ((1639-1638)*30/(14745-1638))
    #   = (1*30/13107) ≈ 0.00023 psi, so hPa ≈ 0.00023 * 68.9476 ≈ 0.016.
    raw_value = 1639
    channel = DummyI2CChannel(raw_value)
    # Avoid actual sleep delays
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    # _get_pressure computes the conversion.
    expected_hpa = ((raw_value - sensor.P_MIN) * (sensor.PSI_MAX - sensor.PSI_MIN) / (sensor.P_MAX - sensor.P_MIN)) * sensor.PSI_TO_HPA
    pressure = sensor.pressure
    # Allow for a small floating-point tolerance.
    assert abs(pressure - expected_hpa) < 0.1
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_nova_pressure_sensor_invalid_top_edge(monkeypatch):
    """
    Simulate a NovaPressureSensor reading above the top edge of the valid range.
    """
    raw_value = 14746
    channel = DummyI2CChannel(raw_value)
    # Avoid actual sleep delays
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    pressure = sensor.pressure
    # Allow for a small floating-point tolerance.
    assert pressure == -1
    # We were not able to read the data initially
    assert sensor.ready is False
    assert sensor.cant_connect is True

def test_nova_pressure_sensor_invalid_bottom_edge(monkeypatch):
    """
    Simulate a NovaPressureSensor reading below the bottom edge of the valid range.
    """
    raw_value = 1637
    channel = DummyI2CChannel(raw_value)
    # Avoid actual sleep delays
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    pressure = sensor.pressure
    # Allow for a small floating-point tolerance.
    assert pressure == -1
    # We were not able to read the data initially
    assert sensor.ready is False
    assert sensor.cant_connect is True

def test_nova_pressure_sensor_triple(monkeypatch):
    """
    Test that _get_triple_pressure returns the median of three pressure readings.
    With a constant raw value, all three calls should yield the same converted hPa.
    """
    raw_value = 1700
    channel = DummyI2CChannel(raw_value)
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    
    expected_hpa = ((raw_value - sensor.P_MIN) * (sensor.PSI_MAX - sensor.PSI_MIN) / (sensor.P_MAX - sensor.P_MIN)) * sensor.PSI_TO_HPA
    triple = sensor.triple_pressure
    assert abs(triple - expected_hpa) < 0.1
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_nova_pressure_sensor_failure(monkeypatch):
    """
    Simulate a channel that fails to read (raises an exception).
    Both _get_pressure and _get_triple_pressure should then return -1.
    """
    channel = DummyI2CFailChannel()
    monkeypatch.setattr(time, "sleep", lambda x: None)
    sensor = NovaPressureSensor(channel)
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
    assert sensor.ready is False
    assert sensor.cant_connect is True

def test_nova_pressure_sensor_init_ready(monkeypatch):
    """
    Test the __init__ behavior of NovaPressureSensor.
    The constructor tries three times to set self.ready.
    (Note: this test exposes a quirk in the __init__ logic where raw values are
    used directly for validity.)
    """
    monkeypatch.setattr(time, "sleep", lambda x: None)
    channel = DummyI2CChannel(raw_value=1700)
    sensor = NovaPressureSensor(channel)
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_nova_pressure_sensor_custom_psi_max(monkeypatch):
    """
    Test NovaPressureSensor with a custom psi_max value.
    The same digital count should be interpreted differently based on PSI_MAX.
    """
    # Use a raw value halfway between P_MIN and P_MAX
    # This should read as 15 psi on a 30 psi sensor, but 50 psi on a 100 psi sensor
    raw_value = (NovaPressureSensor.P_MAX + NovaPressureSensor.P_MIN) // 2
    channel = DummyI2CChannel(raw_value)
    monkeypatch.setattr(time, "sleep", lambda x: None)

    resolution30 = 30 / (NovaPressureSensor.P_MAX - NovaPressureSensor.P_MIN) * NovaPressureSensor.PSI_TO_HPA  # expected resolution (30 psi over 13107 states)
    resolution100 = 100 / (NovaPressureSensor.P_MAX - NovaPressureSensor.P_MIN) * NovaPressureSensor.PSI_TO_HPA  # expected resolution (100 psi over 13107 states)
    
    # Test with 30 psi sensor (default)
    sensor_30psi = NovaPressureSensor(channel)
    pressure_30psi = sensor_30psi.pressure
    expected_30psi = (30 * (raw_value * 1.0 / (NovaPressureSensor.P_MAX + NovaPressureSensor.P_MIN))) * NovaPressureSensor.PSI_TO_HPA  # 15 psi * conversion factor

    assert abs(pressure_30psi - expected_30psi) < resolution30
    assert sensor_30psi.ready is True
    
    # Test with 100 psi sensor
    sensor_100psi = NovaPressureSensor(channel, psi_max=100)
    pressure_100psi = sensor_100psi.pressure
    expected_100psi = 50 * NovaPressureSensor.PSI_TO_HPA  # 50 psi * conversion factor

    assert abs(pressure_100psi - expected_100psi) < resolution100
    assert sensor_100psi.ready is True

def test_nova_pressure_sensor_custom_psi_max_edge(monkeypatch):
    """
    Test NovaPressureSensor with a custom psi_max value at the edge case.
    P_MAX should always read as PSI_MAX, regardless of what PSI_MAX is set to.
    """
    raw_value = NovaPressureSensor.P_MAX
    channel = DummyI2CChannel(raw_value)
    monkeypatch.setattr(time, "sleep", lambda x: None)

    resolution30 = 30 / (NovaPressureSensor.P_MAX - NovaPressureSensor.P_MIN) * NovaPressureSensor.PSI_TO_HPA  # expected resolution (30 psi over 13107 states)
    resolution100 = 100 / (NovaPressureSensor.P_MAX - NovaPressureSensor.P_MIN) * NovaPressureSensor.PSI_TO_HPA  # expected resolution (100 psi over 13107 states)
    
    # Test with 30 psi sensor (default)
    sensor_30psi = NovaPressureSensor(channel)
    pressure_30psi = sensor_30psi.pressure
    expected_30psi = 30 * NovaPressureSensor.PSI_TO_HPA  # 30 psi * conversion factor

    assert abs(pressure_30psi - expected_30psi) < resolution30
    assert sensor_30psi.ready is True
    
    # Test with 100 psi sensor
    sensor_100psi = NovaPressureSensor(channel, psi_max=100)
    pressure_100psi = sensor_100psi.pressure
    expected_100psi = 100 * NovaPressureSensor.PSI_TO_HPA  # 100 psi * conversion factor

    assert abs(pressure_100psi - expected_100psi) < resolution100
    assert sensor_100psi.ready is True

def test_nova_pressure_sensor_custom_psi_max_min(monkeypatch):
    """
    Test NovaPressureSensor with a custom psi_max value at the minimum case.
    P_MIN will read close to 0 psi, regardless of what PSI_MAX is set to.
    """
    raw_value = NovaPressureSensor.P_MIN + 1
    channel = DummyI2CChannel(raw_value)
    monkeypatch.setattr(time, "sleep", lambda x: None)

    resolution30 = 30 / (NovaPressureSensor.P_MAX - NovaPressureSensor.P_MIN) * NovaPressureSensor.PSI_TO_HPA  # expected resolution (30 psi over 13107 states)
    resolution100 = 100 / (NovaPressureSensor.P_MAX - NovaPressureSensor.P_MIN) * NovaPressureSensor.PSI_TO_HPA  # expected resolution (100 psi over 13107 states)
    
    # Test with 30 psi sensor (default)
    sensor_30psi = NovaPressureSensor(channel)
    pressure_30psi = sensor_30psi.pressure
    expected_30psi = resolution30  # First possible value

    assert abs(pressure_30psi - expected_30psi) < resolution30
    assert sensor_30psi.ready is True
    
    # Test with 100 psi sensor
    sensor_100psi = NovaPressureSensor(channel, psi_max=100)
    pressure_100psi = sensor_100psi.pressure
    expected_100psi = resolution100  # First possible value

    assert abs(pressure_100psi - expected_100psi) < resolution100
    assert sensor_100psi.ready is True

# -----------------------------------------
# Tests for MPRLSFile implementation
# -----------------------------------------

# Get file relative to the test file dir
PRESSURE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pressures.csv")

def test_mprlsfile_initialization():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"10.5\n20.3\n30.7\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.file_path == temp_filename
    assert sensor.data == [10.5, 20.3, 30.7]
    assert sensor.ready is True
    assert sensor.cant_connect is False
    os.remove(temp_filename)

def test_mprlsfile_empty_file():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == []
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
    assert sensor.ready is False
    assert sensor.cant_connect is True
    os.remove(temp_filename)

def test_mprlsfile_get_pressure():
    sensor = MPRLSFile(PRESSURE_FILE)
    #assert isinstance(sensor._get_pressure(), float)
    with open(PRESSURE_FILE, "r") as f:
        data = [float(line.strip()) for line in f.readlines()]
    for value in data:
        assert sensor.pressure == value

def test_mprlsfile_get_triple_pressure():
    sensor = MPRLSFile(PRESSURE_FILE)
    #assert isinstance(sensor._get_triple_pressure(), float)
    with open(PRESSURE_FILE, "r") as f:
        data = [float(line.strip()) for line in f.readlines()]
    for i in range(((len(data)-1) % 3) + 1):
        expected_values=[]
        for j in range(i*3, (i*3)+3):
            if j<len(data):
                expected_values+=[data[j]]
            else:
                expected_values+=[-1]
        assert sensor.triple_pressure == sorted(expected_values)[1]  # Median calculation

def test_mprlsfile_triple_pressure_eof():
    """Even if we reach the end of file, we should still return the median of the first pressures"""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"10.5\n30.7\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == [10.5, 30.7]
    assert sensor.triple_pressure == 20.6
    assert sensor.ready is True
    assert sensor.cant_connect is False
    os.remove(temp_filename)

def test_mprlsfile_triple_pressure_handles_all_invalid_readings():
    """Even if we reach the end of file, we should still return the median of the first pressures"""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"-1\n-1\n-1\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == [-1, -1, -1]
    assert sensor.triple_pressure == -1
    assert sensor.ready is True
    assert sensor.cant_connect is False
    os.remove(temp_filename)

def test_mprlsfile_corrupted_data():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"10.5\nINVALID\n30.7\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == []  # Should handle parsing failure gracefully
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
    assert sensor.ready is False
    assert sensor.cant_connect is True
    os.remove(temp_filename)

# -----------------------------------------
# Tests for MockPressureSensorStatic
# -----------------------------------------

def test_mock_pressure_sensor_static():
    sensor = MockPressureSensorStatic(pressure=15.0, triple_pressure=16.0)
    assert sensor.pressure == 15.0
    assert sensor.triple_pressure == 16.0
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_mock_pressure_sensor_default_triple_pressure():
    sensor = MockPressureSensorStatic(pressure=20.0)
    assert sensor.pressure == 20.0
    assert sensor.triple_pressure == 20.0  # Defaults to same as pressure
    assert sensor.ready is True
    assert sensor.cant_connect is False

def test_mock_pressure_sensor_no_connection():
    sensor = MockPressureSensorStatic(pressure=-1, triple_pressure=-1)
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
    assert sensor.ready is False
    assert sensor.cant_connect is True

def test_mock_pressure_sensor_partial_connection():
    sensor = MockPressureSensorStatic(pressure=10.0, triple_pressure=-1)
    assert sensor.pressure == 10.0
    assert sensor.triple_pressure == -1
    assert sensor.ready is False
    assert sensor.cant_connect is True

def test_mock_pressure_sensor_changing_values():
    sensor = MockPressureSensorStatic(pressure=5.0, triple_pressure=7.0)
    assert sensor.pressure == 5.0
    assert sensor.triple_pressure == 7.0
    
    sensor.pressure = 8.5  # Simulating a change in pressure
    sensor.triple_pressure = 9.2
    
    assert sensor.pressure == 5.0
    assert sensor.triple_pressure == 7.0

    assert sensor.ready is True
    assert sensor.cant_connect is False


# -----------------------------------------
# Tests for MCP9600Thermocouple
# -----------------------------------------

def test_MCP9600_no_multiplexer():
    """
    When no multiplexer_channel is provided, the sensor should mark itself as unable to connect.
    """
    sensor = MCP9600Thermocouple(multiplexer_channel=None)
    assert sensor.cant_connect is True
    assert sensor.temperature == -1
    assert sensor.triple_temperature == -1

def test_MCP9600_normal(monkeypatch):
    """
    Test normal operation by simulating a sensor that returns constant pressure.
    We override the adafruit_mprls.MCP9600 class so that our DummyNormalAdafruitMCP9600 is used.
    """
    # Dummy adafruit mprls that simulates a working sensor returning temperaturess.
    class DummyNormalAdafruitMCP9600:
        def __init__(self, multiplexer_channel):
            self._temperatures = [10.0, 10.0, 90.0, 40.0]
            self._index = 0

        @property
        def temperature(self):
            try:
                value = self._temperatures[self._index]
            except IndexError:
                value = self._temperatures[-1]
            self._index += 1
            return value

    # Dummy module to stand in for adafruit_mprls.
    class DummyModule:
        MCP9600 = DummyNormalAdafruitMCP9600

    # Patch the module-level adafruit_mprls variable so that __init__ can create our dummy sensor.
    import pi.MPRLS as mprls_module
    monkeypatch.setattr(mprls_module, "adafruit_mcp9600", DummyModule)

    dummy_line = object()  # any dummy multiplexer line
    sensor = MCP9600Thermocouple(dummy_line)

    assert sensor.cant_connect is False
    # Single temperature reading should return 10.0 C -> 283.15 K.
    assert sensor.temperature == 283.15
    # Triple pressure reading calls the sensor three times, so the median of [10.0, 90.0, 40.0] is 40.0 -> 313.15
    assert sensor.triple_temperature == 313.15

def test_MCP9600_exception(monkeypatch):
    """
    Simulate a sensor that always raises an exception on reading.
    Both temperature and triple_temperature should return -1.
    """
    # Dummy sensor that always fails when reading pressure.
    class DummyFailAdafruitMCP9600:
        def __init__(self, multiplexer_channel):
            pass

        @property
        def temperature(self):
            raise Exception("Simulated sensor error")

    class DummyModule:
        # Return an instance of the failing sensor.
        MCP9600 = lambda multiplexer_channel: DummyFailAdafruitMCP9600(multiplexer_channel)

    # Patch the module-level adafruit_mprls variable so that __init__ can create our dummy sensor.
    import pi.MPRLS as mprls_module
    monkeypatch.setattr(mprls_module, "adafruit_mcp9600", DummyModule)

    dummy_line = object()
    sensor = MCP9600Thermocouple(dummy_line)
    # In case of exceptions, both single and triple readings should return -1.
    assert sensor.temperature == -1
    assert sensor.triple_temperature == -1
    # We connected, but the sensor is raising errors
    assert sensor.cant_connect is False

def test_MCP9600_partial(monkeypatch):
    """
    Simulate a sensor that returns a valid value on the first call, then fails on the second,
    and returns another valid value on the third call. The triple reading should compute the median
    over the valid readings.
    """
    class DummyRoughAdafruitMCP9600:
        def __init__(self, multiplexer_channel):
            self._values = [10.0, "raise", 50.0]
            self._index = 0

        @property
        def temperature(self):
            val = self._values[self._index]
            self._index += 1
            if val == "raise":
                raise Exception("Simulated sensor error")
            return val

    class DummyModule:
        MCP9600 = DummyRoughAdafruitMCP9600

    # Patch the module-level adafruit_mprls variable so that __init__ can create our dummy sensor.
    import pi.MPRLS as mprls_module
    monkeypatch.setattr(mprls_module, "adafruit_mcp9600", DummyModule)

    dummy_line = object()
    sensor = MCP9600Thermocouple(dummy_line)
    # The triple reading collects pressures: 10.0 C, (skips error), 50.0 C.
    # The median of [10.0, 50.0] C is 30.0 -> 303.15 K.
    assert sensor.triple_temperature == 303.15

def test_MCP9600_no_lib(monkeypatch):
    """Simulate a sensor that has no library available."""

    dummy_line = object()
    sensor = MCP9600Thermocouple(dummy_line)
    assert sensor.cant_connect == True
