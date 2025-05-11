import time
import pytest
import tempfile
from warnings import warn

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pi.processes.process_swap_tanks import SwapTanks
from pi.processes.process import Process
from pi.collection import Collection
from pi.tank import Tank, TankState
from pi.MPRLS import MockPressureSensorStatic
from pi.RTC import RTCFile
from pi.multiprint import MockMultiPrinter

from tests.test_Tank import MockValve

class MockCollection(Collection):
    def __init__(self, num: int):
        # Provide dummy values for required parameters; num is stored as a string.
        super().__init__(num=num, up_start_time=0, bleed_duration=0, up_driving_pressure=0,
                         up_final_stagnation_pressure=0, choke_pressure=0, up_duration=0)
        self.assigned_tank = None

    def associate_tank(self, tank):
        self.assigned_tank = tank

class MockTankWithStaticPressure(Tank):
    def __init__(self, name, pressure_single=800, pressure_triple=950):
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
def setup(monkeypatch, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Setup the Process class."""

    Process.set_multiprint(mock_multiprint)
    Process.set_rtc(mock_rtc)
    Process.set_output_log(mock_log)
    Process.set_output_pressures(mock_pressures_log)

@pytest.fixture
def swap_tanks_instance() -> SwapTanks:
    """Fixture to create an instance of SwapTanks."""
    return SwapTanks()

def test_initialize(setup, swap_tanks_instance: SwapTanks, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process."""
    
    assert Process.get_multiprint() == mock_multiprint
    assert Process.get_rtc() == mock_rtc
    assert Process.get_output_log() == mock_log
    assert Process.get_output_pressures() == mock_pressures_log
    assert Process.is_ready()
    assert Process.can_log()
    
    swap_tanks_instance.run()

    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\t" + "Initializing SwapTanks.") in Process.multiprint.logs[Process.output_log.name]

def test_run_not_ready(monkeypatch, setup, swap_tanks_instance: SwapTanks):
    """Test that run() returns False when Process.is_ready() is False."""
    # Force the process to be not ready.
    monkeypatch.setattr(Process, "is_ready", lambda: False)

    result = swap_tanks_instance.run()
    assert result is False
    # Expect a warning message (logged via pform) about process not being ready.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tProcess is not ready for SwapTanks!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_failure_tanks_none(setup, swap_tanks_instance: SwapTanks):
    """Test initialize() returns False when tanks is empty."""
    
    swap_tanks_instance.set_collections([MockCollection(1)])
    result = swap_tanks_instance.run()

    assert result is False
    # Check that an appropriate warning message was logged.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tTanks not set for SwapTanks! Aborting!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_failure_collections_none(setup, swap_tanks_instance: SwapTanks):
    """Test initialize() returns False when collections is None."""
    swap_tanks_instance.set_tanks([MockTankWithStaticPressure(1)])
    result = swap_tanks_instance.run()

    assert result is False
    # Check that an appropriate warning message was logged.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tCollections not set for SwapTanks! Aborting!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_failure_length_mismatch(setup, swap_tanks_instance: SwapTanks):
    """Test initialize() returns False when the number of tanks and collections differ."""
    swap_tanks_instance.tanks = [MockTankWithStaticPressure(1)]
    swap_tanks_instance.collections = [MockCollection(1), MockCollection(2)]
    result = swap_tanks_instance.run()

    assert result is False
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tNumber of Tanks not equal to the number of Collections in SwapTanks! Aborting!") in Process.multiprint.logs[Process.output_log.name]
    
def test_execute_various_states(setup, swap_tanks_instance: SwapTanks):
    """Test execute() assigns tanks to collections based on state and pressure."""
    # Create several mock tanks:
    # One LAST_RESORT tank, two READY tanks, and one NOT_READY tank.
    tank_last_resort = MockTankWithStaticPressure("LR", 700, 700)
    tank_last_resort.state = TankState.LAST_RESORT
    tank_ready1 = MockTankWithStaticPressure("R1", 500, 500)
    tank_ready1.state = TankState.READY
    tank_ready2 = MockTankWithStaticPressure("R2", 600, 600)
    tank_ready2.state = TankState.READY
    tank_not_ready = MockTankWithStaticPressure("NR", 400, 400)
    tank_not_ready.state = TankState.UNREACHABLE

    swap_tanks_instance.set_tanks([tank_last_resort, tank_ready1, tank_not_ready, tank_ready2])
    # Create one collection for each tank.
    col1 = MockCollection(1)
    col2 = MockCollection(2)
    col3 = MockCollection(3)
    col4 = MockCollection(4)
    swap_tanks_instance.set_collections([col1, col2, col3, col4])

    # Run execute (assumes initialize has passed).
    swap_tanks_instance.run()

    # According to the code:
    #  - The LAST_RESORT tank should be assigned first.
    #  - Then the READY tanks (sorted by pressure: R1 then R2).
    #  - Finally, the not ready tank.
    assert col1.assigned_tank == tank_last_resort
    assert col2.assigned_tank == tank_ready1
    assert col3.assigned_tank == tank_ready2
    assert col4.assigned_tank == tank_not_ready

    # Also verify that the log messages include the expected assignment messages.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank LR to Collection 1") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R1 to Collection 2") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R2 to Collection 3") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank NR to Collection 4") in Process.multiprint.logs[Process.output_log.name]

def test_execute_all_ready(setup, swap_tanks_instance: SwapTanks):
    """Test execute() assigns tanks to collections based on pressure."""
    # Create several mock tanks:
    # One LAST_RESORT tank, two READY tanks, and one NOT_READY tank.
    tank_ready0 = MockTankWithStaticPressure("R0", 700, 700)
    tank_ready0.state = TankState.READY
    tank_ready1 = MockTankWithStaticPressure("R1", 500, 500)
    tank_ready1.state = TankState.READY
    tank_ready2 = MockTankWithStaticPressure("R2", 600, 600)
    tank_ready2.state = TankState.READY
    tank_ready3 = MockTankWithStaticPressure("R3", 400, 400)
    tank_ready3.state = TankState.READY

    swap_tanks_instance.set_tanks([tank_ready0, tank_ready1, tank_ready2, tank_ready3])
    # Create one collection for each tank.
    col1 = MockCollection(1)
    col2 = MockCollection(2)
    col3 = MockCollection(3)
    col4 = MockCollection(4)
    swap_tanks_instance.set_collections([col1, col2, col3, col4])

    # Run execute (assumes initialize has passed).
    swap_tanks_instance.run()

    # According to the code:
    #  - The READY tanks (sorted by pressure: R3, R1, R2, R0).
    assert col1.assigned_tank == tank_ready3
    assert col2.assigned_tank == tank_ready1
    assert col3.assigned_tank == tank_ready2
    assert col4.assigned_tank == tank_ready0

    # Also verify that the log messages include the expected assignment messages.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R3 to Collection 1") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R1 to Collection 2") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R2 to Collection 3") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R0 to Collection 4") in Process.multiprint.logs[Process.output_log.name]

def test_execute_triple_pressure(setup, swap_tanks_instance: SwapTanks):
    """Test execute() assigns tanks to collections based on triple pressure."""
    # Create several mock tanks:
    # One LAST_RESORT tank, two READY tanks, and one NOT_READY tank.
    tank_ready0 = MockTankWithStaticPressure("R0", 400, 700)
    tank_ready0.state = TankState.READY
    tank_ready1 = MockTankWithStaticPressure("R1", 600, 500)
    tank_ready1.state = TankState.READY
    tank_ready2 = MockTankWithStaticPressure("R2", 500, 600)
    tank_ready2.state = TankState.READY
    tank_ready3 = MockTankWithStaticPressure("R3", 700, 400)
    tank_ready3.state = TankState.READY

    swap_tanks_instance.set_tanks([tank_ready0, tank_ready1, tank_ready2, tank_ready3])
    # Create one collection for each tank.
    col1 = MockCollection(1)
    col2 = MockCollection(2)
    col3 = MockCollection(3)
    col4 = MockCollection(4)
    swap_tanks_instance.set_collections([col1, col2, col3, col4])

    # Run execute (assumes initialize has passed).
    swap_tanks_instance.run()

    # According to the code:
    #  - The READY tanks (sorted by triple pressure: R3, R1, R2, R0).
    assert col1.assigned_tank == tank_ready3
    assert col2.assigned_tank == tank_ready1
    assert col3.assigned_tank == tank_ready2
    assert col4.assigned_tank == tank_ready0

    # Also verify that the log messages include the expected assignment messages.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R3 to Collection 1") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R1 to Collection 2") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R2 to Collection 3") in Process.multiprint.logs[Process.output_log.name]
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tAssigned tank R0 to Collection 4") in Process.multiprint.logs[Process.output_log.name]

def test_cleanup(setup, swap_tanks_instance: SwapTanks):
    """Test that cleanup() logs the finishing message."""

    tank_last_resort = MockTankWithStaticPressure("LR", 700, 700)
    tank_last_resort.state = TankState.READY

    swap_tanks_instance.set_tanks([tank_last_resort])
    # Create one collection for each tank.
    col1 = MockCollection(1)
    swap_tanks_instance.set_collections([col1])

    # Run
    swap_tanks_instance.run()

    # The cleanup message should be the last log entry.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tFinished Initial Pressure Check.") == Process.multiprint.logs[Process.output_log.name][-1]