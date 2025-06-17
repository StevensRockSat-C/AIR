import time
import pytest
import tempfile
from warnings import warn

_original_time = time.time

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))


from pi.processes.process import Process, PlumbingState
from pi.processes.process_sample_upwards import SampleUpwards
from pi.processes.process_log_pressures import LogPressures

from pi.RTC import RTCFile
from pi.MPRLS import MockPressureSensorStatic, MockPressureTemperatureSensorStatic, MPRLSFile
from pi.multiprint import MockMultiPrinter
from pi.collection import Collection
from pi.tank import Tank, TankState

from tests.test_Tank import MockValve

class MockTankWithStaticPressure(Tank):
    def __init__(self, name, pressure_single=800, pressure_triple=None):
        if pressure_triple == None: pressure_triple = pressure_single
        super().__init__(name, MockPressureSensorStatic(pressure_single, pressure_triple))
        self.valve = MockValve(10, name)

class MockTankWithDynamicPressure(Tank):
    def __init__(self, name, pressure_single: list[float], pressure_triple=None):
        if pressure_triple == None: pressure_triple = pressure_single
        # Convert single values to lists if they aren't already
        self._pressure_single = pressure_single if isinstance(pressure_single, list) else [pressure_single]
        self._pressure_triple = pressure_triple if isinstance(pressure_triple, list) else [pressure_triple]
        super().__init__(MockValve(10, name), MockPressureSensorStatic(self._pressure_single[0], self._pressure_triple[0]))
        self._pressure_index = 1

    def open(self):
        """Override Tank.open() to change pressure sensor after opening valve"""
        super().open()
        # Get next pressure values, cycling back to start if we reach the end
        single_pressure = self._pressure_single[self._pressure_index % len(self._pressure_single)]
        triple_pressure = self._pressure_triple[self._pressure_index % len(self._pressure_triple)]
        self.pressure_sensor = MockPressureSensorStatic(single_pressure, triple_pressure)
        self._pressure_index += 1

class MPRLSList(MPRLSFile):
    def __init__(self, values: list[float]):
        # Create a temporary file with the values
        temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False)
        try:
            # Write each value on a new line
            for value in values:
                temp_file.write(f"{value}\n")
            temp_file.close()
            # Initialize parent with the temporary file path
            super().__init__(temp_file.name)
        finally:
            # Clean up the temporary file
            import os
            os.unlink(temp_file.name)

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

