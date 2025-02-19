import time
import sys
sys.path.append('../')
from pi.RTC import RTCFile, RTCWrappedSensor
import pytest

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

def test_rtcwrappedsensor_success(monkeypatch):
    """
    Successful initialization of RTCWrappedSensor using a dummy DS3231.
    """
    # Fix the time so that all time.time() calls return a constant value.
    fixed_time = 2000.0  # seconds; equivalent to 2,000,000 ms
    monkeypatch.setattr(time, "time", lambda: fixed_time)
    
    # Create a dummy module-like object with the DS3231 attribute.
    DummyModule = type("DummyModule", (), {"DS3231": DummyDS3231})
    
    # Monkeypatch the adafruit_ds3231 variable in the RTC module.
    import pi.RTC as rtc_module
    monkeypatch.setattr(rtc_module, "adafruit_ds3231", DummyModule)
    
    # Create a dummy I2C object (could be any object).
    dummy_i2c = object()
    sensor = RTCWrappedSensor(dummy_i2c)
    
    # The dummy DS3231 returns tm_min=1 and tm_sec=30, so the offset is:
    # offset = (1*60 + 30)*1000 = 90,000 ms.
    # With fixed_time=2000.0 s, both ref and now are 2,000,000 ms.
    # Then, t0 = 2000000 - 90,000 ms = 1910000 ms.
    expected_t0_ms = 1910000
    expected_t0 = round(expected_t0_ms / 1000)  # 1970 seconds
    
    # Verify that the sensor reports readiness and the calculated t0 values.
    assert sensor.isReady() is True
    assert sensor.getT0() == expected_t0
    assert sensor.getT0MS() == expected_t0_ms
    
    # TPlus is calculated as the difference between current time and t0.
    # Thus, tPlus = 2,000s - 1,910s = 90s
    expected_tplus = round(fixed_time - expected_t0)
    expected_tplus_ms = int(fixed_time * 1000) - expected_t0_ms
    assert sensor.getTPlus() == expected_tplus
    assert sensor.getTPlusMS() == expected_tplus_ms

def test_rtcwrappedsensor_failure(monkeypatch):
    """
    Initialization failure of RTCWrappedSensor (simulate DS3231 failure).
    """
    fixed_time = 2000.0  # seconds
    monkeypatch.setattr(time, "time", lambda: fixed_time)
    
    # Define a dummy DS3231 constructor that always raises an exception.
    def DummyFailingDS3231(i2c):
        raise Exception("Simulated DS3231 failure")
    
    DummyModule = type("DummyModule", (), {"DS3231": DummyFailingDS3231})
    
    import pi.RTC as rtc_module
    monkeypatch.setattr(rtc_module, "adafruit_ds3231", DummyModule)
    
    dummy_i2c = object()
    sensor = RTCWrappedSensor(dummy_i2c)
    
    # On failure, the sensor should remain not ready.
    assert sensor.isReady() is False
    
    # In the failure branch, ref is set to round(time()*1000), so ref = 2000000 ms.
    expected_est_t0 = fixed_time
    expected_est_t0_ms = int(fixed_time * 1000)
    assert sensor.getT0() == expected_est_t0
    assert sensor.getT0MS() == expected_est_t0_ms
    
    # TPlus calculations use the fallback ref value.
    expected_tplus = round(fixed_time - expected_est_t0)
    expected_tplus_ms = int(fixed_time * 1000) - expected_est_t0_ms
    assert sensor.getTPlus() == expected_tplus
    assert sensor.getTPlusMS() == expected_tplus_ms

def test_rtcwrappedsensor_set_est_t0(monkeypatch):
    """
    setEstT0 updates the internal reference time correctly.
    """
    fixed_time = 2000.0
    monkeypatch.setattr(time, "time", lambda: fixed_time)
    
    DummyModule = type("DummyModule", (), {"DS3231": DummyDS3231})
    
    import pi.RTC as rtc_module
    monkeypatch.setattr(rtc_module, "adafruit_ds3231", DummyModule)
    
    dummy_i2c = object()
    sensor = rtc_module.RTCWrappedSensor(dummy_i2c)
    
    assert sensor.isReady() is True
    
    old_t0 = sensor.getT0MS()
    new_t0 = 3000000  # New reference time in ms.
    diff = sensor.setEstT0(new_t0)

    # The returned difference should equal the change in t0.
    assert diff == new_t0 - old_t0
    # After setting, getT0 should reflect the new reference (in seconds).
    assert sensor.getT0() == new_t0 // 1000
    # And getT0MS should return the new reference directly.
    assert sensor.getT0MS() == new_t0