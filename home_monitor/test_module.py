#!/usr/bin/env python3
'''
Created on 21 Feb 2021

@author: keithgough
'''

import logging
import time
import zigbeetools.threaded_serial as at


LOGGER = logging.getLogger(__name__)

def main():
    """ Main Program """
    threads = at.start_serial_threads(port="/dev/HIVE_DONGLE",
                                      baud=115200,
                                      print_status=False,
                                      rx_q=True)

    while True:
        while not at.RX_QUEUE.empty():
            msg = at.RX_QUEUE.get()
            # CHECKIN:2F28,06
            if msg.startswith("CHECKIN"):
                LOGGER.debug("CHECKIN RECEIVED")
                node_id = msg.split(',')[0].split(":")[1]

                dongle_eui = "000D6F000C44F290"
                sensor_eui = "00124B0015D56962"
                report_interval = "{:04x}".format(60 * 10)
                bind_msg = "at+bind:{node_id},3,{sensor_eui},06,0402,{dongle_eui},01"
                set_report = "at+cfgrpt:{node_id},06,0,0402,0,0000,29,0001,{report_interval},0001"
                at.TX_QUEUE.put(bind_msg.format(node_id=node_id,
                                                sensor_eui=sensor_eui,
                                                dongle_eui=dongle_eui))
                
                at.TX_QUEUE.put(set_report.format(node_id=node_id,
                                                  report_interval=report_interval))

        time.sleep(0.1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()