from abc import ABC, abstractmethod
from io import TextIOWrapper
from tempfile import _TemporaryFileWrapper
import time
from typing import Union
from warnings import warn
import os
from enum import Enum

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.absolute()))

from pi.multiprint import MultiPrinter, MultiPrinterAbstract
from pi.RTC import RTC

class PlumbingState(Enum):
    """
    An enumeration to represent the state at which the plumbing is in.
    """
    READY = 1
    MAIN_LINE_FAILURE = 2

class Process(ABC):
    """
    Abstract base class for processes.
    """

    multiprint: MultiPrinterAbstract = None
    output_log: Union[TextIOWrapper, _TemporaryFileWrapper] = None
    output_pressures: Union[TextIOWrapper, _TemporaryFileWrapper] = None
    rtc: RTC = None
    plumbing_state: PlumbingState = PlumbingState.READY
    
    @classmethod
    def set_multiprint(cls, multiprint: MultiPrinter):
        cls.multiprint = multiprint

    @classmethod
    def set_output_log(cls, output_log: Union[TextIOWrapper, _TemporaryFileWrapper]):
        cls.output_log = output_log

    @classmethod
    def set_output_pressures(cls, output_pressures: Union[TextIOWrapper, _TemporaryFileWrapper]):
        cls.output_pressures = output_pressures

    @classmethod
    def set_rtc(cls, rtc: RTC):
        cls.rtc = rtc

    @classmethod
    def set_plumbing_state(cls, plumbing_state: PlumbingState):
        cls.plumbing_state = plumbing_state

    @classmethod
    def get_multiprint(cls):
        return cls.multiprint

    @classmethod
    def get_output_log(cls):
        return cls.output_log

    @classmethod
    def get_output_pressures(cls):
        return cls.output_pressures

    @classmethod
    def get_rtc(cls):
        return cls.rtc
    
    @classmethod
    def get_plumbing_state(cls):
        return cls.plumbing_state

    @classmethod
    def is_ready(cls):
        if not isinstance(cls.multiprint, MultiPrinterAbstract):
            warn("MultiPrinter not set for Process! " + str(type(cls.multiprint)))
        if not isinstance(cls.output_log, (TextIOWrapper, _TemporaryFileWrapper)):
            warn("Output log not set for Process! " + str(type(cls.output_log)))
        if not isinstance(cls.rtc, RTC):
            warn("RTC not set for Process! " + str(type(cls.rtc)))
            cls.multiprint.p("RTC not set for Process! Time: " + str(round(time.time()*1000)) + " ms:", cls.output_log) # TODO: Use refactor timeMS() into Utils class
        if not isinstance(cls.output_pressures, (TextIOWrapper, _TemporaryFileWrapper)):
            warn("Output pressures not set for Process! " + str(type(cls.output_pressures)))
            cls.multiprint.pform("Output pressures not set for Process!", cls.rtc.getTPlusMS(), cls.output_pressures)
        return (isinstance(cls.multiprint, MultiPrinterAbstract) and 
                isinstance(cls.output_log, (TextIOWrapper, _TemporaryFileWrapper)) and 
                isinstance(cls.output_pressures, (TextIOWrapper, _TemporaryFileWrapper)) and 
                isinstance(cls.rtc, RTC))
    
    @classmethod
    def can_log(cls):
        """
        Check if the Process is ready to log.
        """
        return isinstance(cls.multiprint, MultiPrinterAbstract) and isinstance(cls.output_log, (TextIOWrapper, _TemporaryFileWrapper)) and isinstance(cls.rtc, RTC)

    @abstractmethod
    def run(self) -> bool:
        if not self.__class__.is_ready():
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def execute(self) -> bool:
        pass

    @abstractmethod
    def cleanup(self) -> bool:
        pass
