import os
import time
import tempfile
import pytest
from enum import Enum 
from warnings import warn
import re

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pi.processes.process_initial_pressure_check import InitialPressureCheck, PlumbingState
from pi.RTC import RTCFile
from pi.MPRLS import MPRLSFile, MockPressureSensorStatic, MockPressureTemperatureSensorStatic
from tests.test_Tank import MockValve
from tests.processes.test_Process import MockTank
from pi.multiprint import MockMultiPrinter
from pi.tank import TankState
from pi.processes.process_log_pressures import LogPressures
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
    #monkeypatch.setattr(time, "time", lambda: fake_time) # Force time to be fake_time, not incrementing
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
def mock_log_process() -> LogPressures:
    log_Process = LogPressures()
    log_Process.set_canister_pressure_sensor(MockPressureSensorStatic(100))
    log_Process.set_dpv_temperature(MockPressureTemperatureSensorStatic(100, 350))
    log_Process.set_pressure_sensors([MockPressureTemperatureSensorStatic(100, 110), MockPressureTemperatureSensorStatic(100, 110), MockPressureTemperatureSensorStatic(100, 110)])
    return log_Process

@pytest.fixture
def setup_initial_pressure_check(monkeypatch, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Setup the initial pressure check."""

    Process.set_multiprint(mock_multiprint)
    Process.set_rtc(mock_rtc)
    Process.set_output_log(mock_log)
    Process.set_output_pressures(mock_pressures_log)

@pytest.fixture
def initial_pressure_check() -> InitialPressureCheck:
    """Fixture to create an instance of InitialPressureCheck."""
    return InitialPressureCheck()


def test_initialize(setup_initial_pressure_check, initial_pressure_check, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process."""
    
    assert Process.get_multiprint() == mock_multiprint
    assert Process.get_rtc() == mock_rtc
    assert Process.get_output_log() == mock_log
    assert Process.get_output_pressures() == mock_pressures_log
    assert Process.is_ready()
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    assert ("T+  ms\t" + "Initializing Initial Pressure Check.") in mp_logs

def test_initialize_failure_tanks(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process."""
    
    pressure_log = mock_pressures_log
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing
    assert ("T+  ms\t" + "Tanks not set for Initial Pressure Check! Aborting Process.") in mp_logs

def test_initialize_failure_manifold_pressure_sensor(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process."""
    
    pressure_log = mock_pressures_log
    initial_pressure_check.set_log_pressures(pressure_log)
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing
    assert ("T+  ms\t" + "Manifold Pressure Sensor not set for Initial Pressure Check! Aborting Process.") in mp_logs

def test_initialize_failure_main_valve(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process."""
    
    pressure_log = mock_pressures_log
    initial_pressure_check.set_log_pressures(pressure_log)
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(100, 110))
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing
    assert ("T+  ms\t" + "Main Valve not set for Initial Pressure Check! Aborting Process.") in mp_logs

def test_all_good(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_log_process: LogPressures):
    """Test when all tanks have good pressure."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)
    print("BRUHHHHHHH: ", tanks[0].mprls.file_path, tanks[0].mprls.data)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(100, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "bruh"))


    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name]))  #remove time stamps for testing

    assert Process.get_plumbing_state() == PlumbingState.READY
    for tank in tanks:
        assert (tank.state == TankState.READY)  # Tanks should be marked ready
        assert f"T+  ms\tPressure in Tank {tank.valve.name} is {tank.mprls.pressure}. Marked it READY." in mp_logs

def test_tanks_atmospheric(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    """Test when tanks have atmospheric pressure (marked as UNSAFE)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_atmospheric_lower.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(700, 707))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    initial_pressure_check.set_log_pressures(pressure_log)
    

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove time stamps for testing

    assert initial_pressure_check.plumbing_state == PlumbingState.READY

    assert initial_pressure_check.tanks[0].state == TankState.UNSAFE 
    assert initial_pressure_check.tanks[1].state == TankState.LAST_RESORT

    for tank in initial_pressure_check.tanks: #both tanks are still originally marked UNSAFE, so we can keep this.
        assert f"T+  ms\tPressure in Tank {tank.valve.name} is atmospheric ({tank.mprls.pressure} hPa). Marked it UNSAFE." in mp_logs

def test_tanks_rocket_pressure(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    """Test when tanks have atmospheric pressure (marked as UNSAFE)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_rocket_pressure.csv"), MockTank("B", "test_Initial_Pressure_Check_rocket_pressure.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))


    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()


    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove time stamps for testing

    for tank in tanks:
        assert tank.state == TankState.CRITICAL # Tanks should be marked critical
        assert f"T+  ms\tPressure in Tank {tank.valve.name} is pressurized above atmospheric ({tank.mprls.pressure} hPa). Marked it CRITICAL." in mp_logs
    assert initial_pressure_check.plumbing_state == PlumbingState.READY

