#used to generate a time file that RTCFile can read from during a whole run through

import time

output_log = open('fake_output_full_mission_sim.csv', 'w')
start_time = time.time()

while ((time.time() - start_time) < 5 ):
    output_log.write(str(time.time()) + "\n")

output_log.close()


