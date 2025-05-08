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
from pi.MPRLS import MockPressureSensorStatic, MockPressureTemperatureSensorStatic
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

def initalize_sensors(t1, t2, t3, t4):
    # easier way to initialize tank, canister, and dpv mock pressureTemperature objects
    # takes in order pressures to set for: tank1, tank2, tank3, dpv
    # does not accept a value for canister sensor since none of the tests involve changing the value
    sensor1 = MockPressureTemperatureSensorStatic(100, t1)
    sensor2 = MockPressureTemperatureSensorStatic(200, t2)
    sensor3 = MockPressureTemperatureSensorStatic(300, t3)

    canister_sensor = MockPressureSensorStatic(400)
    
    dpv_temp_sensor = MockPressureTemperatureSensorStatic(1000, t4)
    return [sensor1, sensor2, sensor3], dpv_temp_sensor, canister_sensor

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

def test_initialize_failure_total(setup_process, log_pressures_instance, mock_multiprint, mock_rtc, mock_log):
    """
    If pressure_sensors is None, run() should return False and log a warning.
    """
    result = log_pressures_instance.run()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tPressure Sensors not set for LogPressures!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_failure_dpv(setup_process, log_pressures_instance, mock_multiprint, mock_rtc, mock_log):
    """
    If dpv temp sensor is None, run() should return False and log a warning.
    """
    # Create three dummy pressure sensors with known pressures
    sensor1 = MockPressureSensorStatic(100)
    sensor2 = MockPressureSensorStatic(200)
    sensor3 = MockPressureSensorStatic(300)
    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3])

    result = log_pressures_instance.run()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tDPV Temperature Sensor not set for LogPressures!") in Process.multiprint.logs[Process.output_log.name]


def test_initialize_failure_canister(setup_process, log_pressures_instance: LogPressures, mock_multiprint, mock_rtc, mock_log):
    """
    If canister_pressure_sensor is None, run() should return False and log a warning.
    """
    # Create three dummy pressure sensors with known pressures
    sensor1 = MockPressureSensorStatic(100)
    sensor2 = MockPressureSensorStatic(200)
    sensor3 = MockPressureSensorStatic(300)
    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3])

    dpv_temp_sensor = MockPressureTemperatureSensorStatic(1000, 350)
    log_pressures_instance.set_dpv_temperature(dpv_temp_sensor)

    result = log_pressures_instance.run()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tCanister Pressure Sensor not set for LogPressures!") in Process.multiprint.logs[Process.output_log.name]

def test_run_success(setup_process, log_pressures_instance: LogPressures, mock_multiprint, mock_rtc, mock_pressures_log):
    """
    Test that execute() constructs the proper output string from the sensor pressures.
    """
    # Create three dummy pressure sensors with known pressures
    pressure_sensors, dpv, canister_sensor = initalize_sensors(340, 340, 340, 350)

    log_pressures_instance.set_pressure_sensors(pressure_sensors)
    log_pressures_instance.set_dpv_temperature(dpv)
    log_pressures_instance.set_canister_pressure_sensor(canister_sensor)
    
    res = log_pressures_instance.run() 
    assert res == True
    
    # The expected output string: "<timestamp>,100,200,300,"
    expected_output = f"{Process.rtc.getTPlusMS()},{pressure_sensors[0].pressure},{pressure_sensors[1].pressure},{pressure_sensors[2].pressure},{canister_sensor.pressure},"
    assert (expected_output) in Process.multiprint.logs[Process.output_pressures.name]

def test_runtime_less_than_5ms(setup_process, log_pressures_instance, mock_multiprint, mock_rtc, mock_pressures_log):
    """Test the execution time with 3 pressure sensors"""
    pressure_sensors, dpv, canister_sensor = initalize_sensors(100, 200, 300, 350)
 
    log_pressures_instance.set_pressure_sensors(pressure_sensors)
    log_pressures_instance.set_dpv_temperature(dpv)
    log_pressures_instance.set_canister_pressure_sensor(canister_sensor)

    import time
    start = time.perf_counter()
    log_pressures_instance.run()
    end = time.perf_counter()
    
    runtime_ms = (end - start) * 1000  # Convert seconds to milliseconds
    assert runtime_ms < 5, f"Runtime was {runtime_ms:.2f} ms, expected less than 5 ms"

