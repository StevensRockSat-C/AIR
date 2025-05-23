import warnings
import pytest
import sys
import tempfile
import time
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

from pi.utils import timeMS, gswitch_callback

from pi.processes.process import Process
from pi.multiprint import MockMultiPrinter
from pi.RTC import RTCFile

from tests.test_RTC import DummyDS3231

@pytest.fixture
def mock_multiprint(monkeypatch):
    """Mock MultiPrinter to capture printed messages."""
    mock_printer = MockMultiPrinter()
    return mock_printer

@pytest.fixture
def mock_log():
    """Create a temporary log file."""
    temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=True)
    yield temp_file
    temp_file.close()

@pytest.fixture
def setup_process(monkeypatch, mock_multiprint, mock_log):
    """Setup the Process class with required dependencies."""
    Process.set_multiprint(mock_multiprint)
    Process.set_output_log(mock_log)

# -----------------------------------------
# Tests for timeMS
# -----------------------------------------
def test_timeMS():
    """Test that timeMS returns current time in milliseconds."""
    # Get two timestamps close together
    t1 = timeMS()
    t2 = timeMS()
    
    # Verify they are close (within 100ms)
    assert abs(t2 - t1) < 100
    # Verify they are in milliseconds (roughly current time)
    assert t1 > 1600000000000  # Should be after 2021

# -----------------------------------------
# Tests for g-switch callback
# -----------------------------------------
def test_gswitch_callback_valid_time(setup_process, monkeypatch):
    """Test gswitch_callback with a valid time difference."""
    mock_rtc = RTCFile(1000 * 1000)  # Start at 1000 seconds
    fake_time = 1002.0  # seconds; simulating current time
    monkeypatch.setattr(time, "time", lambda: fake_time) # Force time to be fake_time, not incrementing
    Process.set_rtc(mock_rtc)

    channel = 25
    GSWITCH_PIN = 25

    # Expectation
    expected_log = f"T+ 0 ms\tG-Switch input! New t0: 1002000 ms. Difference from RBF estimation: 2000 ms"
    
    # Call the callback
    gswitch_callback(channel, GSWITCH_PIN)

    # Verify the RTC was updated
    assert Process.get_rtc().getT0MS() > 0
    
    # Verify the message was logged
    logs = Process.multiprint.logs[Process.output_log.name]
    assert any(expected_log in log for log in logs)

def test_gswitch_callback_invalid_time_early(setup_process, monkeypatch):
    """Test gswitch_callback with a time too early (before T-120s)."""
    channel = 25
    GSWITCH_PIN = 25
    
    # Set RTC to a time that would make the difference too early
    mock_rtc = RTCFile(1000 * 1000)  # Start at 1000 seconds
    fake_time = 870  # T-130s; simulating current time
    monkeypatch.setattr(time, "time", lambda: fake_time) # Force time to be fake_time, not incrementing
    Process.set_rtc(mock_rtc)

    # Expectations
    expected_log = f"T+ -130000 ms\tG-Switch input! Difference from RBF estimation: -130000 ms, which is too far off! We'll ignore it!"
    
    # Call the callback
    gswitch_callback(channel, GSWITCH_PIN)
    
    # Verify the message was logged about ignoring
    assert expected_log in Process.get_multiprint().logs[Process.get_output_log().name]

def test_gswitch_callback_invalid_time_late(setup_process, monkeypatch):
    """Test gswitch_callback with a time too late (after T+5s)."""
    channel = 25
    GSWITCH_PIN = 25
    
    # Set RTC to a time that would make the difference too late
    mock_rtc = RTCFile(1000 * 1000)  # Start at 1000 seconds
    fake_time = 1010  # T+10s; simulating current time
    monkeypatch.setattr(time, "time", lambda: fake_time) # Force time to be fake_time, not incrementing
    Process.set_rtc(mock_rtc)

    # Expectation
    expected_log = f"T+ 10000 ms\tG-Switch input! Difference from RBF estimation: 10000 ms, which is too far off! We'll ignore it!"
    
    # Call the callback
    gswitch_callback(channel, GSWITCH_PIN)
    
    # Verify the message was logged about ignoring
    assert expected_log in Process.get_multiprint().logs[Process.get_output_log().name]
