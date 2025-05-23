import time
import pytest
import tempfile
from warnings import warn

_original_time = time.time

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))


from pi.processes.process import Process, PlumbingState
from pi.processes.process_vent_hot_air import VentHotAir
from pi.processes.process_log_pressures import LogPressures

from pi.RTC import RTCFile
from pi.MPRLS import MockPressureSensorStatic, MockPressureTemperatureSensorStatic, MockTimeDependentTemperatureSensor
from pi.multiprint import MockMultiPrinter

from tests.test_Tank import MockValve



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
    Process.set_plumbing_state(PlumbingState.READY)

@pytest.fixture
def mock_log_process() -> LogPressures:
    log_Process = LogPressures()
    log_Process.set_canister_pressure_sensor(MockPressureSensorStatic(100))
    log_Process.set_dpv_temperature(MockPressureTemperatureSensorStatic(100, 350))
    log_Process.set_pressure_sensors([MockPressureTemperatureSensorStatic(100, 110), MockPressureTemperatureSensorStatic(100, 110), MockPressureTemperatureSensorStatic(100, 110)])
    return log_Process

@pytest.fixture
def vent_hot_air_instance() -> VentHotAir:
    """Fixture to create an instance of VentHotAir."""
    return VentHotAir()

def test_initialize_process(setup_process, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process. Verifies the fixtures"""
    
    assert Process.get_multiprint() == mock_multiprint
    assert Process.get_rtc() == mock_rtc
    assert Process.get_output_log() == mock_log
    assert Process.get_output_pressures() == mock_pressures_log
    assert Process.is_ready()
    assert Process.can_log()

def test_run_not_ready(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir):
    """
    If Process.is_ready() is False, run() should return False and log a warning.
    """
    monkeypatch.setattr(Process, "is_ready", lambda: False)
    
    result = vent_hot_air_instance.run()

    assert result is False
    # Check that a warning message was logged via pform on the output log
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tProcess is not ready for VentHotAir!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_general_failure(setup_process, vent_hot_air_instance: VentHotAir):
    """
    If nothing is set, initialize() should return False and log a warning.
    """
    result = vent_hot_air_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tLogPressures not set for VentHotAir! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_all_valves(setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """
    If All Valves are set, initialize() should return False and log a warning.
    """
    vent_hot_air_instance.set_log_pressures(mock_log_process)

    result = vent_hot_air_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tAll Valves not set for VentHotAir! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_main_valve(setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """
    If no main_valve is set, initialize() should return False and log a warning.
    """
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)

    result = vent_hot_air_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tMain Valve not set for VentHotAir! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_static_valve(setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """
    If no static_valve is set, initialize() should return False and log a warning.
    """
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)

    result = vent_hot_air_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tStatic Valve not set for VentHotAir! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_dpv_temp_sensor(setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """
    If no dpv temp sensor is set, initialize() should return False and log a warning.
    """
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)

    result = vent_hot_air_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tDPV Temperature Sensor not set for VentHotAir! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_total_success(setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """
    If everything is set and the temp_thresh was not reached, should continue and log that we're NOT here because of it
    """
    mock_log_process.set_temp_thresh_reached(False)
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockPressureTemperatureSensorStatic(pressure=-1, temperature=350)
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    result = vent_hot_air_instance.initialize()

    assert result is True
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tWe are NOT here because TEMP_THRESH_REACHED!") in Process.multiprint.logs[Process.output_log.name]

    mock_log_process.set_temp_thresh_reached(False) # Reset Class variable for future tests

def test_initialize_temp_thresh_reached(setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """
    If everything is set, but the temp_thresh was reached, should continue and log that we're here because of it
    """
    mock_log_process.set_temp_thresh_reached(True)
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockPressureTemperatureSensorStatic(pressure=-1, temperature=350)
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    result = vent_hot_air_instance.initialize()

    assert result is True
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tWe are here because TEMP_THRESH_REACHED!") in Process.multiprint.logs[Process.output_log.name]

    mock_log_process.set_temp_thresh_reached(False) # Reset Class variable for future tests

def test_cleanup_no_error(setup_process, vent_hot_air_instance: VentHotAir):
    """
    Since cleanup() is a no-op, calling it should not produce errors.
    """
    # Just ensure that calling cleanup() does not raise an exception.
    vent_hot_air_instance.cleanup()
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tFinished VentHotAir.") in Process.multiprint.logs[Process.output_log.name]

# -----------------------------------------
# Cyclomatic Complexity Path Tests
# -----------------------------------------

def test_dpv_temp_increasing_abort(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test ΔPtank ≈ 0."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 420),
        (16000, 450)
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert any("Temperature is increasing (" in log for log in logs)
    assert any("Aborting Venting!" in log for log in logs)

def test_dpv_temp_lessthan_target(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp less than target temperature. Should close VMain and VStatic without checking change in temperature"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 370),
        (16000, 350)
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("Temperature is increasing (" in log for log in logs)
    assert not any("Aborting Venting!" in log for log in logs)
    assert any(f"DPV Temperature (370K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)

def test_dpv_temp_decreasing(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp decreasing until it reaches T_VENT_TARGET"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 600),
        (16000, 500),
        (17000, 400),
        (18000, 300)
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("Temperature is increasing (" in log for log in logs)
    assert not any("Aborting Venting!" in log for log in logs)
    assert any(f"DPV Temperature (300K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)

def test_dpv_temp_same(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp staying the same until t_vent time elapses."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 600),
        (16000, 600),
        (17000, 600),
        (18000, 600),
        (19000, 600),
        (20000, 600),
        (21000, 200) #should be ignored, since t_vent has already elapsed by this time
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("Temperature is increasing (" in log for log in logs)
    assert not any("Aborting Venting!" in log for log in logs)
    assert not any(f"DPV Temperature (200K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)
    assert any("Closed Main Valve and Static Valve." in log for log in logs) 

# -----------------------------------------
# Tests for triple pressure
# -----------------------------------------
def test_triple_dpv_temp_lessthan_target(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp staying the same until t_vent time elapses."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 200),
        (16000, 600),
        (17000, 600),
    ], triple_time_temp_pairs= [
        (15000, 220),
        (16000, 230),
        (17000, 240),
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("Temperature is increasing (" in log for log in logs)
    assert not any("Aborting Venting!" in log for log in logs)
    assert not any("DPV Temperature (200K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)
    assert any("Closed Main Valve and Static Valve." in log for log in logs) 

def test_triple_dpv_temp_increasing(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp staying the same until t_vent time elapses."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 400),
        (16000, 500),
        (17000, 600),
    ], triple_time_temp_pairs= [
        (15000, 420),
        (16000, 460),
        (17000, 540),
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert any("Temperature is increasing (420.0K -> 460.0K over 0.5s = 80.00K/s)! Aborting Venting!" in log for log in logs)
    assert any("Closed Main Valve and Static Valve." in log for log in logs) 

# -----------------------------------------
# Tests for unconnected sensors / missing values
# -----------------------------------------

def test_unconnected_thermocouple(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """T_thermocouple <= T_ventTarget shouldn't triger if T_thermocouple is -1"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, -1),
    ], triple_time_temp_pairs= [
        (15000, -1),
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("DPV Temperature (-1K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)
    
def test_unconnected_triple_thermocouple(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """ T_thermocouple <= T_ventTarget shouldn't triger if the first temperature < T_ventTarget but then the sensor disconnects"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 200),
    ], triple_time_temp_pairs= [
        (15000, -1),
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("DPV Temperature (-1K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)
    assert not any("DPV Temperature (200K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)

def test_unconnected_thermocouple_delta(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp staying the same until t_vent time elapses."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 500),
        (16000, -1),
        (17000, -1)
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("DPV Temperature (-1K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)
    assert not any("Temperature is increasing (" in log for log in logs)
    assert not any("Aborting Venting!" in log for log in logs)

def test_unconnected_triple_thermocouple_delta(monkeypatch, setup_process, vent_hot_air_instance: VentHotAir, mock_log_process: LogPressures):
    """t_small test DPV temp staying the same until t_vent time elapses."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    mock_log_process.set_temp_thresh_reached(False) # Did not reach thresholds
    vent_hot_air_instance.set_log_pressures(mock_log_process)
    main_valve = MockValve(1, "Main")
    dynamic_valve = MockValve(2, "Dynamic")
    static_valve = MockValve(3, "Static")
    valve_1 = MockValve(4, "1")
    valve_2 = MockValve(5, "2")
    all_valves = [main_valve, dynamic_valve, static_valve, valve_1, valve_2]
    vent_hot_air_instance.set_all_valves(all_valves)
    vent_hot_air_instance.set_main_valve(main_valve)
    vent_hot_air_instance.set_static_valve(static_valve)
    dpv_temp = MockTimeDependentTemperatureSensor(rtc=mock_rtc, time_temp_pairs=[
        (15000, 500),
        (16000, -1),
        (17000, 510),
        (18000, 520)
    ], triple_time_temp_pairs= [
        (15000, 510),
        (16000, -1),
        (17000, -1)
    ])
    vent_hot_air_instance.set_dpv_temperature_sensor(dpv_temp)

    vent_hot_air_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]

    assert not any("DPV Temperature (-1K) is less than VENT_TARGET (380K). Finished Venting." in log for log in logs)
    assert not any("Temperature is increasing (" in log for log in logs)
    assert not any("Aborting Venting!" in log for log in logs)