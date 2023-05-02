import sys
import os

class MultiPrinter:
    
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