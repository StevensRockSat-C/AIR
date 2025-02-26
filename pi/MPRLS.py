#Jan 29, 2025

from abc import ABC, abstractmethod
import time
from statistics import median
from warnings import warn

try:
    import adafruit_mprls
except ImportError:
    adafruit_mprls = None

class PressureSensor(ABC):
    """Abstract base class for pressure sensors."""
    
    @abstractmethod
    def _get_pressure(self) -> float:
        """
        Get the pressure in hPa.

        Returns
        -------
        float
            Pressure, in hPa. -1 if there's an error.

        """
        pass
    
    @abstractmethod
    def _get_triple_pressure(self) -> float:
        """
        Sample the pressure three times for a median.

        Returns
        -------
        float
            Median pressure. -1 if all 3 reads failed.

        """
        pass
    
    def _set_pressure(self, value):
        pass

    def _del_pressure(self):
        pass
    
    pressure = property(
        fget=_get_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The pressure of the Pressure Sensor or -1 if it cannot be accessed"
    )
    
    triple_pressure = property(
        fget=_get_triple_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The 3-sample median pressure of the Pressure Sensor or -1 if it cannot be accessed"
    )

class MPRLSWrappedSensor(PressureSensor):
    """Handles real MPRLS hardware by wrapping the base MPRLS to enact soft error handling."""
    
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
                warn("Adafruit MPRLS library not found!")
                self.cant_connect = True
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

class NovaPressureSensor(PressureSensor):
    """Implementation of the NovaSensor NPI-19-I2C pressure sensor (30 psi absolute pressure)."""
    
    I2C_ADDRESS = 0x28  # Default I2C address
    P_MIN = 1638        # Digital count at minimum pressure (10% VDD)
    P_MAX = 14745       # Digital count at maximum pressure (90% VDD)
    PSI_MIN = 0         # Absolute pressure sensor, minimum at vacuum
    PSI_MAX = 30        # Maximum rated pressure for the 30 psi version
    PSI_TO_HPA = 68.9476# Conversion factor
    
    def __init__(self, channel):
        self.channel = channel
        self.ready = False
        for i in range(3):
            if (self.is_pressure_valid(self._read_pressure_digital())):
                self.ready = True
                break
            time.sleep(0.01) # Wait 10 ms to see if i2c works again
    
    def _read_pressure_digital(self) -> int:
        """
        Read the pressure from the sensor in digital counts.

        Returns
        -------
        int
            Pressure in digital counts. -1 if there's an error.
        """
        try:
            incoming_buffer = bytearray(2)
            self.channel.readfrom_into(self.I2C_ADDRESS, incoming_buffer)
            raw_pressure = (incoming_buffer[0] << 8) | incoming_buffer[1]
            return raw_pressure
        except Exception:
            return -1
    
    def _convert_pressure_hpa(self, digital_pressure: int) -> float:
        """
        Convert the pressure from digital counts to hPa.

        Parameters
        ----------
        digital_pressure : int
            Pressure in digital counts.

        Returns
        -------
        float
            Pressure in hPa.
        """
        pressure_psi = ((digital_pressure - self.P_MIN) * (self.PSI_MAX - self.PSI_MIN) /
                        (self.P_MAX - self.P_MIN)) + self.PSI_MIN
        return pressure_psi * self.PSI_TO_HPA  # Convert psi to hPa
    
    def is_pressure_valid(self, pressure_hpa: float) -> bool:
        """
        Check if the pressure value is valid.

        Parameters
        ----------
        pressure_hpa : float
            Measured pressure as hPa.

        Returns
        -------
        bool
            If the pressure is within the expected bounds of the sensor.

        """
        pressure_psi = pressure_hpa / self.PSI_TO_HPA
        return (pressure_psi > self.PSI_MIN and pressure_psi <= self.PSI_MAX)
    
    def _get_pressure(self) -> float:
        """
        Get the pressure in hPa.

        Returns
        -------
        float
            Pressure, in hPa. -1 if there's an error.

        """
        digital_pressure = self._read_pressure_digital()    
        hpa_pressure = self._convert_pressure_hpa(digital_pressure)
        
        if (self.is_pressure_valid(hpa_pressure)): return hpa_pressure
        return -1
    
    def _get_triple_pressure(self) -> float:
        """
        Sample the pressure three times for a median.

        Returns
        -------
        float
            Median pressure. -1 if all 3 reads failed.

        """
        pressures = []
        for i in range(3):
            pressures.append(self._get_pressure())
            if i < 2: time.sleep(0.001)  # On the Nova Sensor, we can safely read at 1 kHz. Tested in lab 2/12/25
        return median([p for p in pressures if p != -1]) if max(pressures) != -1 else -1
    
    def _set_pressure(self, value):
        pass

    def _del_pressure(self):
        pass
    
    pressure = property(
        fget=_get_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The pressure of the Nova Pressure Sensor or -1 if it cannot be accessed"
    )
    
    triple_pressure = property(
        fget=_get_triple_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The 3-sample median pressure of the Nova Pressure Sensor or -1 if it cannot be accessed"
    )


class MPRLSFile(PressureSensor):
    """Handles virtualized MPRLS sensor playback from a file (for testing)."""
    
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
        try:
            value = self.data[self.index]
        except IndexError:
            return -1
            print("MPRLSFile get_pressure: reached EOF")
        self.index = self.index + 1
        return value
    
    def _get_triple_pressure(self) -> float:
        if not self.data:
            return -1
        pressures = [self._get_pressure() for _ in range(3)]
        time.sleep(0.010) # MPRLS sample rate is 200 Hz https://forums.adafruit.com/viewtopic.php?p=733797
                          # Simulate 2 sleeps for reading from the actual sensor
        return median(pressures)
    
    def _set_pressure(self, value):
        pass

    def _del_pressure(self):
        pass
    
    pressure = property(
        fget=_get_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The pressure from the File or -1 if it cannot be accessed"
    )
    
    triple_pressure = property(
        fget=_get_triple_pressure,
        fset=_set_pressure,
        fdel=_del_pressure,
        doc="The 3-sample median pressure from the File or -1 if it cannot be accessed"
    )