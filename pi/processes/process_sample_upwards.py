import sys
import os
from warnings import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pi.processes.process import Process
from pi.collection import Collection

class SampleUpwards(Process):

    def __init__(self):
        self.collections: list[Collection] = []

    def set_collections(self, collections: list[Collection]):
        self.collections = collections
        
    def run(self) -> bool:
        print(type(Process.get_multiprint()))
        if not Process.is_ready():
            warn("Process is not ready for Sample Upwards!")
            if Process.can_log():
                Process.get_multiprint().pform("Process is not ready for Sample Upwards!", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            return False
        if not self.initialize():
            return False
        self.execute()
        self.cleanup()
        return True

    def initialize(self) -> bool:
        Process.get_multiprint().pform("Initializing Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
        if not self.collections:
            Process.get_multiprint().pform("Collections not set for Sample Upwards! Aborting Process.", Process.get_rtc().getTPlusMS(), Process.get_output_log())
            warn("Collections not set for Sample Upwards!")
            return False
        return True

    def execute(self):
        Process.get_multiprint().pform("Performing Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())

    
    def cleanup(self):
        Process.get_multiprint().pform("Finished Sample Upwards.", Process.get_rtc().getTPlusMS(), Process.get_output_log())