def test_temp_thresh_previously_reached(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """Tests that if max temperature was previously reached, log_pressures just records pressure data"""
    sensors, dpv, sensor_canister = initalize_sensors(100, 200, 430, 350)

    log_pressures_instance.set_pressure_sensors(sensors)
    log_pressures_instance.set_dpv_temperature(dpv)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance._temp_thresh_reached = True

    assert log_pressures_instance.run() == True

    expected_output = f"{Process.rtc.getTPlusMS()},{sensors[0].pressure},{sensors[1].pressure},{sensors[2].pressure},{sensor_canister.pressure},"
    assert (expected_output) in Process.multiprint.logs[Process.output_pressures.name]

def test_over_temp_thresh_anytime_dpv(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """ Tests that if the temperature in the dpv goes about T_anytime, process stops and begins only recording pressures"""    
    sensors, dpv, sensor_canister = initalize_sensors(100, 200, 300, 880)
    
    log_pressures_instance.set_pressure_sensors(sensors)
    log_pressures_instance.set_dpv_temperature(dpv)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance.set_currently_sampling = False
    log_pressures_instance._temp_thresh_reached = False

    log_pressures_instance.run()

    assert log_pressures_instance.get_temp_thresh_reached() == True
    
    first_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tDPV Temperature may be over T_ANYTIME: " + str(dpv.temperature) + "K. Running triple check...")
    assert first_log in Process.multiprint.logs[Process.output_log.name]

    second_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTEMP_THRESH_REACHED! DPV Temperature over T_ANYTIME: " + str(dpv.temperature) + "K, triple checked!")
    assert second_log in Process.multiprint.logs[Process.output_log.name]  
    
def test_over_temp_thresh_sample_false(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """Tests that if sample tanks get above T_anytime, process stops and begins only recording pressures"""
    sensors, dpv, sensor_canister = initalize_sensors(100, 200, 500, 200)

    log_pressures_instance.set_pressure_sensors(sensors)
    log_pressures_instance.set_dpv_temperature(dpv)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance.set_currently_sampling(False)
    log_pressures_instance.set_temp_thresh_reached(False)

    log_pressures_instance.run()

    first_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tA temperature sensor may be over T_ANYTIME: " + f"[{sensors[0].temperature}, {sensors[1].temperature}, {sensors[2].temperature}]K. Running triple check...")
    second_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTEMP_THRESH_REACHED! A temperature sensor is over T_ANYTIME: " + str(sensors[2].temperature) + "K, triple checked!")
    assert first_log in Process.multiprint.logs[Process.output_log.name]
    assert second_log in Process.multiprint.logs[Process.output_log.name]

def test_over_temp_thresh_sample_true(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """Tests that if tanks reach T_sample while sampling, process stops and begins only recording pressures"""
    sensors, dpv, sensor_canister = initalize_sensors(100, 200, 410, 200)

    log_pressures_instance.set_pressure_sensors(sensors)
    log_pressures_instance.set_dpv_temperature(dpv)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance.set_currently_sampling(True)
    log_pressures_instance.set_temp_thresh_reached(False)

    log_pressures_instance.run()

    first_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tA temperature sensor may be over T_SAMPLE: " + f"[{sensors[0].temperature}, {sensors[1].temperature}, {sensors[2].temperature}]K. Running triple check...")
    second_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTEMP_THRESH_REACHED! A temperature sensor is over T_SAMPLE: " + str(sensors[2].temperature) + "K, triple checked!")
    assert first_log in Process.multiprint.logs[Process.output_log.name]
    assert second_log in Process.multiprint.logs[Process.output_log.name]

def test_over_temp_thresh_sample_uses_triple_pressure(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """Tests decisions are made with triple pressure while sampling"""
    sensor1 = MockPressureTemperatureSensorStatic(1000, 100)
    sensor2 = MockPressureTemperatureSensorStatic(1000, 800, triple_temperature=100.2)
    sensor3 = MockPressureTemperatureSensorStatic(1000, 390)

    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3])

    dpv_temp_sensor = MockPressureTemperatureSensorStatic(1000, 390)
    log_pressures_instance.set_dpv_temperature(dpv_temp_sensor)

    sensor_canister = MockPressureSensorStatic(400)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance.set_currently_sampling(True)
    log_pressures_instance.set_temp_thresh_reached(False)

    log_pressures_instance.run()

    first_log =  ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tA temperature sensor may be over T_SAMPLE: " + f"[{sensor1.temperature}, {sensor2.temperature}, {sensor3.temperature}]K. Running triple check...") 
    second_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTEMP_THRESH_REACHED! A temperature sensor is over T_SAMPLE: " + str(sensor2.triple_temperature) + "K, triple checked!")
 
    assert first_log in Process.multiprint.logs[Process.output_log.name]
    assert second_log not in Process.multiprint.logs[Process.output_log.name]

    assert log_pressures_instance.get_temp_thresh_reached() == False

def test_over_temp_thres_anytime_uses_triple_pressure(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """Tests decisions are made with triple pressure at sample tanks while not sampling"""
    sensor1 = MockPressureTemperatureSensorStatic(1000, 100)
    sensor2 = MockPressureTemperatureSensorStatic(1000, 200)
    sensor3 = MockPressureTemperatureSensorStatic(1000, 810, triple_temperature = 100.1)

    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3])

    dpv_temp_sensor = MockPressureTemperatureSensorStatic(1000, -1)
    log_pressures_instance.set_dpv_temperature(dpv_temp_sensor)

    sensor_canister = MockPressureSensorStatic(400)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance.set_currently_sampling(False)
    log_pressures_instance.set_temp_thresh_reached(False)

    log_pressures_instance.run()   

    first_log =  ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tA temperature sensor may be over T_ANYTIME: " + f"[{sensor1.temperature}, {sensor2.temperature}, {sensor3.temperature}]K. Running triple check...") 
    second_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTEMP_THRESH_REACHED! A temperature sensor is over T_ANYTIME: " + str(sensor3.triple_temperature) + "K, triple checked!")
    assert first_log in Process.multiprint.logs[Process.output_log.name]
    assert second_log not in Process.multiprint.logs[Process.output_log.name]

    assert log_pressures_instance.get_temp_thresh_reached() == False

def test_over_temp_thres_anytime_dpv_uses_triple_pressure(setup_process, log_pressures_instance: LogPressures,  mock_multiprint, mock_rtc, mock_pressures_log):
    """Tests decisions are made with triple pressure at dpv"""
    sensor1 = MockPressureTemperatureSensorStatic(1000, 100)
    sensor2 = MockPressureTemperatureSensorStatic(1000, 200)
    sensor3 = MockPressureTemperatureSensorStatic(1000, 110)

    log_pressures_instance.set_pressure_sensors([sensor1, sensor2, sensor3])

    dpv_temp_sensor = MockPressureTemperatureSensorStatic(1000, 800, triple_temperature = 100.1)
    log_pressures_instance.set_dpv_temperature(dpv_temp_sensor)

    sensor_canister = MockPressureSensorStatic(400)
    log_pressures_instance.set_canister_pressure_sensor(sensor_canister)

    log_pressures_instance.set_currently_sampling(False)
    log_pressures_instance.set_temp_thresh_reached(False)

    log_pressures_instance.run()   

    first_log =  ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tDPV Temperature may be over T_ANYTIME: " + str(dpv_temp_sensor.temperature) + "K. Running triple check...") 
    second_log = ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTEMP_THRESH_REACHED! DPV Temperature over T_ANYTIME: " + str(dpv_temp_sensor.triple_temperature) + "K, triple checked!")
    
    assert log_pressures_instance.get_temp_thresh_reached() == False
    assert first_log in Process.multiprint.logs[Process.output_log.name]
    assert second_log not in Process.multiprint.logs[Process.output_log.name]


def test_cleanup_no_error(setup_process, log_pressures_instance):
    """
    Since cleanup() is a no-op, calling it should not produce errors.
    """
    # Just ensure that calling cleanup() does not raise an exception.
    log_pressures_instance.cleanup()
