import sys
import os
from io import TextIOWrapper

class MultiPrinter:
    """An instanciable logger for continously writing and flushing to a file."""
    
    def __init__(self):
        self.ready = True
    
    def p(self, message: str, f: TextIOWrapper):
        """
        Print to the screen and write & flush a specified file.

        Parameters
        ----------
        message : str
            The string to print and write.
            Automatically terminated with a newline.
        f : TextIOWrapper
            The file to write to..

        Returns
        -------
        None.

        """
        print(message)
        self.w(message, f)
            
    def w(self, message: str, f: TextIOWrapper):
        """
        Only write and flush to the file.
        
        This process should take roughly 1 ms / 1 KB written.
        f.flush and os.fsync should have execution times
        in the order of microseconds.

        Parameters
        ----------
        message : str
            The string to print.
            Automatically terminated with a newline.
        f : TextIOWrapper
            The file to write to.

        Returns
        -------
        None.

        """
        try:
            f.write(message + "\n") # File.write doesn't automatically add a newline
            f.flush()               # Flush the data to the file
            os.fsync(f.fileno())    # Force the operating system to write the data to disk
        except IOError as e:
            print("COULD NOT WRITE TO THE INPUT FILE! Error: {}".format(e))
            
    def pform(self, message: str, tPlus: int, f: TextIOWrapper):
        """
        Format by prepending T+ to each message.
        
        Print to the screen and write & flush a specified file.

        Parameters
        ----------
        message : str
            The string to print and write.
        tPlus : int
            The T+ of the mission.
        f : TextIOWrapper
            The file to write to.

        Returns
        -------
        None.

        """
        print("T+ " + str(tPlus) + " ms\t" + message)
        self.w("T+ " + str(tPlus) + " ms\t" + message, f)
