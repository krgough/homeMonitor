#!/usr/bin/env python3
'''
Created on 8 Nov 2018

@author: Keith.Gough

Pairing Commands:
Bind to on/off cluster.
Write to the button press type cfg attribute to turn on all button press types.

# Only need these two
at+bind:<nodeId>,3,<BUTTON EUI>,01,0006,<COORD EUI>,01
at+rawzcl:<nodeId>,01,0006,0C3910010200FD181C

# Set attribute report configuration for the custom attribute
# (note it's a server to client)
at+cfgrpt:<nodeId>,0,0001,0,0020,20,0E10,0E10,01
at+rawzcl:<nodeId>,0006,0C391001060003FD1801000000

25/11/2019
Edited to comply with PEP8 (pylint).

'''
import time
import sys
import datetime
import threading
import queue
import re
import logging
import serial

LOGGER = logging.getLogger(__name__)
ZIGBEE_DEBUG = False
RX_QUEUE = queue.Queue()

# PORT for MAC Testing
PORT = "/dev/tty.SLAB_USBtoUART"
BAUD = 115200


def serial_read_handler(ser):
    """ Serial port read thread handler
        If serial timeout=None then this thread blocks until a new line is
        available
    """
    while True:
        reading = ser.readline().decode(errors='replace').strip()
        if reading != '':
            if RX_QUEUE.full():
                LOGGER.info("*** DEBUG: rxQ is full.  Dumping oldest message")
                RX_QUEUE.get()
            RX_QUEUE.put(reading)

            my_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
            LOGGER.debug("DEBUG RX: %s, %s", my_time, reading)


def main(port, baud, button_press_q):
    """ Main program
    """
    # Start Serial Rx thread
    try:
        serial_port = serial.Serial(port, baud, timeout=1)
        # global SER
        # SER = serialPort
    except IOError as err:
        LOGGER.error('Error opening port. %s', err)
        sys.exit()
    LOGGER.info("Serial port opened... %s", port)

    # Start the serial port handler thread
    read_thread = threading.Thread(target=serial_read_handler,
                                   args=(serial_port,))
    read_thread.daemon = True  # This kills the thread when main program exits
    read_thread.start()
    read_thread.name = 'readThread'
    LOGGER.info('Serial port read handler thread started.')

    # Monitor the Rx Queue and intercept button press messages
    while True:
        if not RX_QUEUE.empty():
            msg = RX_QUEUE.get()

            # If a button press command is received from any device then we
            # add a message to the button_press_q.

            # REPORTMATTR:{},01,1039,0006,FD03,18
            button_regex = "REPORTMATTR:[0-9a-fA-F]{4},01,1039,0006,FD03,18"
            if re.match(button_regex, msg):
                # Code number on end of the message is the button press type
                # 04 = Short press
                # 08 = double press
                # 10 = long press
                node_id = msg.split(':')[1][:4]
                msg_code = msg.split(',')[-1]
                button_press_q.put({"nodeId": node_id, "msgCode": msg_code})
                LOGGER.debug("BUTTON PRESS, %s, %s", node_id, msg_code)

            # ZONESTATUS:{},06,0020,00,01,0000
            pir_regex = "ZONESTATUS:[0-9a-fA-F]{4},06,0021"
            if re.match(pir_regex, msg):
                # On sensor modified to work as a switch
                # status '0020' = Button not pressed
                # status '0021' = Button pressed
                # We only want to trigger on button pressed as status get
                # reported periodically and would cause doorbell to ring
                # Can't remember which way round these map to open/closed
                # on normal sensor
                node_id = msg.split(':')[1][:4]
                msg_code = msg.split(",")[2]
                button_press_q.put({"nodeId": node_id, "msgCode": msg_code})
                LOGGER.debug("BUTTON PRESS, %s, %s", node_id, msg_code)

        time.sleep(0.1)


def test():
    """ Run this to test the button listener
    """
    button_press_q = queue.Queue()
    main(PORT, BAUD, button_press_q)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test()
