#Jan 29, 2025

from abc import ABC, abstractmethod
import time
from statistics import median

try:
    import adafruit_mprls
except ImportError:
    adafruit_mprls = None

class MPRLS(ABC):
    """
    Abstract base class for MPRLS pressure sensors.
    """
    
    @abstractmethod
    def _get_pressure(self) -> float:
        pass
    
    @abstractmethod
    def _get_triple_pressure(self) -> float:
        pass
    
    def _set_pressure(self, value):
        pass

    def _del_pressure(self):
        pass
    
    pressure = property(
        fget=_get_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The pressure of the MPRLS or -1 if it cannot be accessed"
    )
    
    triple_pressure = property(
        fget=_get_triple_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The 3-sample median pressure of the MPRLS or -1 if it cannot be accessed"
    )

class MPRLSWrappedSensor(MPRLS):
    """
    Handles real MPRLS hardware by wrapping the base MPRLS to enact soft error handling.
    """
    
    def __init__(self, multiplexer_line=None):
        self.cant_connect = False
        self.mprls = None
        
        if not multiplexer_line:
            self.cant_connect = True
            return
        
        try:
            if adafruit_mprls:
                self.mprls = adafruit_mprls.MPRLS(multiplexer_line, psi_min=0, psi_max=25)
            else:
                raise ImportError("Adafruit MPRLS library not found")
        except:
            self.cant_connect = True
    
    def _get_pressure(self) -> float:
        if self.cant_connect:
            return -1
        try:
            return self.mprls.pressure
        except Exception:
            return -1
    
    
    def _get_triple_pressure(self) -> float:
        if self.cant_connect:
            return -1
        pressures = []
        for i in range(3):
            try:
                pressures.append(self.mprls.pressure)
            except Exception:
                pass
            if i < 2: time.sleep(0.005) # MPRLS sample rate is 200 Hz https://forums.adafruit.com/viewtopic.php?p=733797
        return median(pressures) if pressures else -1

class NovaPressureSensor(MPRLS):
    """
    Implementation of the NovaSensor NPI-19-I2C pressure sensor (30 psi absolute pressure).
    """
    
    I2C_ADDRESS = 0x28  # Default I2C address
    P_MIN = 1638        # Digital count at minimum pressure (10% VDD)
    P_MAX = 14745       # Digital count at maximum pressure (90% VDD)
    PSI_MIN = 0         # Absolute pressure sensor, minimum at vacuum
    PSI_MAX = 30        # Maximum rated pressure for the 30 psi version
    PSI_TO_HPA = 68.9476# Conversion factor
    
    def __init__(self, channel):
        self.channel = channel
        self.ready = False
        time.sleep(0.01)  # Allow sensor initialization
        self.ready = True
    
    def _read_pressure_raw(self):
        try:
            data = self.channel.readfrom(self.I2C_ADDRESS, 2)
            raw_pressure = (data[0] << 8) | data[1]
            return raw_pressure
        except Exception:
            return -1
    
    def _convert_pressure(self, raw_pressure):
        if raw_pressure == -1:
            return -1
        pressure_psi = ((raw_pressure - self.P_MIN) * (self.PSI_MAX - self.PSI_MIN) /
                        (self.P_MAX - self.P_MIN)) + self.PSI_MIN
        return pressure_psi * self.PSI_TO_HPA  # Convert psi to hPa
    
    def _get_pressure(self) -> float:
        raw_pressure = self._read_pressure_raw()
        return self._convert_pressure(raw_pressure)
    
    def _get_triple_pressure(self) -> float:
        pressures = []
        for i in range(3):
            pressures.append(self._get_pressure())
            if i < 2: time.sleep(0.005)  # Sampling delay
        return median([p for p in pressures if p != -1]) if pressures else -1


class MPRLSFile(MPRLS):
    """
    Handles virtualized MPRLS sensor playback from a file (for testing).

    """
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self._load_data()
        self.index = 0
    
    def _load_data(self):
        try:
            with open(self.file_path, 'r') as f:
                return [float(line.strip()) for line in f.readlines()]
        except Exception:
            return []
    
    def _get_pressure(self) -> float:
        if not self.data:
            return -1
        value = self.data[self.index]
        self.index = (self.index + 1) % len(self.data)
        return value
    
    def _get_triple_pressure(self) -> float:
        if not self.data:
            return -1
        pressures = [self._get_pressure() for _ in range(3)]
        time.sleep(0.010) # MPRLS sample rate is 200 Hz https://forums.adafruit.com/viewtopic.php?p=733797
                          # Simulate 2 sleeps for reading from the actual sensor
        return median(pressures)