def test_tanks_cannot_connect(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    """Test when tanks cannot connect to MPRLS sensor (marked as unreachable)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_tanks_cannot_connect.csv"), MockTank("B", "test_Initial_Pressure_Check_tanks_cannot_connect.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)
    

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    for tank in tanks:
        assert tank.state == TankState.UNREACHABLE # Tanks should be marked unreachable
        assert f"T+  ms\tPressure in Tank {tank.valve.name} cannot be determined! Marked it UNREACHABLE." in mp_logs

def test_tanks_two_ready_one_unsafe(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_log_process: LogPressures):
    """Test when tanks have atmospheric pressure (marked as UNSAFE)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_atmospheric.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))


    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()


    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove time stamps for testing

    assert tanks[0].state == TankState.READY
    assert tanks[1].state == TankState.READY
    assert tanks[2].state == TankState.UNSAFE
    
    assert f"T+  ms\tPressure in Tank {tanks[0].valve.name} is {tanks[0].mprls.pressure}. Marked it READY." in mp_logs
    assert f"T+  ms\tPressure in Tank {tanks[1].valve.name} is {tanks[1].mprls.pressure}. Marked it READY." in mp_logs
    assert f"T+  ms\tPressure in Tank {tanks[2].valve.name} is atmospheric ({tanks[2].mprls.pressure} hPa). Marked it UNSAFE." in mp_logs
    assert initial_pressure_check.plumbing_state == PlumbingState.READY


