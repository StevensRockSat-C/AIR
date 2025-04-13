#Jan 29, 2025

from abc import ABC, abstractmethod
import time
from statistics import median
from warnings import warn
from typing import Optional
try:
    import adafruit_mprls
except ImportError:
    adafruit_mprls = None

class PressureSensor(ABC):
    """Abstract base class for pressure sensors."""
    
    @property
    @abstractmethod
    def pressure(self) -> float:
        """
        Get the pressure in hPa.

        Returns
        -------
        float
            Pressure, in hPa. -1 if there's an error.

        """
        pass
    
    @property
    @abstractmethod
    def triple_pressure(self) -> float:
        """
        Sample the pressure three times for a median.

        Returns
        -------
        float
            Median pressure. -1 if all 3 reads failed.

        """
        pass

class PressureTemperatureSensor(PressureSensor):
    """Pressure sensors that can also read temperature"""

    @property
    @abstractmethod
    def temperature(self) -> float:
        """
        Get the temperature in Celcius.

        Returns
        -------
        float
            Temperature, in C. -1 if there's an error.
        """
        pass

    @property
    @abstractmethod
    def triple_temperature(self) -> float:
        """
        Sample the temperature three times for a median.

        Returns
        -------
        float
            Median temperature, in C. -1 if all 3 reads failed.
        """
        pass

    @property
    @abstractmethod
    def pressure_and_temp(self) -> tuple[float, float]:
        """
        Get the pressure and temperature in one read.

        Returns
        -------
        float
            Pressure, in hPa. -1 if there's an error.
        float
            Temperature, in C. -1 if there's an error.
        """
        pass

    @property
    @abstractmethod
    def triple_pressure_and_temp(self) -> tuple[float, float]:
        """
        Get the pressure and temperature in three reads.

        Returns
        -------
        float
            Pressure, in hPa. -1 if all 3 reads failed.
        float
            Temperature, in C. -1 if all 3 reads failed.
        """
        pass

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
    
    @property
    def pressure(self) -> float:
        if self.cant_connect:
            return -1
        try:
            return self.mprls.pressure
        except Exception:
            return -1
    
    @property
    def triple_pressure(self) -> float:
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
    

class NovaPressureSensor(PressureTemperatureSensor):
    """Implementation of the NovaSensor NPI-19-I2C pressure sensor (30 psi absolute pressure)."""
    
    I2C_ADDRESS = 0x28      # Default I2C address
    P_MIN = 1638            # Digital count at minimum pressure (10% VDD)
    P_MAX = 14745           # Digital count at maximum pressure (90% VDD)
    PSI_MIN = 0             # Absolute pressure sensor, minimum at vacuum
    PSI_MAX = 30            # Maximum rated pressure for the 30 psi version
    PSI_TO_HPA = 68.9476    # Conversion factor
    TEMP_BITS_SPAN = 2048   # 11 bits
    TEMP_MAX = 150          # Celcius     
    TEMP_MIN = -50          # Celcius
    TEMP_SPAN = TEMP_MAX - TEMP_MIN
    
    def __init__(self, channel):
        self.channel = channel
        self.ready = False
        for i in range(3):
            if (self._is_pressure_valid(self._convert_pressure_hpa(self._read_pressure_digital()))):
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
            if self.channel.try_lock():
                try:
                    incoming_buffer = bytearray(2)
                    self.channel.readfrom_into(self.I2C_ADDRESS, incoming_buffer)
                    raw_pressure = ((incoming_buffer[0] & 0x3F) << 8) | incoming_buffer[1] # Only bits 13-0, first two are status bit
                    return raw_pressure
                finally:
                    self.channel.unlock()
            else:
                return -1
        except Exception:
            return -1
        
    def _read_pressure_and_temp_digital(self) -> tuple[int, int]:
        """
        Read the pressure and temperature from the sensor in digital counts.

        Returns
        -------
        int
            Pressure in digital counts. -1 if there's an error.
        int
            Temperature in digital counts. -1 if there's an error.
        """
        try:
            if self.channel.try_lock():
                try:
                    incoming_buffer = bytearray(4)
                    self.channel.readfrom_into(self.I2C_ADDRESS, incoming_buffer)
                    raw_pressure = ((incoming_buffer[0] & 0x3F) << 8) | incoming_buffer[1] # Only bits 13-0, first two are status bit
                    raw_temperature = (incoming_buffer[2] << 3) | ((incoming_buffer[3] & 0xE0) >> 5) # All 3rd byte bits and top 3 bits of fourth byte for temperature
                    return (raw_pressure, raw_temperature)
                finally:
                    self.channel.unlock()
            else:
                return (-1, -1)
        except Exception:
            return (-1, -1)
    
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
    
    def _convert_temperature_C(self, digital_temperature: int) -> float:
        """
        Convert the temperature from digital counts to Celcius.

        Parameters
        ----------
        digital_temperature : int
            Temperature in digital counts.

        Returns
        -------
        float
            Temperature in Celcius.
        """
        temperature = (digital_temperature * self.TEMP_SPAN / self.TEMP_BITS_SPAN) + self.TEMP_MIN
        return temperature
    
    def _is_pressure_valid(self, pressure_hpa: float) -> bool:
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
    
    @property
    def pressure(self) -> float:
        """
        Get the pressure in hPa.

        Returns
        -------
        float
            Pressure, in hPa. -1 if there's an error.

        """
        digital_pressure = self._read_pressure_digital()
        hpa_pressure = self._convert_pressure_hpa(digital_pressure)
        
        if (self._is_pressure_valid(hpa_pressure)): return hpa_pressure
        return -1
    
    @property
    def triple_pressure(self) -> float:
        """
        Sample the pressure three times for a median.

        Returns
        -------
        float
            Median pressure. -1 if all 3 reads failed.

        """
        pressures = []
        for i in range(3):
            pressures.append(self.pressure)
            if i < 2: time.sleep(0.001)  # On the Nova Sensor, we can safely read at 1 kHz. Tested in lab 2/12/25
        return median([p for p in pressures if p != -1]) if max(pressures) != -1 else -1
    
    @property
    def temperature(self) -> float:
        """
        Get the temperature in Celcius.

        Returns
        -------
        float
            Temperature, in C. -1 if there's an error.
        """
        _, digital_temperature = self._read_pressure_and_temp_digital()

        if digital_temperature == -1: return digital_temperature

        return self._convert_temperature_C(digital_temperature)

    @property
    def triple_temperature(self) -> float:
        """
        Sample the temperature three times for a median.

        Returns
        -------
        float
            Median temperature, in C. -1 if all 3 reads failed.
        """
        temps = []
        for i in range(3):
            temps.append(self.temperature)
            if i < 2: time.sleep(0.001)  # On the Nova Sensor, we can safely read at 1 kHz. Tested in lab 2/12/25
        return median([t for t in temps if t != -1]) if max(temps) != -1 else -1

    @property
    def pressure_and_temp(self) -> tuple[float, float]:
        """
        Get the pressure and temperature in one read.

        Returns
        -------
        float
            Pressure, in hPa. -1 if there's an error.
        float
            Temperature, in C. -1 if there's an error.
        """
        digital_pressure, digital_temperature = self._read_pressure_and_temp_digital()
        ret_pressure = -1.0
        ret_temperature = -1.0

        if digital_pressure != -1:
            hpa_pressure = self._convert_pressure_hpa(digital_pressure)
            if (self._is_pressure_valid(hpa_pressure)):
                ret_pressure = hpa_pressure

        if digital_temperature != -1:
            ret_temperature = self._convert_temperature_C(digital_temperature)

        return (ret_pressure, ret_temperature)

    @property
    def triple_pressure_and_temp(self) -> tuple[float, float]:
        """
        Get the pressure and temperature in three reads.

        Returns
        -------
        float
            Pressure, in hPa. -1 if all 3 reads failed.
        float
            Temperature, in C. -1 if all 3 reads failed.
        """
        pressures = []
        temps = []
        for i in range(3):
            p, t = self.pressure_and_temp
            pressures.append(p)
            temps.append(t)
            if i < 2: time.sleep(0.001)  # On the Nova Sensor, we can safely read at 1 kHz. Tested in lab 2/12/25
        
        ret_pressure = median([p for p in pressures if t != -1]) if max(pressures) != -1 else -1
        ret_temp = median([t for t in temps if t != -1]) if max(temps) != -1 else -1

        return (ret_pressure, ret_temp)


