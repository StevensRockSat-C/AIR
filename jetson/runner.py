""" Run automatically with 
    sudo bash -c 'python3 -u ~/Documents/AIR/jetson/runner.py |& tee ~/Documents/$(date +%s%3N)_GPU_log.txt' &
    
    Or use a system service
        
        [Unit]
        Description=Benchmark Service

        [Service]
        Type=simple
        Environment=PYTHONPATH=/home/rocksat/.local/lib/python3.6/site-packages
        ExecStart=/bin/bash -c 'python3 -u /home/rocksat/Documents/AIR/jetson/runner.py |& tee /home/rocksat/Documents/$(date +%%s%%3N)_GPU_log.txt" &'

        [Install]
        WantedBy=multi-user.target
        
        
        sudo systemctl daemon-reload
        sudo systemctl enable benchmark-service.service
"""

# Settings
DEFAULT_BOOT_TIME = 20000   # The estimated time to boot and run the beginnings of the script, in MS. Will be used only if RTC is not live
VERSION = "1.0.2-alpha"

from ai_benchmark import AIBenchmark
import psutil, os, time

def main():
    try:
        p = psutil.Process(os.getpid())
        p.nice(-16) # Set this process to a higher priority. Could help us with GPU Memory issues
    except:
        print("Couldn't elevate process!! Are we not running as sudo?")
    
    print("Runner version " + str(VERSION))
    
    aib = AIBenchmark(verbose_level=2)
    
    print(str(time.time()) + " - Waiting for 120 second mark...")
    while get_uptime() < 120 - (DEFAULT_BOOT_TIME / 1000):
        pass
    
    try:
        results = aib.run_nano()
    except:
        print("Ran into an error. I guess let's shut down.")
    
    # Shutdown the system (No going back!)
    print("A mimir... zzz... " + str(get_uptime()) + " s")
    os.system("shutdown now")

def get_uptime():
    return time.time() - psutil.boot_time()

if __name__ == "__main__":
    # execute only if run as a script
    main()