def test_tanks_one_ready(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    """Test when one tank is ready and two are not ready (unconnected and critical)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_rocket_pressure.csv"), MockTank("B", "test_Initial_Pressure_Check_tanks_cannot_connect.csv"), 
             MockTank("C", "test_Initial_Pressure_Check_all_good.csv"), MockTank("D", "test_Initial_Pressure_Check_atmospheric.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))


    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove time stamps for testing

    assert tanks[0].state == TankState.CRITICAL
    assert tanks[1].state == TankState.UNREACHABLE
    assert tanks[2].state == TankState.READY
    assert tanks[3].state == TankState.UNSAFE

    assert f"T+  ms\tPressure in Tank {tanks[0].valve.name} is pressurized above atmospheric ({tanks[0].mprls.pressure} hPa). Marked it CRITICAL." in mp_logs
    assert f"T+  ms\tPressure in Tank {tanks[1].valve.name} cannot be determined! Marked it UNREACHABLE." in mp_logs
    assert f"T+  ms\tPressure in Tank {tanks[2].valve.name} is {tanks[2].mprls.pressure}. Marked it READY." in mp_logs
    assert f"T+  ms\tPressure in Tank {tanks[3].valve.name} is atmospheric ({tanks[3].mprls.pressure} hPa). Marked it UNSAFE." in mp_logs

    assert initial_pressure_check.plumbing_state == PlumbingState.READY

def test_cleanup(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    """Test the cleanup phase."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    assert (f"T+  ms\tFinished Initial Pressure Check.") in mp_logs

def test_uses_triple_pressure(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_log_process: LogPressures):
    """Test that triple_pressure is used for dead tank determination."""
    # Create a tank with different pressure and triple_pressure values
    class MockTankWithDifferentPressures(MockTank):
        def __init__(self, name):
            super().__init__(name, "test_Initial_Pressure_Check_all_good.csv")
            self.pressure_sensor = MockPressureSensorStatic(800, 950)
    
    tanks = [MockTankWithDifferentPressures("A")]
    initial_pressure_check.set_tanks(tanks)

    file_pressure_sensor = MPRLSFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_Initial_Pressure_Check_manifold_failing.csv"))
    initial_pressure_check.set_manifold_pressure_sensor(file_pressure_sensor)

    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()
    
    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    # Tank should be marked LAST_RESORT because it is unsafe and main plumbing line is failing
    assert tanks[0].state == TankState.LAST_RESORT
    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE

    # Verify the log message uses triple_pressure value
    assert f"T+  ms\tPressure in Tank {tanks[0].valve.name} is atmospheric ({tanks[0].mprls.triple_pressure} hPa). Marked it UNSAFE." in mp_logs

def test_manifold_failing_one_LAST_RESORT(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MPRLSFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_Initial_Pressure_Check_manifold_failing.csv")))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()
    
    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE
    assert initial_pressure_check.tanks[1].state == TankState.LAST_RESORT #since values in test_Initial_Pressure_Check_all_good.csv are: 100, 101.1, 101.1, 101.1, 101.1
    assert initial_pressure_check.tanks[0].state == TankState.UNSAFE #since values in test_Initial_Pressure_Check_atmospheric.csv are: 1000.1, 1000.1, ...

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing
    assert (f"T+  ms\tThe manifold pressure changed by more than {initial_pressure_check.delta_manifold_pressure_failing_threshold} hPa! There is a MAIN LINE FAILURE!") in mp_logs

def test_manifold_failing_no_LAST_RESORT(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck, mock_log_process: LogPressures):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_rocket_pressure.csv"), MockTank("B", "test_Initial_Pressure_Check_rocket_pressure.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MPRLSFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_Initial_Pressure_Check_manifold_failing.csv")))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE
    assert initial_pressure_check.tanks[0].state == TankState.CRITICAL
    assert initial_pressure_check.tanks[1].state == TankState.CRITICAL

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing
    assert (f"T+  ms\tThe manifold pressure changed by more than {initial_pressure_check.delta_manifold_pressure_failing_threshold} hPa! There is a MAIN LINE FAILURE!") in mp_logs

def test_manifold_unconnected_all_tanks_good(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(-1))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    for tank in tanks:
        assert tank.state == TankState.READY 
    assert (f"T+  ms\tManifold pressure sensor is offline! Assuming the plumbing state is READY.") in mp_logs

def test_manifold_unconnected_one_tank_all_good(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(-1))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    assert initial_pressure_check.tanks[0].state == TankState.UNSAFE 
    assert initial_pressure_check.tanks[1].state == TankState.UNSAFE 
    assert initial_pressure_check.tanks[2].state == TankState.READY

    assert (f"T+  ms\tManifold pressure sensor is offline! Assuming the plumbing state is READY.") in mp_logs

def test_manifold_unconnected_tanks_unsafe(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("C", "test_Initial_Pressure_Check_tanks_cannot_connect.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(-1))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    assert initial_pressure_check.tanks[0].state == TankState.LAST_RESORT
    assert initial_pressure_check.tanks[1].state == TankState.UNSAFE
    assert initial_pressure_check.tanks[2].state == TankState.UNREACHABLE
    assert (f"T+  ms\tManifold pressure sensor is offline! Assuming the plumbing state is READY.") in mp_logs

def test_manifold_critical_all_tanks_good(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MPRLSFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_Initial_Pressure_Check_manifold_critical.csv")))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = mock_log_process
    
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    for tank in tanks: 
        assert tank.state == TankState.READY
# ========================
# DISCONNECTION TESTS
# ========================

def test_manifold_disconnect_mid_check(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    # ensure that a -1 isn't counted towards the delta pressure to set PlumbingState.MAIN_LINE_FAILURE
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    man_press_sensor = MPRLSFile("tests/processes/test_Initial_Pressure_Check_disconnect_mid.csv") #file reads: 101 101 101 101 101 -1 -1 -1 -1 101
    initial_pressure_check.set_manifold_pressure_sensor(man_press_sensor) 

    pressure_log = mock_log_process
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.READY #probably should still be ready if one is unconnected but next one is connected (and valid)

def test_manifold_disconnect_after_disconnect_check(setup_initial_pressure_check, initial_pressure_check, mock_log_process: LogPressures):
    # ensure that a -1 isn't counted towards the delta pressure to set PlumbingState.MAIN_LINE_FAILURE
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    man_press_sensor = MPRLSFile("tests/processes/test_Initial_Pressure_Check_disconnect_start.csv") #file reads: 101 101 -1 -1 -1 -1 -1 -1 -1
    initial_pressure_check.set_manifold_pressure_sensor(man_press_sensor) 

    pressure_log = mock_log_process
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.READY #if sensor disconnects even though its not marked disconnected, plumbing should be READY