class MPRLSFile(PressureSensor):
    """Handles virtualized MPRLS sensor playback from a file (for testing)."""
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self._load_data()
        self.index = 0
        self.cant_connect = False
    
    def _load_data(self):
        try:
            with open(self.file_path, 'r') as f:
                return [float(line.strip()) for line in f.readlines()]
        except Exception:
            self.cant_connect = True
            return []
    
    @property
    def pressure(self) -> float:
        if not self.data:
            return -1
        try:
            value = self.data[self.index]
        except IndexError:
            return -1
            print("MPRLSFile get_pressure: reached EOF")
        self.index = self.index + 1
        return value
    
    @property
    def triple_pressure(self) -> float:
        if not self.data:
            return -1
        pressures = [self.pressure for _ in range(3)]
        time.sleep(0.010) # MPRLS sample rate is 200 Hz https://forums.adafruit.com/viewtopic.php?p=733797
                          # Simulate 2 sleeps for reading from the actual sensor
        return median(pressures)

class MockPressureSensorStatic(PressureSensor):
    """Mock PressureSensor class to simulate pressure readings which are constant for testing."""

    def __init__(self, pressure: float, triple_pressure: Optional[float] = None):
        self._pressure_value = pressure
        if triple_pressure is None:
            self._triple_pressure_value = pressure
        else:
            self._triple_pressure_value = triple_pressure
            
        if self.pressure == -1 or self.triple_pressure == -1:
            self.cant_connect = True
        else:
            self.cant_connect = False

    @property
    def pressure(self) -> float:
        """Simulate getting a single pressure reading."""
        return self._pressure_value
    
    @pressure.setter
    def pressure(self, value):
        """
        Does nothing.
        """
        warn("You tried to set the pressure! There is something wrong with your implementation.")

    @property
    def triple_pressure(self) -> float:
        """Simulate getting a median of three pressure readings."""
        time.sleep(0.010) # MPRLS sample rate is 200 Hz https://forums.adafruit.com/viewtopic.php?p=733797
                          # Simulate 2 sleeps for reading from the actual sensor
        return self._triple_pressure_value
    
    @triple_pressure.setter
    def triple_pressure(self, value):
        """
        Does nothing.
        """
        warn("You tried to set the pressure! There is something wrong with your implementation.")