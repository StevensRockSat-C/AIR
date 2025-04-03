import os
import time
import pytest
import tempfile
from warnings import warn

import sys
sys.path.append('../../')

from pi.processes.process_swap_tanks import SwapTanks
from pi.processes.process import Process
from pi.collection import Collection
from tests.processes.test_Process import MockTank
from tests.test_Tank import MockValve
from pi.MPRLS import MPRLSFile, MockPressureSensorStatic
from pi.RTC import RTCFile
from pi.multiprint import MockMultiPrinter

class MockCollection(Collection):
    def __init__(self, num: int):
        # Provide dummy values for required parameters; num is stored as a string.
        super().__init__(num=num, up_start_time=0, down_start_time=0, bleed_duration=0,
                         up_driving_pressure=0, down_driving_pressure=0, upwards_bleed=False)
        self.assigned_tank = None

    def associate_tank(self, tank):
        self.assigned_tank = tank

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

def test_initialize(setup, swap_tanks_instance, mock_multiprint, mock_rtc, mock_log, mock_pressures_log):
    """Test the initialization process."""
    
    assert Process.get_multiprint() == mock_multiprint
    assert Process.get_rtc() == mock_rtc
    assert Process.get_output_log() == mock_log
    assert Process.get_output_pressures() == mock_pressures_log
    assert Process.is_ready()
    assert Process.can_log()
    
    swap_tanks_instance.run()

    assert ("T+ " + str(Process.rtc.getTPlusMS()) + " ms\t" + "Initializing SwapTanks.") in Process.multiprint.logs[Process.output_log.name]

def test_run_not_ready(monkeypatch, setup, swap_tanks_instance):
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
    result = swap_tanks_instance.initialize()

    assert result is False
    # Check that an appropriate warning message was logged.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tTanks not set for SwapTanks! Aborting!") in Process.multiprint.logs[Process.output_log.name]

def test_initialize_failure_collections_none(setup, swap_tanks_instance: SwapTanks):
    """Test initialize() returns False when collections is None."""
    class MockTankWithStaticPressure(MockTank):
        def __init__(self, name):
            super().__init__(name, "none")
            self.mprls = MockPressureSensorStatic(800, 950)
    
    swap_tanks_instance.set_tanks([MockTankWithStaticPressure("1")])
    result = swap_tanks_instance.initialize()

    assert result is False
    # Check that an appropriate warning message was logged.
    assert (f"T+ {Process.rtc.getTPlusMS()} ms\tCollections not set for SwapTanks! Aborting!") in Process.multiprint.logs[Process.output_log.name]
