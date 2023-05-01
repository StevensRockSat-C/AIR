# Settings
DEFAULT_BOOT_TIME = 35000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live

from ai_benchmark import AIBenchmark
import psutil, os, time

def main():
    try:
        p = psutil.Process(os.getpid())
        p.nice(-15) # Set this process to a higher priority. Could help us with GPU Memory issues
    except:
        print("Couldn't elevate process!! Are we not running as sudo?")
    
    aib = AIBenchmark(verbose_level=2)
    
    while get_uptime() < 120 - (DEFAULT_BOOT_TIME / 1000):
        pass
    
    results = aib.run_nano()

def get_uptime():
    return time.time() - psutil.boot_time()

if __name__ == "__main__":
    # execute only if run as a script
    main()