def test_initialize_no_collections(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If no collections are set, initialize() should return False and log a warning.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

    result = sample_upwards_instance.initialize()

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tCollections not set for SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_no_main_valve(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If no main_valve is set, initialize() should return False and log a warning.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

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

def test_initialize_no_dynamic_valve(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If no dynamic_valve is set, initialize() should return False and log a warning.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

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

def test_initialize_no_static_valve(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If no static_valve is set, initialize() should return False and log a warning.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

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

def test_initialize_no_manifold(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If no manifold is set, initialize() should return False and log a warning.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

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

def test_initialize_temp_thresh_reached(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If everything is set, but the temp_thresh was reached, should return False
    """
    mock_log_process.set_temp_thresh_reached(True)
    sample_upwards_instance.set_log_pressures(mock_log_process)

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

    assert result is False
    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tTemp threshold was reached before SampleUpwards! Aborting Process.") in Process.multiprint.logs[Process.output_log.name]

    mock_log_process.set_temp_thresh_reached(False) # Reset Class variable for future tests

def test_initialize_total_success(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If everything is set, initialize() should return True.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

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

    assert sample_upwards_instance.log_pressures == mock_log_process
    assert sample_upwards_instance.collections == collections
    assert sample_upwards_instance.main_valve == main_valve
    assert sample_upwards_instance.dynamic_valve == dynamic_valve
    assert sample_upwards_instance.static_valve == static_valve
    assert sample_upwards_instance.manifold_pressure_sensor == manifold_pressure_sensor

    assert result is True

    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\tPerforming Sample Upwards.") in Process.multiprint.logs[Process.output_log.name]

def test_system_tank_unknown(setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
    If the tank is unknown for a collection we won't sample it.
    """
    sample_upwards_instance.set_log_pressures(mock_log_process)

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
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tFinished Sample Upwards.") in Process.multiprint.logs[Process.output_log.name]
    

def test_cleanup_no_error(setup_process, sample_upwards_instance: SampleUpwards):
    """
    Since cleanup() is a no-op, calling it should not produce errors.
    """
    # Just ensure that calling cleanup() does not raise an exception.
    sample_upwards_instance.cleanup()

# --- Cyclomatic Path Tests for SampleUpwards._do_sample_collection ---

def test_sample_success_first_try(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[100,1234])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=3290,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(1000, 1000))

    sample_upwards_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Sampled successfully" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (1234 hPa) has met final stag pressure ({collection.up_final_stagnation_pressure} hPa)." in log for log in logs)
    assert      any(f"Collection {collection.num} succeeded (Tank {tank.valve.name} {tank.state})!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.SAMPLED

def test_sample_success_during_tsmall(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """If we reach the final stag pressure during t-small, do not sample again"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithDynamicPressure("A", pressure_single=[100,800,1001,1300])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))
    
    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Sampled successfully" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (800 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (1001 hPa) has met final stag pressure ({collection.up_final_stagnation_pressure} hPa) during t_small test. Sampled successfully" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.SAMPLED

def test_sample_success_second_try(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithDynamicPressure("A", pressure_single=[100,800,900,1100])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))
    
    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert any("Sampled successfully" in log for log in logs)
    assert any(f"Tank {tank.valve.name} pressure (800 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert any(f"Tank {tank.valve.name} pressure (900 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa) during t_small test! Trying again" in log for log in logs)
    assert any("Try #2" in log for log in logs)
    assert tank.state == TankState.SAMPLED

def test_sample_fail_second_try(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """Continual flow, but simply fails to meet the final stag pressure"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[200,300,400,500])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))

    sample_upwards_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert any("Failed sample" in log for log in logs)
    assert any(f"Tank {tank.valve.name} pressure (300 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert any(f"Tank {tank.valve.name} pressure (300 -> 400 hPa) changed significantly during t_small test. This means that the valve chain is open, but the math on collection duration was wrong" in log for log in logs)
    assert any(f"Collection {collection.num} failed (Tank {tank.valve.name} {tank.state})!" in log for log in logs)
    assert any("Try #2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE

def test_sample_main_line_failure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """ΔPtank ≈ 0 and ΔPmanifold ≈ 0."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithStaticPressure("A", pressure_single=100)
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} pressure (100 -> 100 hPa) and manifold pressure (800 -> 800 hPa) did not change significantly. There must be a main line failure!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert Process.get_plumbing_state() == PlumbingState.MAIN_LINE_FAILURE

def test_sample_valve_failure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """ΔPtank ≈ 0 and ΔPmanifold ≠ 0."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithStaticPressure("A", pressure_single=100)
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MPRLSList([800, 810, 820, 870, 880, 890]))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} pressure (100 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (100 -> 100 hPa) did not change significantly but the manifold pressure did (810.0 -> 880.0 hPa). Valve for Tank {tank.valve.name} must have failed!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE

def test_sample_vacuum_compromised_tsmall(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """t_small test ΔPtank ≈ 0."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[200,500,505])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} pressure (500 -> 505 hPa) did not change significantly during t_small test. This means that the vacuum of Tank {tank.valve.name} was compromised, but the sample is questionable. Failed Sample!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE

def test_sample_tank_last_resort(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithStaticPressure("A", pressure_single=1050, pressure_triple=1050)
    tank.state = TankState.LAST_RESORT
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(900, 900))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} for Collection {collection.num} is {tank.state}! Due to new constraints, we can not test for efficacy & therefore will not sample this Collection!" in log for log in logs)
    assert not  any(f"Beginning Collection 1" in log for log in logs)

def test_sample_tank_not_ready(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithStaticPressure("A", pressure_single=1400, pressure_triple=1400)
    tank.state = TankState.CRITICAL
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(900, 900))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert any(f"Tank {tank.valve.name} for Collection {collection.num} is {tank.state}! Will not sample this Collection!" in log for log in logs)

def test_sample_plumbing_not_ready(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithStaticPressure("A", pressure_single=150, pressure_triple=150)
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(900, 900))
    Process.set_plumbing_state(PlumbingState.MAIN_LINE_FAILURE)
    
    sample_upwards_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert any(f"Tank {tank.valve.name} for Collection {collection.num} is {tank.state}, but the plumbing is {PlumbingState.MAIN_LINE_FAILURE}. Will not sample this Collection!" in log for log in logs)

def test_bleed_threshold_hit(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[100,1234])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=3290,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )

    class MockValveTempThresh(MockValve):
        def __init__(self, pin, name):
            super().__init__(pin, name)
        
        def open(self):
            super().open()
            LogPressures.set_temp_thresh_reached(True)
    
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValveTempThresh(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(1000, 1000))

    sample_upwards_instance.run()

    LogPressures.set_temp_thresh_reached(False)
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Temp threshold hit!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.READY

def test_sampling_threshold_hit(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[100,1234])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=3290,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )

    class MockValveTempThresh(MockValve):
        def __init__(self, pin, name):
            super().__init__(pin, name)
        
        def open(self):
            super().open()
            LogPressures.set_temp_thresh_reached(True)
    
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValveTempThresh(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(1000, 1000))

    sample_upwards_instance.run()

    LogPressures.set_temp_thresh_reached(False)
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Temp threshold hit!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE    # Vacuum was compromised

def test_t_small_threshold_hit(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[100,800,900,1300])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=3290,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )

    class MockValveTempThresh(MockValve):
        def __init__(self, pin, name):
            super().__init__(pin, name)
            self.index = 0
        
        def open(self):
            super().open()
            self.index += 1
            if self.index == 2: LogPressures.set_temp_thresh_reached(True)
    
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValveTempThresh(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(1000, 1000))

    sample_upwards_instance.run()

    LogPressures.set_temp_thresh_reached(False)
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Temp threshold hit!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE    # Vacuum was compromised

def test_waiting_for_collection_threshold_hit(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithStaticPressure("A", pressure_single=100)
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=3290,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )

    monkeypatch.setattr(LogPressures, "execute", lambda c: LogPressures.set_temp_thresh_reached(True))
    
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(1000, 1000))

    sample_upwards_instance.run()

    LogPressures.set_temp_thresh_reached(False)
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Temp threshold hit!" in log for log in logs)
    assert not  any(f"Beginning Collection {collection.num}" in log for log in logs) # Ensure we don't start sampling
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.READY

# -----------------------------------------
# Tests for triple pressure
# -----------------------------------------

def test_sample_success_first_try_triple_pressure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """Ptank ≥ 95% of pc? (using triple pressure)"""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[100,900], pressure_triple=[100,1234])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=3290,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(1000, 1000))

    sample_upwards_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Sampled successfully" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (1234 hPa) has met final stag pressure ({collection.up_final_stagnation_pressure} hPa)." in log for log in logs)
    assert      any(f"Collection {collection.num} succeeded (Tank {tank.valve.name} {tank.state})!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.SAMPLED

def test_sample_fail_continual_flow_t_small_changed_triple_pressure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
        Δ Ptank ≈ 0? (using triple pressure)
        No (valvex is operational)(tank has been opened to the manifold)
        Δ Ptank ≈ 0? (using triple pressure)
        No (valve chain is open, math on tx was wrong)
    """
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[200,201,202,203], pressure_triple=[200,300,400,500])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))

    sample_upwards_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any("Failed sample" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (300 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (300 -> 400 hPa) changed significantly during t_small test. This means that the valve chain is open, but the math on collection duration was wrong" in log for log in logs)
    assert      any(f"Collection {collection.num} failed (Tank {tank.valve.name} {tank.state})!" in log for log in logs)
    assert      any("Try #2" in log for log in logs)
    assert not  any("201" in log for log in logs)
    assert not  any("202" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE

def test_sample_fail_continual_flow_t_small_unchanged_triple_pressure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """
        Δ Ptank ≈ 0? (using triple pressure)
        No (valvex is operational)(tank has been opened to the manifold)
        Δ Ptank ≈ 0? (using triple pressure)
        Yes (Vacuum of tank was compromised, but questionable sample)
    """
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)

    tank = MockTankWithDynamicPressure("A", pressure_single=[200,310,601.2,800], pressure_triple=[200,299,301])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=0, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(800, 800))

    sample_upwards_instance.run()
    
    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} pressure (299 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (299 -> 301 hPa) did not change significantly during t_small test. This means that the vacuum of Tank {tank.valve.name} was compromised, but the sample is questionable. Failed Sample!" in log for log in logs)
    assert      any(f"Collection {collection.num} failed (Tank {tank.valve.name} {tank.state})!" in log for log in logs)
    assert not  any("Try #2" in log for log in logs)
    assert not  any("310" in log for log in logs)
    assert not  any("601.2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE

def test_sample_valve_failure_triple_pressure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """ΔPtank ≈ 0 and ΔPmanifold ≠ 0."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithDynamicPressure("A", pressure_single=[200, 500, 1000, 1500], pressure_triple=100)
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MPRLSList([800, 810, 820, 870, 880, 890]))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} pressure (100 hPa) did NOT meet final stag pressure ({collection.up_final_stagnation_pressure} hPa)!" in log for log in logs)
    assert      any(f"Tank {tank.valve.name} pressure (100 -> 100 hPa) did not change significantly but the manifold pressure did (810.0 -> 880.0 hPa). Valve for Tank {tank.valve.name} must have failed!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert tank.state == TankState.FAILED_SAMPLE

def test_sample_main_line_failure_triple_pressure(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """ΔPtank ≈ 0 and ΔPmanifold ≈ 0."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithStaticPressure("A", pressure_single=100)
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(2000, 800))

    sample_upwards_instance.run()

    logs = Process.multiprint.logs[Process.output_log.name]
    assert      any(f"Tank {tank.valve.name} pressure (100 -> 100 hPa) and manifold pressure (800 -> 800 hPa) did not change significantly. There must be a main line failure!" in log for log in logs)
    assert not  any(f"Try #2" in log for log in logs)
    assert Process.get_plumbing_state() == PlumbingState.MAIN_LINE_FAILURE

# -----------------------------------------
# Tests for disconnections
# -----------------------------------------

def test_sample_tank_disconnect(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """If sample tank disconnects after reference pressure taken, then ΔPtank should ≈ 0 because we can't assume it's changing."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithDynamicPressure("A", pressure_single=[100, -1, -1, -1])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MockPressureSensorStatic(2000, 800))

    sample_upwards_instance.run()

    assert Process.plumbing_state == PlumbingState.MAIN_LINE_FAILURE

def test_manifold_disconnect(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """If manifold sensor disconnects after reference pressure taken, then ΔPmanifold should ≈ 0 because we can't assume it's changing."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithDynamicPressure("A", pressure_single=[150, 150, 150, 150])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MPRLSList([800, 800, 800, -1, -1, -1])) # delta manifold != 0 but delta tank = 0

    sample_upwards_instance.run()

    assert tank.state == TankState.FAILED_SAMPLE

def test_tank_disconnect_during_tsmall(monkeypatch, setup_process, sample_upwards_instance: SampleUpwards, mock_log_process: LogPressures):
    """If sample tank disconnects after reference pressure taken, then ΔPtank should ≈ 0 because we can't assume it's changing."""
    monkeypatch.setattr(time, "time", _original_time) # Force time to be fake_time, not incrementing
    mock_rtc = RTCFile(int(time.time() * 1000 - 15000)) # Put us at T+15000ms
    Process.set_rtc(mock_rtc)
    
    tank = MockTankWithDynamicPressure("A", pressure_single=[0, 150, -1, -1, -1, -1])
    tank.state = TankState.READY
    collection = Collection(
        num=1, up_start_time=15500, bleed_duration=10, up_driving_pressure=1000,
        up_final_stagnation_pressure=1000, choke_pressure=900, up_duration=10, tank=tank
    )
    sample_upwards_instance.set_log_pressures(mock_log_process)
    sample_upwards_instance.set_collections([collection])
    sample_upwards_instance.set_main_valve(MockValve(1, "Main"))
    sample_upwards_instance.set_dynamic_valve(MockValve(2, "Dynamic"))
    sample_upwards_instance.set_static_valve(MockValve(3, "Static"))
    sample_upwards_instance.set_manifold_pressure_sensor(MPRLSList([800, 800, 800, 800, 800, 800])) 

    sample_upwards_instance.run()

    assert tank.state == TankState.FAILED_SAMPLE #should NOT try to sample again
    logs = Process.multiprint.logs[Process.output_log.name]
    assert not any ("Trying again" in log for log in logs)