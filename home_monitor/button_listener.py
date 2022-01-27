#!/usr/bin/env python3
"""
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

Adding some code to listen for the temperature reports from a contact sensor.
This sensor will be placed in the garage freezer.  If the temp rises above
our threshold then we warn the users (email or blue light??)

"""

import time
import sys
import datetime
import threading
import queue
import re
import logging
import serial

from udpcomms import hex_temp

LOGGER = logging.getLogger(__name__)
ZIGBEE_DEBUG = False
RX_QUEUE = queue.Queue()

# PORT for MAC Testing
PORT = "/dev/tty.SLAB_USBtoUART"
BAUD = 115200


def start_serial_port_thread(port, baud):
    """Start a thread to read serial port

    Puts incomming messages on the RX_QUEUE
    """
    # Start the serial port handler thread
    read_thread = threading.Thread(target=serial_read_handler, args=(port, baud))
    read_thread.daemon = True  # This kills the thread when main program exits
    read_thread.start()
    read_thread.name = "readThread"
    LOGGER.info("Serial port read handler thread started.")

    return read_thread


def serial_read_handler(port, baud):
    """Serial port read thread handler

    If serial timeout=None then thread blocks until a new line is available
    """
    # Open the serial port
    try:
        ser = serial.Serial(port, baud, timeout=1)
        # global SER
        # SER = serialPort
    except IOError as err:
        LOGGER.error("Error opening port. %s", err)
        sys.exit()
    LOGGER.info("Serial port opened... %s", port)

    while True:
        reading = ser.readline().decode(errors="replace").strip()
        if reading != "":
            if RX_QUEUE.full():
                LOGGER.info("*** DEBUG: rxQ is full.  Dumping oldest message")
                RX_QUEUE.get()
            RX_QUEUE.put(reading)

            my_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
            LOGGER.debug("DEBUG RX: %s, %s", my_time, reading)


def main(port, baud, button_press_q):
    """Main program"""
    read_thread = start_serial_port_thread(port=port, baud=baud)

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
                node_id = msg.split(":")[1][:4]
                msg_code = msg.split(",")[-1]
                button_press_q.put({"nodeId": node_id, "msgCode": msg_code})
                LOGGER.debug("BUTTON PRESS, %s, %s", node_id, msg_code)

            # ZONESTATUS:{},06,0020,00,01,0000
            # REPORTATTR:C23A,06,0402,0000,29,FBB4
            # Catch temperature reports
            contact_regex = "REPORTATTR:[0-9a-fA-F]{4},06,0402,0000,29"
            if re.match(contact_regex, msg):
                # On PIR 0020/0021 = open/closed
                # On Contact we are moitoring temperature
                node_id = msg.split(":")[1][:4]
                temperature = msg.split(",")[-1]
                temperature = hex_temp.convert_s16(temperature) / 100

                button_press_q.put({"nodeId": node_id, "temperature": temperature})

                LOGGER.debug("TEMPERATURE, %s, %s", node_id, temperature)

        # Check our serial thread is still alive
        if not read_thread.is_alive():
            LOGGER.debug("Button listener serial read thread has exited")
            return

        # Sleep to stop loop spinning
        time.sleep(0.1)


def test():
    """Run this to test the button listener"""
    button_press_q = queue.Queue()
    main(port=PORT, baud=BAUD, button_press_q=button_press_q)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test()
