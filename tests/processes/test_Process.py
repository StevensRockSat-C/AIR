import os
import tempfile
import time
import pytest
from warnings import warn

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pi.processes.process import Process, PlumbingState
from pi.RTC import RTCFile
from pi.MPRLS import MPRLSFile
from pi.tank import Tank
from tests.test_Tank import MockValve
from pi.multiprint import MockMultiPrinter

class MockTank(Tank):
    """Mock Tank class to simulate tanks with valves and sensors."""
    def __init__(self, name, filepath: str):
        self.valve = MockValve(10, name)
        self.pressure_sensor = MPRLSFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath))
        super().__init__(self.valve, self.pressure_sensor)

@pytest.fixture
def mock_multiprint(monkeypatch):
    """Mock MultiPrinter to capture printed messages."""
    mock_printer = MockMultiPrinter()
    
    from pi.processes.process import Process
    monkeypatch.setattr(Process, "multiprint", mock_printer)
    return mock_printer

@pytest.fixture
def mock_rtc(monkeypatch):
    """Mock RTC to provide fixed timestamps."""
    
    mock_rtc = RTCFile(123456)
    
    from pi.processes.process import Process
    monkeypatch.setattr(Process, "rtc", mock_rtc)
    return mock_rtc

@pytest.fixture
def mock_log(monkeypatch):
    """Mock log file as a simple list."""
    mock_log = "mock_process_log.txt"
    
    from pi.processes.process import Process
    monkeypatch.setattr(Process, "output_log", mock_log)
    return mock_log

@pytest.fixture
def mock_pressure_log(monkeypatch):
    """Mock log file as a simple list."""
    mock_pressures = "mock_pressures_log.txt"
    
    from pi.processes.process import Process
    monkeypatch.setattr(Process, "output_pressures", mock_pressures)
    return mock_pressures

def test_process_monkeypatch(mock_multiprint, mock_rtc, mock_log, mock_pressure_log):
    """Test the monkeypatching of the Process class."""

    assert Process.multiprint == mock_multiprint
    assert Process.rtc == mock_rtc
    assert Process.output_log == mock_log
    assert Process.output_pressures == mock_pressure_log

def test_process_initialization():
    """Test the initialization process."""

    multiprint = MockMultiPrinter()
    rtc = RTCFile(123456)
    log = tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=True)
    pressures = tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=True)
    state = PlumbingState.READY

    Process.multiprint = multiprint
    Process.rtc = rtc
    Process.output_log = log
    Process.output_pressures = pressures
    Process.plumbing_state = state


    assert Process.multiprint == multiprint
    assert Process.rtc == rtc
    assert Process.output_log == log
    assert Process.output_pressures == pressures
    assert Process.plumbing_state == PlumbingState.READY
    
    log.close()
    pressures.close()