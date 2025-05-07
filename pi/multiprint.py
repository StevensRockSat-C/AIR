import sys
import os
from abc import ABC, abstractmethod
from tempfile import _TemporaryFileWrapper

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.absolute()))

class MultiPrinterAbstract(ABC):
    @abstractmethod
    def p(self, message, f):
        pass
    
    @abstractmethod
    def w(self, message, f):
        pass

    @abstractmethod
    def pform(self, message, tPlus, f):
        pass

class MultiPrinter(MultiPrinterAbstract):
    
    def __init__(self):
        self.ready = True
    
    def p(self, message, f):
        """
        
        Print to both the screen and a specified file.
        
        message:    The message to print and write
        f:          The file to write to
        
        """
        print(message)
        self.w(message, f)
            
    def w(self, message, f):
        """
        Only write and flush to the file
        """
        
        # This process should take roughly 1 ms / 1 KB written. f.flush and os.fsync should have execution times in the order of microseconds.
        try:
            f.write(message + "\n") # File.write doesn't automatically add a newline
            f.flush()               # Flush the data to the file
            os.fsync(f.fileno())    # Force the operating system to write the data to disk
        except IOError as e:
            print("COULD NOT WRITE TO THE INPUT FILE! Error: {}".format(e))
            
    def pform(self, message, tPlus, f):
        """
        message:    The message to print and write
        tPlus:      The mission tPlus
        f:          The file to write to
        
        Print to both the screen and a specified file and prepend the T+.
        """
        print("T+ " + str(tPlus) + " ms\t" + message)
        self.w("T+ " + str(tPlus) + " ms\t" + message, f)

class MockMultiPrinter(MultiPrinterAbstract):
    """
    Mock MultiPrinter for testing purposes.
    """
    def __init__(self):
        self.ready = True
        self.logs = {}

    def p(self, message, f: _TemporaryFileWrapper):
        """
        
        Print to both the screen and a specified file.
        
        message:    The message to print and write
        f:          The file to write to
        
        """
        if f.name not in self.logs:
            self.logs[f.name] = []
        print(message)
        self.logs[f.name].append(message)

    def w(self, message, f: _TemporaryFileWrapper):
        """
        Only write and flush to the file
        """
        if f.name not in self.logs:
            self.logs[f.name] = []
        self.logs[f.name].append(message)

    def pform(self, message, tPlus, f: _TemporaryFileWrapper):
        """
        message:    The message to print and write
        tPlus:      The mission tPlus
        f:          The file to write to
        
        Print to both the screen and a specified file and prepend the T+.
        """
        print("T+ " + str(tPlus) + " ms\t" + message)
        self.w("T+ " + str(tPlus) + " ms\t" + message, f)

