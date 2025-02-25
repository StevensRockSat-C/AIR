import pytest
import sys
sys.path.append('../')

import tempfile
import os
import time
from pi.MPRLS import MPRLSFile, MPRLSWrappedSensor, NovaPressureSensor

# -----------------------------------------
# Dummy implementations for MPRLSWrappedSensor tests
# -----------------------------------------

# A dummy sensor to simulate a working MPRLS sensor
class DummyMPRLSSensor:
    def __init__(self, pressures):
        # pressures is a list of values that will be returned sequentially
        self._pressures = pressures
        self._index = 0

    @property
    def pressure(self):
        try:
            value = self._pressures[self._index]
        except IndexError:
            value = self._pressures[-1]
        self._index += 1
        return value

# A dummy sensor that raises an exception when reading pressure
class DummyFailSensor:
    @property
    def pressure(self):
        raise Exception("Simulated sensor error")

# A dummy sensor that fails on one call in a sequence (for triple reading)
class DummyPartialSensor:
    def __init__(self):
        self._values = [15.0, "raise", 17.0]
        self._index = 0

    @property
    def pressure(self):
        val = self._values[self._index]
        self._index += 1
        if val == "raise":
            raise Exception("Simulated error")
        return val

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

def test_nova_pressure_sensor_init_ready(monkeypatch):
    """
    Test the __init__ behavior of NovaPressureSensor.
    The constructor tries three times to set self.ready.
    By simulating a channel that returns a raw value low enough (e.g. 5),
    is_pressure_valid will return True (since 5 > 0 and 5 <= 30),
    so ready should be set to True.
    (Note: this test exposes a quirk in the __init__ logic where raw values are
    used directly for validity.)
    """
    class DummyI2CChannelReady:
        def readfrom_into(self, address, buf):
            # Simulate a raw value of 5 (which is <= PSI_MAX)
            buf[0] = 0
            buf[1] = 5  # raw value = 5
    monkeypatch.setattr(time, "sleep", lambda x: None)
    channel = DummyI2CChannelReady()
    sensor = NovaPressureSensor(channel)
    assert sensor.ready is True

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
    os.remove(temp_filename)

def test_mprlsfile_empty_file():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == []
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
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

def test_mprlsfile_corrupted_data():
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"10.5\nINVALID\n30.7\n")
        temp_filename = temp_file.name
    
    sensor = MPRLSFile(temp_filename)
    assert sensor.data == []  # Should handle parsing failure gracefully
    assert sensor.pressure == -1
    assert sensor.triple_pressure == -1
    os.remove(temp_filename)
