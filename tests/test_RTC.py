import time
import sys
sys.path.append('../')
from pi.RTC import RTC, RTCFile
import pytest
  # Import the classes from your module; for example, assume the module is named rtc_module
  # from rtc_module import RTCFile, RTCWrappedSensor
  # --- Dummy DS3231 for simulating a working RTC in RTCWrappedSensor ---
class DummyDS3231:
      def __init__(self, i2c):
          self.i2c = i2c
          # Provide a dummy datetime object with required attributes.
          # For example, tm_min=1 and tm_sec=30 simulate 1 minute and 30 seconds (90s)
          self.datetime = type("DummyDatetime", (), {"tm_min": 1, "tm_sec": 30})()


  # ===========================
  # Tests for RTCFile (Simulated RTC)
  # ===========================
def test_rtcfile_is_ready():
      """
      Verify that RTCFile is immediately ready when constructed.
      """
      start_time = 1000000  # millisecond timestamp
      rtc = RTCFile(start_time)
      assert rtc.isReady() is True

def test_rtcfile_get_t0_and_get_t0_ms():
      """
      Check that getT0 returns the correct seconds value (derived from t0)
      and that getT0MS returns the original millisecond value.
      """
      start_time = 1000000  # ms
      rtc = RTCFile(start_time)
      expected_t0_sec = round(start_time / 1000)
      assert rtc.getT0() == expected_t0_sec
      assert rtc.getT0MS() == start_time

def test_rtcfile_set_est_t0():
    """
    Test that setting an estimated T0 updates the internal state correctly.
    The difference returned should equal the new t0 minus the old one.
    """
    start_time = 1000000
    rtc = RTCFile(start_time)
    new_ref = 2000000
    diff = rtc.setEstT0(new_ref)
    assert diff == new_ref - start_time
    # After updating, getT0 should reflect the new value.
    assert rtc.getT0() == new_ref // 1000

def test_rtcfile_get_tplus(monkeypatch):
    """
    With a fixed time, ensure that getTPlus calculates the elapsed time in seconds
    correctly as: current_time - t0 (both in seconds).
    """
    start_time = 1000000
    rtc = RTCFile(start_time)
    fake_time = 1005.0  # seconds; simulating current time
    monkeypatch.setattr(time, "time", lambda: fake_time)
    expected_tplus = round(fake_time - round(start_time / 1000))
    assert rtc.getTPlus() == expected_tplus

def test_rtcfile_get_tplus_ms(monkeypatch):
    """
    With a fixed time, ensure that getTPlusMS calculates the elapsed time in milliseconds
    correctly as: current_time_in_ms - t0.
    """
    start_time = 1000000
    rtc = RTCFile(start_time)
    fake_time = 1005.0  # seconds
    monkeypatch.setattr(time, "time", lambda: fake_time)
    expected_tplus_ms = round(fake_time * 1000) - start_time
    assert rtc.getTPlusMS() == expected_tplus_ms
# ===========================
# Tests for RTCWrappedSensor (Hardware-backed RTC)
# ===========================
''' commented out as we focus on getting the unit testing to work for files
def test_rtcwrappedsensor_success(monkeypatch):
    """
    Test the normal operation of RTCWrappedSensor when the DS3231 is available.
    We monkeypatch time.time to return a fixed value and replace the DS3231 with our DummyDS3231.
    Calculation reasoning:
      - fixed_time (in seconds) is 2000.0; so round(time()*1000) returns 2,000,000 ms.
      - DummyDS3231 returns tm_min=1 and tm_sec=30, so the RTC time offset is (60+30)*1000 = 90,000
      - tMinus60 is then: 2,000,000 - 90,000 = 1,910,000.
      - t0 is calculated as: tMinus60 + 60,000 = 1,970,000 ms.
      - getT0() should therefore return 1,970,000/1000 = 1970 seconds.
    """
    fixed_time = 2000.0  # seconds
    monkeypatch.setattr(time, "time", lambda: fixed_time)
    # Patch the DS3231 class to use DummyDS3231 instead
    import adafruit_ds3231
    monkeypatch.setattr(adafruit_ds3231, "DS3231", DummyDS3231)
    dummy_i2c = object()  # a dummy i2c instance
    sensor = RTCWrappedSensor(dummy_i2c)
    assert sensor.isReady() is True
    # Expected calculations
    expected_t0_ms = 2000000 - 90000 + 60000  # = 1970000 ms
    expected_t0 = round(expected_t0_ms / 1000)  # = 1970 seconds
    assert sensor.getT0() == expected_t0
    assert sensor.getT0MS() == expected_t0_ms
    # Since time is fixed, TPlus should be current_time - t0 in seconds and ms
    expected_tplus = round(fixed_time - expected_t0)
    expected_tplus_ms = round(fixed_time * 1000) - expected_t0_ms
    assert sensor.getTPlus() == expected_tplus
    assert sensor.getTPlusMS() == expected_tplus_ms

def test_rtcwrappedsensor_failure(monkeypatch):
    """
    Simulate a failure in initializing the DS3231 (e.g. no RTC on the I2C bus).
    We monkeypatch DS3231 to raise an exception. In this failure mode:
    - The sensor should set ready to False.
    - getT0 and getT0MS should fall back to using the 'ref' value computed from time.time().
    - TPlus calculations then use the fallback value.
    """
    # Create a dummy DS3231 constructor that always fails.
    def failing_ds3231(i2c):
        raise Exception("RTC not found")

    import adafruit_ds3231
    monkeypatch.setattr(adafruit_ds3231, "DS3231", failing_ds3231)

    fixed_time = 2000.0  # seconds
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    dummy_i2c = object()
    sensor = RTCWrappedSensor(dummy_i2c)

    # The failure path should set ready to False
    assert sensor.isReady() is False

    # In failure mode, ref was set to round(time()*1000) = 2,000,000
    expected_ref = 2000000
    expected_t0 = round(expected_ref / 1000)
    assert sensor.getT0() == expected_t0
    assert sensor.getT0MS() == expected_ref

    # TPlus in failure mode is calculated based on the fallback ref.
    expected_tplus = round(fixed_time - expected_t0)
    expected_tplus_ms = round(fixed_time * 1000) - expected_ref
    assert sensor.getTPlus() == expected_tplus
    assert sensor.getTPlusMS() == expected_tplus_ms

    # Also test that setEstT0 properly updates the internal state in failure mode.
    new_ref = 3000000
    diff = sensor.setEstT0(new_ref)
    assert diff == new_ref - expected_ref

    # After updating, getT0 should reflect the new 'ref' (even if ready remains False).
    assert sensor.getT0() == new_ref // 1000
'''