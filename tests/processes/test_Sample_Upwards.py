import os
import time
import pytest
import tempfile
from warnings import warn

import sys
sys.path.append('../../')

from pi.processes.process import Process
from pi.processes.process_sample_upwards import SampleUpwards
from pi.processes.process_log_pressures import LogPressures

from pi.RTC import RTCFile
from pi.MPRLS import MockPressureSensorStatic
from pi.multiprint import MockMultiPrinter
from pi.collection import Collection
from pi.tank import Tank

from tests.test_Tank import MockValve

class MockTankWithStaticPressure(Tank):
    def __init__(self, name, pressure_single=800, pressure_triple=None):
        if pressure_triple == None: pressure_triple = pressure_single
        super().__init__(name, MockPressureSensorStatic(pressure_single, pressure_triple))
        self.valve = MockValve(10, name)

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
def sample_upwards_instance() -> SampleUpwards:
    """Fixture to create an instance of InitialPressureCheck."""
    return SampleUpwards()

def test_initialize_process(setup_process, sample_upwards_instance: SampleUpwards, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process. Verifies the fixtures"""
    
    assert Process.get_multiprint() == mock_multiprint
    assert Process.get_rtc() == mock_rtc
    assert Process.get_output_log() == mock_log
    assert Process.get_output_pressures() == mock_pressures_log
    assert Process.is_ready()
    assert Process.can_log()

def test_run_not_ready(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards):
    """
    If Process.is_ready() is False, run() should return False and log a warning.
    """
    monkeypatch.setattr(Process, "is_ready", lambda: False)
    
    result = sample_upwards_instance.run()

    assert result is False
    # Check that a warning message was logged via pform on the output log
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tProcess is not ready for SampleUpwards!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_general_failure(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If nothing is set, initialize() should return False and log a warning.
    """
    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tLogPressures not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_collections(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If no collections are set, initialize() should return False and log a warning.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tCollections not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_main_valve(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If no main_valve is set, initialize() should return False and log a warning.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    collection_1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        up_final_stagnation_pressure=1600.5,
        choke_pressure=1500.0,
        up_duration=600,
        tank=MockTankWithStaticPressure("1")
    )
    collections = [collection_1]
    sample_upwards_instance.set_collections(collections)

    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tMain Valve not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_dynamic_valve(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If no dynamic_valve is set, initialize() should return False and log a warning.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    collection_1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        up_final_stagnation_pressure=1600.5,
        choke_pressure=1500.0,
        up_duration=600,
        tank=MockTankWithStaticPressure("1")
    )
    collections = [collection_1]
    sample_upwards_instance.set_collections(collections)

    main_valve = MockValve(18, "Main")
    sample_upwards_instance.set_main_valve(main_valve)

    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tDynamic Valve not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_static_valve(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If no static_valve is set, initialize() should return False and log a warning.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    collection_1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        up_final_stagnation_pressure=1600.5,
        choke_pressure=1500.0,
        up_duration=600,
        tank=MockTankWithStaticPressure("1")
    )
    collections = [collection_1]
    sample_upwards_instance.set_collections(collections)

    main_valve = MockValve(18, "Main")
    sample_upwards_instance.set_main_valve(main_valve)

    dynamic_valve = MockValve(17, "Dynamic")
    sample_upwards_instance.set_dynamic_valve(dynamic_valve)

    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tStatic Valve not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_manifold(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If no manifold is set, initialize() should return False and log a warning.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    collection_1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        up_final_stagnation_pressure=1600.5,
        choke_pressure=1500.0,
        up_duration=600,
        tank=MockTankWithStaticPressure("1")
    )
    collections = [collection_1]
    sample_upwards_instance.set_collections(collections)

    main_valve = MockValve(18, "Main")
    sample_upwards_instance.set_main_valve(main_valve)

    dynamic_valve = MockValve(17, "Dynamic")
    sample_upwards_instance.set_dynamic_valve(dynamic_valve)

    static_valve = MockValve(27, "Static")
    sample_upwards_instance.set_static_valve(static_valve)

    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tManifold Pressure Sensor not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_total_success(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If everything is set, initialize() should return True.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    collection_1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        up_final_stagnation_pressure=1600.5,
        choke_pressure=1500.0,
        up_duration=600,
        tank=MockTankWithStaticPressure("1")
    )
    collections = [collection_1]
    sample_upwards_instance.set_collections(collections)

    main_valve = MockValve(18, "Main")
    sample_upwards_instance.set_main_valve(main_valve)

    dynamic_valve = MockValve(17, "Dynamic")
    sample_upwards_instance.set_dynamic_valve(dynamic_valve)

    static_valve = MockValve(27, "Static")
    sample_upwards_instance.set_static_valve(static_valve)

    manifold_pressure_sensor = MockPressureSensorStatic(100)
    sample_upwards_instance.set_manifold_pressure_sensor(manifold_pressure_sensor)

    result = sample_upwards_instance.run()

    assert sample_upwards_instance.log_pressures == logPre
    assert sample_upwards_instance.collections == collections
    assert sample_upwards_instance.main_valve == main_valve
    assert sample_upwards_instance.dynamic_valve == dynamic_valve
    assert sample_upwards_instance.static_valve == static_valve
    assert sample_upwards_instance.manifold_pressure_sensor == manifold_pressure_sensor

    assert result is True

    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tPerforming Sample Upwards.") in Process.multiprint.logs[Process.output_log.name]

def test_system_tank_unknown(setup_process, sample_upwards_instance: SampleUpwards):
    """
    If the tank is unknown for a collection we won't sample it.
    """
    logPre = LogPressures()
    sample_upwards_instance.set_log_pressures(logPre)

    collection_1 = Collection(
        num=1,
        up_start_time=40305,
        bleed_duration=1, 
        up_driving_pressure=1270.44,
        up_final_stagnation_pressure=1600.5,
        choke_pressure=1500.0,
        up_duration=600,
        tank=MockTankWithStaticPressure("1")
    )
    collections = [collection_1]
    sample_upwards_instance.set_collections(collections)

    main_valve = MockValve(18, "Main")
    sample_upwards_instance.set_main_valve(main_valve)

    dynamic_valve = MockValve(17, "Dynamic")
    sample_upwards_instance.set_dynamic_valve(dynamic_valve)

    static_valve = MockValve(27, "Static")
    sample_upwards_instance.set_static_valve(static_valve)

    manifold_pressure_sensor = MockPressureSensorStatic(100)
    sample_upwards_instance.set_manifold_pressure_sensor(manifold_pressure_sensor)

    sample_upwards_instance.run()

    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tTank {collection_1.tank.valve.name} for Collection {collection_1.num} is {collection_1.tank.state}! Will not sample this Collection!") in Process.multiprint.logs[Process.output_log.name]
    

def test_cleanup_no_error(setup_process, sample_upwards_instance: SampleUpwards):
    """
    Since cleanup() is a no-op, calling it should not produce errors.
    """
    # Just ensure that calling cleanup() does not raise an exception.
    sample_upwards_instance.cleanup()
