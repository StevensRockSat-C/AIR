import os
import time
import tempfile
import pytest
from enum import Enum 
from warnings import warn
import re


import sys
sys.path.append('../../')

from pi.processes.process_initial_pressure_check import InitialPressureCheck, PlumbingState
from pi.RTC import RTCFile
from pi.MPRLS import MPRLSFile, MockPressureSensorStatic
from tests.test_Tank import MockValve
from pi.multiprint import MockMultiPrinter
from pi.tank import TankState
from pi.processes.process_log_pressures import LogPressures
from pi.processes.process import Process


class MockTank:
    """Mock Tank class to simulate tanks with valves and sensors."""
    def __init__(self, name, filepath: str):
        self.valve = MockValve(10, name)
        self.mprls = MPRLSFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath))
        self.state = TankState.UNKNOWN   

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

    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\t" + "Initializing Initial Pressure Check.") in Process.multiprint.logs[Process.output_log.name]

# TODO: Add tests for missing main valve and manifold pressure sensor

def test_all_good(setup_initial_pressure_check, initial_pressure_check: InitialPressureCheck):
    """Test when all tanks have good pressure."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)
    print("BRUHHHHHHH: ", tanks[0].mprls.file_path, tanks[0].mprls.data)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(100, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "bruh"))


    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name]))

    assert Process.get_plumbing_state() == PlumbingState.READY
    for tank in tanks:
        assert (tank.state == TankState.READY)  # Tanks should be marked ready
        #assert f"T+ {Process.rtc.getTPlusMS()} ms\tPressure in Tank {tank.valve.name} is {tank.mprls.pressure}. All good." in Process.multiprint.logs[Process.output_log.name]
        assert f"T+  ms\tPressure in Tank {tank.valve.name} is {tank.mprls.pressure}. Marked it READY." in mp_logs


def test_tanks_atmospheric(setup_initial_pressure_check, initial_pressure_check):
    """Test when tanks have atmospheric pressure (marked as UNSAFE)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_atmospheric_lower.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(700, 707))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)
    

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name]))

    assert initial_pressure_check.plumbing_state == PlumbingState.READY

    assert initial_pressure_check.tanks[0].state == TankState.UNSAFE #separately check if each tank is the correct state
    assert initial_pressure_check.tanks[1].state == TankState.LAST_RESORT

    for tank in initial_pressure_check.tanks: #both tanks are still originally marked UNSAFE, so we can keep this.
        #assert tank.state == TankState.UNSAFE # Tanks should be marked unsafe
        assert f"T+  ms\tPressure in Tank {tank.valve.name} is atmospheric ({tank.mprls.pressure} hPa). Marked it UNSAFE." in mp_logs


def test_tanks_rocket_pressure(setup_initial_pressure_check, initial_pressure_check):
    """Test when tanks have atmospheric pressure (marked as UNSAFE)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_rocket_pressure.csv"), MockTank("B", "test_Initial_Pressure_Check_rocket_pressure.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))


    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)
    
    initial_pressure_check.run()


    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove time stamps for testing

    for tank in tanks:
        assert tank.state == TankState.CRITICAL # Tanks should be marked critical
        assert f"T+  ms\tPressure in Tank {tank.valve.name} is pressurized above atmospheric ({tank.mprls.pressure} hPa). Marked it CRITICAL." in mp_logs
    assert initial_pressure_check.plumbing_state == PlumbingState.READY

def test_tanks_cannot_connect(setup_initial_pressure_check, initial_pressure_check):
    """Test when tanks cannot connect to MPRLS sensor (marked as unreachable)."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_cannot_connect.csv"), MockTank("B", "test_Initial_Pressure_Check_cannot_connect.csv")]
    initial_pressure_check.set_tanks(tanks)
    
    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)
    

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    for tank in tanks:
        assert tank.state == TankState.UNREACHABLE # Tanks should be marked unreachable
        assert f"T+  ms\tPressure in Tank {tank.valve.name} cannot be determined! Marked it UNREACHABLE." in mp_logs

def test_cleanup(setup_initial_pressure_check, initial_pressure_check):
    """Test the cleanup phase."""
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(600, 110))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    assert (f"T+  ms\tFinished Initial Pressure Check.") in mp_logs

