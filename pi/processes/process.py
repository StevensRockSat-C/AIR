from abc import ABC, abstractmethod
from io import TextIOWrapper
import sys
import os

if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from multiprint import MultiPrinter
from RTC import RTC

class Process(ABC):
    """
    Abstract base class for processes.
    """

    multiprint: MultiPrinter = None
    output_log: TextIOWrapper = None
    output_pressures: TextIOWrapper = None
    rtc: RTC = None
    
    @classmethod
    def set_multiprint(cls, multiprint: MultiPrinter):
        cls.multiprint = multiprint

    @classmethod
    def set_output_log(cls, output_log: TextIOWrapper):
        cls.output_log = output_log

    @classmethod
    def set_output_pressures(cls, output_pressures: TextIOWrapper):
        cls.output_pressures = output_pressures

    @classmethod
    def set_rtc(cls, rtc: RTC):
        cls.rtc = rtc

    def run(self):
        self.__initialize()
        self.__execute()
        self.__cleanup()

    @abstractmethod
    def __initialize(self):
        pass

    @abstractmethod
    def __execute(self):
        pass

    @abstractmethod
    def __cleanup(self):
        pass
