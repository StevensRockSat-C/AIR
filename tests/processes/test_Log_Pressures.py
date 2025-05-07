import os
import time
import pytest
import tempfile
from warnings import warn

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pi.processes.process_log_pressures import LogPressures
from pi.RTC import RTCFile
from pi.MPRLS import MockPressureSensorStatic
from pi.multiprint import MockMultiPrinter

from pi.processes.process import Process

@pytest.fixture
def mock_multiprint(monkeypatch):
    """Mock MultiPrinter to capture printed messages."""

    mock_printer = MockMultiPrinter()
    return mock_printer

@pytest.fixture
def mock_rtc(monkeypatch):
    """Mock RTC to provide fixed timestamps."""
    
    mock_rtc = RTCFile(200 * 1000)
    fake_time = 230.0  # seconds; simulating current time
    monkeypatch.setattr(time, "time", lambda: fake_time) # Force time to be fake_time, not incrementing
    return mock_rtc

@pytest.fixture
def mock_log():
    temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=True)
    yield temp_file
    temp_file.close()

@pytest.fixture
def mock_pressures_log():
    temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=True)
    yield temp_file
    temp_file.close()

@pytest.fixture
def setup_process(monkeypatch, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Setup the initial pressure check."""

    Process.set_multiprint(mock_multiprint)
    Process.set_rtc(mock_rtc)
    Process.set_output_log(mock_log)
    Process.set_output_pressures(mock_pressures_log)

@pytest.fixture
def log_pressures_instance() -> LogPressures:
    """Fixture to create an instance of InitialPressureCheck."""
    return LogPressures()

def test_initialize_process(setup_process, log_pressures_instance: LogPressures, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process. Verifies the fixtures"""
    
    assert Process.get_multiprint() == mock_multiprint
    assert Process.get_rtc() == mock_rtc
    assert Process.get_output_log() == mock_log
    assert Process.get_output_pressures() == mock_pressures_log
    assert Process.is_ready()
    assert Process.can_log()

def test_run_not_ready(monkeypatch, setup_process, log_pressures_instance: LogPressures):
    """
    If Process.is_ready() is False, run() should return False and log a warning.
    """
    monkeypatch.setattr(Process, "is_ready", lambda: False)
    
    result = log_pressures_instance.run()

    assert result is False
    # Check that a warning message was logged via pform on the output log
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tProcess is not ready for LogPressures!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_failure(setup_process, log_pressures_instance, mock_multiprint, mock_rtc, mock_log):
    """
    If pressure_sensors is None, run() should return False and log a warning.
    """
    result = log_pressures_instance.run()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tPressure Sensors not set for LogPressures!") in Process.multiprint.logs[Process.output_log.name]

def test_run_success(setup_process, log_pressures_instance, mock_multiprint, mock_rtc, mock_pressures_log):
    """
    Test that execute() constructs the proper output string from the sensor pressures.
    """
    # Create three dummy pressure sensors with known pressures
    sensor1 = MockPressureSensorStatic(100)
    sensor2 = MockPressureSensorStatic(200)
    sensor3 = MockPressureSensorStatic(300)
    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3])
    
    res = log_pressures_instance.run() 
    assert res == True
    
    # The expected output string: "<timestamp>,100,200,300,"
    expected_output = f"{Process.rtc.getTPlusMS()},{sensor1.pressure},{sensor2.pressure},{sensor3.pressure},"
    assert (expected_output) in Process.multiprint.logs[Process.output_pressures.name]

def test_runtime_less_than_5ms(setup_process, log_pressures_instance):
    """Test the execution time with 5 pressure sensors"""
    sensor1 = MockPressureSensorStatic(100)
    sensor2 = MockPressureSensorStatic(200)
    sensor3 = MockPressureSensorStatic(300)
    sensor4 = MockPressureSensorStatic(400)
    sensor5 = MockPressureSensorStatic(500)
    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3, sensor4, sensor5])

    import time
    start = time.perf_counter()
    log_pressures_instance.run()
    end = time.perf_counter()
    
    runtime_ms = (end - start) * 1000  # Convert seconds to milliseconds
    assert runtime_ms < 5, f"Runtime was {runtime_ms:.2f} ms, expected less than 5 ms"

def test_cleanup_no_error(setup_process, log_pressures_instance):
    """
    Since cleanup() is a no-op, calling it should not produce errors.
    """
    # Just ensure that calling cleanup() does not raise an exception.
    log_pressures_instance.cleanup()
