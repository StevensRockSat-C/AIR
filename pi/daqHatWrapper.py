from daqhats import mcc128, OptionFlags, HatIDs, AnalogInputMode, \
    AnalogInputRange
from daqhats_utils import select_hat_device, chan_list_to_mask
from time import sleep, time


def timeMS():
    """Get system time to milliseconds."""
    return time() * 1000
       
class WrapDAQHAT:
    """Wrap the DAQHAT library for ease of use."""
    
    #hat-id for 128 is 326, according to the library reference
    def __init__(self, mprint, mainLogFile, chanList=[0,1,2,4,5,6], debug=False, hat_id=326, sampleRate=6400): #open port/channel
        self.hat_id = hat_id
        self.sampleRate = sampleRate #with 6400 samples, can do 10 kS
        self.samples_per_channel = 0
        self.channelList = chan_list_to_mask(chanList)
        self.numChannels = len(chanList)
        self.mainLogFile = mainLogFile
        self.debug = debug
        self.mprint = mprint
        self.overrun = False
        self.outputLog = open(str(time()) + '_AccelerationData.csv', 'w') #open file to write to, name it outputLog
        self.connected = False
        self.connectionAttempts = 0
        
        self.__connect_to_MCC()

    def __connect_to_MCC(self):
        """
        Attempt to connect to the MCC. Try-except protected.

        Returns
        -------
        Boolean
            Whether we are connected to the MCC128.

        """
        self.connectionAttempts += 1
        try:
            self.address = select_hat_device(HatIDs.MCC_128)
            self.hat = mcc128(self.address)
            
            self.hat.a_in_mode_write(AnalogInputMode.SE)
            self.hat.a_in_range_write(AnalogInputRange.BIP_5V)
            self.hat.a_in_scan_start(self.channelList, self.samples_per_channel, self.sampleRate, OptionFlags.CONTINUOUS)
            self.connected = True
        except Exception as err:
            self.connected = False
            self.mprint.p("FAILED TO CONNECT TO MCC128!! Error: " + str(err) + "\n\tTime: " + str(timeMS()) + " ms", self.mainLogFile)
        return self.connected
    
    
    def close(self):
        """
        Close the log and the connection to the MCC128.

        Returns
        -------
        None.

        """
        self.outputLog.close()
        self.hat.a_in_scan_stop() #stopping continuous scan
        self.hat.a_in_scan_cleanup() #cleaning up


    def __write_data_to_csv(self, data, endTime):
        """
        Write buffer data to the csv file.
        
        Inputs:
            data: data in 1D list 
            numChannels: number of channels daqHat reading from
            startTime: time started reading data (in microseconds)
        
        Output: 
            saves data to file given with timestamps in leftmost column 
            using multiprint
        """
        data_csv = ''
        for row in range(int(len(data)/self.numChannels)):
            data_csv += ("," if (row != int(len(data)/self.numChannels) - 1) else (str(endTime) + ",")) # Only write timestamp to last value
            for i in range(self.numChannels):
                data_csv += ("," + str(data[row*self.numChannels + i]))
            data_csv += "\n"
        data_csv = data_csv.removesuffix("\n") # Remove trailing newline
        self.mprint.p(data_csv, self.outputLog)

    def read_buffer_write_file(self, endTime=timeMS()):
        """
        Get the current buffer and write it to the file.

        Parameters
        ----------
        endTime : int
            The time to append to the last sample in the CSV.

        Returns
        -------
        Whether the buffer has overrun, or False if MCC isn't connected.
        """
        read_request_size = -1      #read all available in buffer
        timeout = 0     # Use 0 timeout to immediately read the buffer's contents, instead of waiting for it to fill.
        
        if not self.connected:
            self.__connect_to_MCC()
            if not self.connected: return False
            
        try:
            buffer_data = self.hat.a_in_scan_read(read_request_size, timeout)
            self.__write_data_to_csv(buffer_data.data, endTime)
            
            if (buffer_data.hardware_overrun | buffer_data.buffer_overrun):
                        self.overrun = True
            return self.overrun
        except:
            self.mprint.p("WAS CONNECTED TO MCC128 BUT CAN'T GET DATA!! Time: " + str(timeMS()) + " ms", self.mainLogFile)
            self.connected = False
            return False
    