def test_uses_triple_pressure(setup_initial_pressure_check, initial_pressure_check):
    """Test that triple_pressure is used for dead tank determination."""
    # Create a tank with different pressure and triple_pressure values
    class MockTankWithDifferentPressures(MockTank):
        def __init__(self, name):
            super().__init__(name, "test_Initial_Pressure_Check_all_good.csv")
            self.mprls = MockPressureSensorStatic(800, 950)
    
    tanks = [MockTankWithDifferentPressures("A")]
    initial_pressure_check.set_tanks(tanks)

    # file_pressure_sensor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), )
    file_pressure_sensor = MPRLSFile("test_Initial_Pressure_Check_manifold_failing.csv")
    print(file_pressure_sensor.data)
    initial_pressure_check.set_manifold_pressure_sensor(file_pressure_sensor)
    
    tanks_2 =  [MockTank("t1", "test_Initial_Pressure_Check_manifold_failing.csv"), MockTank("t2", "test_Initial_Pressure_Check_all_good.csv")]
    print(tanks_2[0].mprls.data, tanks_2[1].mprls.data)


    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()
    
    mp_logs = list(map(lambda elem: re.sub(r'\d{13}', '', elem), Process.multiprint.logs[Process.output_log.name])) #remove timestamps for testing

    # Tank should be marked LAST_RESORT because it is unsafe and main plumbing line is failing
    assert tanks[0].state == TankState.LAST_RESORT
    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE

    # Verify the log message uses triple_pressure value
    assert f"T+  ms\tPressure in Tank {tanks[0].valve.name} is pressurized above atmospheric ({tanks[0].mprls.triple_pressure} hPa). Marked it UNSAFE." in mp_logs

def test_manifold_failing_one_LAST_RESORT(setup_initial_pressure_check, initial_pressure_check):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MPRLSFile("test_Initial_Pressure_Check_manifold_failing.csv"))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()
    
    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE
    assert initial_pressure_check.tanks[0].state == TankState.LAST_RESORT #since values in test_Initial_Pressure_Check_all_good.csv are: 100, 101.1, 101.1, 101.1, 101.1
    assert initial_pressure_check.tanks[0] == tanks[1] #check that the right tank was assigned LAST_RESORT

def test_manifold_failing_no_LAST_RESORT(setup_initial_pressure_check, initial_pressure_check):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_rocket_pressure.csv"), MockTank("B", "test_Initial_Pressure_Check_rocket_pressure.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MPRLSFile("test_Initial_Pressure_Check_manifold_failing.csv"))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE
    assert initial_pressure_check.tanks[0].state == TankState.LAST_RESORT #since values in test_Initial_Pressure_Check_all_good.csv are: 100, 101.1, 101.1, 101.1, 101.1
    assert initial_pressure_check.tanks[0] == tanks[1] #check that the right tank was assigned LAST_RESORT

def test_manifold_unconnected_all_tanks_good(setup_initial_pressure_check, initial_pressure_check):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(-1))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    for tank in tanks:
        assert tank.state == TankState.READY 
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tManifold Pressure Sensor OFFLINE.") in Process.multiprint.logs[Process.output_log.name]

def test_manifold_unconnected_one_tank_all_good(setup_initial_pressure_check, initial_pressure_check):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(-1))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    assert initial_pressure_check.tanks[0].state == TankState.READY 
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tManifold Pressure Sensor OFFLINE.") in Process.multiprint.logs[Process.output_log.name]

def test_manifold_unconnected_no_tanks_all_good(setup_initial_pressure_check, initial_pressure_check):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("B", "test_Initial_Pressure_Check_atmospheric.csv"), MockTank("C", "test_Initial_Pressure_Check_tanks_cannot_conneect.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MockPressureSensorStatic(-1))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.READY
    assert initial_pressure_check.tanks[0].state == TankState.LAST_RESORT
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tManifold Pressure Sensor OFFLINE.") in Process.multiprint.logs[Process.output_log.name]

def test_manifold_unconnected_no_tanks_all_good(setup_initial_pressure_check, initial_pressure_check):
    tanks = [MockTank("A", "test_Initial_Pressure_Check_all_good.csv"), MockTank("B", "test_Initial_Pressure_Check_all_good.csv"), MockTank("C", "test_Initial_Pressure_Check_all_good.csv")]
    initial_pressure_check.set_tanks(tanks)

    initial_pressure_check.set_manifold_pressure_sensor(MPRLSFile("test_Initial_Pressure_Check_manifold_critical.csv"))
    initial_pressure_check.set_main_valve(MockValve(10, "mockValve"))

    pressure_log = LogPressures()
    pressure_log.set_pressure_sensors([MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110), MockPressureSensorStatic(100, 110)])
    initial_pressure_check.set_log_pressures(pressure_log)

    initial_pressure_check.run()

    assert initial_pressure_check.plumbing_state == PlumbingState.MAIN_LINE_FAILURE
    assert initial_pressure_check.tanks[0].state == TankState.LAST_RESORT
