#!/usr/bin/env python3
"""
Created on 20 Dec 2017

@author: Keith.Gough

Generate UART commands to drive HH360 LED board

9 RGB LEDS so 27byes of data.

We can send a table of rows, each row contains 9 LED values (RGB) plus holdtime
and fade time parameters. LED machine steps through the table rows and holds
then fades for the given times. Pattern starts after GO command is sent.

"""
# pylint: disable=logging-format-interpolation
# pylint: disable=pointless-string-statement

import getopt
import glob
import os
import sys
from textwrap import dedent

import queue
import threading
import datetime
import time
import enum
import logging
import serial


LOGGER = logging.getLogger(__name__)

TERM = 0xDE

# Partial command.  We must fill in the leds, fade, hold and TERM
LED_CMD = [0x01, 0xAA]

# Start from current row (for seamless animation)
GO_CMD = [0x02, TERM]
VER_CMD = [0x03, TERM]

# Start from row 0.  If current row is hold forever use to restart pattern.
START_CMD = [0x04, TERM]

HOLD_FOREVER = 65535


class Colours(enum.Enum):
    """Enum for LED colour values"""

    # noqa: e221
    OFF = [0x00, 0x00, 0x00]  # noqa: E221
    RED = [0xFF, 0x00, 0x00]  # noqa: E221
    AMBER = [0xFF, 60, 0x00]  # noqa: E221
    YELLOW = [0xFF, 125, 0x00]  # noqa: E221
    GREEN = [0x00, 0xFF, 0x00]  # noqa: E221
    GREEN_DIM = [0x00, 0x10, 0x00]  # noqa: E221
    GREEN_BLUE = [0x00, 0xFF, 60]  # noqa: E221
    BLUE_GREEN = [0x00, 0xFF, 180]  # noqa: E221
    BLUE = [0x00, 0x00, 0xFF]  # noqa: E221
    BLUE_DIM = [0x00, 0x00, 10]  # noqa: E221
    PURPLE = [0xFF, 0x00, 40]  # noqa: E221
    WHITE = [0xFF, 0xFF, 0xFF]  # noqa: E221


RAINBOW = (
    Colours.RED.value
    + Colours.AMBER.value
    + Colours.YELLOW.value
    + Colours.GREEN.value
    + Colours.GREEN_BLUE.value
    + Colours.BLUE_GREEN.value
    + Colours.BLUE.value
    + Colours.PURPLE.value
    + Colours.WHITE.value
)

RX_QUEUE = queue.Queue(maxsize=1000)
TX_QUEUE = queue.Queue(maxsize=1000)
LISTENER_QUEUE = queue.Queue(maxsize=1000)

STOP_THREAD = threading.Event()
THREAD_POOL = []


def read_args():
    # pylint: disable=too-many-branches
    """Read command line parameters"""
    all_colours = [colour.name for colour in Colours]
    all_patterns = list(COLOUR_PATTERNS.keys()) + list(NON_COLOUR_PATTERNS.keys())

    help_string = dedent(
        f"""
    USAGE: ./{os.path.basename(__file__)}
    -d port -b baud -p pattern -c colour [-h]

    LED Pattern Generator for HH360 LED board
    -d port       serial port /dev/...
    -b baud       usually 115200
    -p pattern    led pattern (see below)
    -c colour     led colour (see below)
    -h            Show this help
    -t            debug test

    Patterns with no colour choice (specify any - it will be ignored):
        {(os.linesep + '        ').join(NON_COLOUR_PATTERNS.keys())}

    Patterns with colour choice:
        {(os.linesep + '        ').join(COLOUR_PATTERNS.keys())}

    Colours:
        {(os.linesep + '        ').join(all_colours)}
    """
    )

    my_port = None
    my_baud = None
    my_pattern = False
    my_colour = None
    my_debug = False

    opts = getopt.getopt(sys.argv[1:], "htd:b:p:c:")[0]

    for opt, arg in opts:
        # print(opt, arg)
        if opt == "-h":
            print(help_string)
            sys.exit()
        if opt == "-d":
            my_port = arg
        if opt == "-b":
            my_baud = arg
        if opt == "-p":
            my_pattern = arg.upper()
            if my_pattern not in all_patterns:
                print(f"\nERROR: Pattern not recognised. pattern={my_pattern}")
                print(help_string)
                sys.exit()
        if opt == "-c":
            my_colour = arg.upper()
            if my_colour not in [col.name for col in Colours]:
                print("\nERROR: Colour not recognised.")
                print(help_string)
                sys.exit()
            my_colour = Colours[my_colour]
        if opt == "-t":
            my_debug = True

    if not my_port:
        print("\nERROR: UART port was not specified.  Try one of these...")
        print(glob.glob("/dev/tty.*"))
        print(help_string)
        sys.exit()

    if not my_baud:
        print("\nERROR: Baud rate not specified.  Typically we use 115200")
        print(help_string)
        sys.exit()

    if not my_pattern:
        print("\nERROR: Pattern not specified.  Try one of these:\n")
        print("\n".join(all_patterns))
        sys.exit()

    # Confirm we have a colour if we need one
    if my_pattern in list(COLOUR_PATTERNS.keys()):
        if not my_colour:
            print("\nERROR: Colour not specified.  Try one of these:\n")
            print("\n".join(all_colours))
            sys.exit()

    return my_port, my_baud, my_pattern, my_colour, my_debug


# Serial Port and Queue methods
def serial_read_handler(ser):
    """Serial port read thread handler
    If serial timeout=None then thread blocks until a new line is available
    """
    while not STOP_THREAD.isSet():
        reading = ser.read()
        # reading = ser.readline().decode(errors='replace').strip()
        if reading.hex() != "":
            # Make sure Qs are not full and blocking
            if RX_QUEUE.full():
                LOGGER.error("*** rxQueue is full.  Dumping oldest message")
                RX_QUEUE.get()
            RX_QUEUE.put(reading)

            my_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
            LOGGER.debug("DEBUG RX: %s,  %s", my_time, reading.hex())

    LOGGER.info("Serial read thread exit")


def serial_write_handler(ser):
    """Serial port write handler

    Get from a queue blocks if queue is empty so we just loop
    and wait for items

    """
    while not STOP_THREAD.isSet():
        try:
            my_message = TX_QUEUE.get(timeout=1)
            ser.write(my_message)
            my_time = datetime.datetime.now().strftime("%H:%M:%S.%f")
            my_print_message = [f"0x{x:02x}" for x in my_message]
            LOGGER.debug("DEBUG Tx: %s,  %s", my_time, my_print_message)

        except queue.Empty:
            time.sleep(0.1)
    LOGGER.info("Serial write thread exit")


def start_serial_threads(port, baud):
    """Start read and write threads for the led serial port"""
    try:
        serial_port = serial.Serial(port, baud, bytesize=8, timeout=1)
    except IOError as err:
        LOGGER.error("Error opening port. %s", err)
        sys.exit()
    LOGGER.info("Serial port opened: %s", port)

    # Make sure the stopThread event is not set
    STOP_THREAD.clear()

    # Start the serial port handler thread
    read_thread = threading.Thread(target=serial_read_handler, args=(serial_port,))
    read_thread.daemon = True  # This kills the thread when main program exits
    read_thread.start()
    read_thread.name = "read_thread"
    THREAD_POOL.append(read_thread)
    LOGGER.info("Serial port read handler thread started.")

    # interCharDelay=0.05
    write_thread = threading.Thread(target=serial_write_handler, args=(serial_port,))
    write_thread.daemon = True  # This kills the thread when main program exits
    write_thread.start()
    write_thread.name = "write_thread"
    THREAD_POOL.append(write_thread)
    LOGGER.info("Serial port write handler thread started.")


def stop_threads():
    """Set the stop event and wait for all threads to exit
    Close the serial port

    """
    STOP_THREAD.set()
    for thd in THREAD_POOL:
        thd.join()


def flush_rx_queue():
    """Flush messages from the RxQ"""
    time.sleep(0.1)
    while not RX_QUEUE.empty():
        msg = RX_QUEUE.get()
        LOGGER.debug("Dumping=%s", msg)


def send_command(cmd, resp_value_expected=False, timeout=2):
    # pylint: disable=too-many-branches, too-many-statements
    # pylint: disable=too-many-nested-blocks
    """resp_value_expected defines whether or not we expect a value in the
    response (2nd Byte). Currently only the software version command
    gives a response value

    First byte is always 0xN* where:
    N = 0x00 - ACK
        0x01 - Unknown command
        0x02 - Illegal arg values
        0x03 - Table full
        0x04 - Insufficient args received
        0x05 - Busy (retry)

    * = Lower nibble of the command byte
    """

    flush_rx_queue()

    timeout = time.time() + timeout

    try_count = 0
    state = "sendCmd"
    resp = None
    resp_state = False
    resp_value = None

    while True:
        time.sleep(0.1)  # Sleep to stop thread spinning

        if state == "sendCmd":
            LOGGER.debug("sendCmd = %s", cmd)
            if try_count < 3:
                TX_QUEUE.put(cmd)
                try_count += 1
                state = "waitForCmdResponse"
            else:
                resp_value = "TIMEOUT: 3x retries without correct response"
                state = "return"

        elif state == "waitForCmdResponse":
            LOGGER.debug("waitForCmdResponse")
            if time.time() < timeout:
                if not RX_QUEUE.empty():
                    resp = int.from_bytes(RX_QUEUE.get(), "big")
                    # respInt = int.from_bytes(resp,'big')
                    LOGGER.debug("resp = %s", resp)
                    if resp & 0x0F == cmd[0]:

                        if resp & 0xF0 == 0x00:
                            resp_value = "ACK"
                            if resp_value_expected:
                                state = "valueExpected"
                            else:
                                resp_state = True
                                state = "return"
                        elif resp & 0xF0 == 0x10:
                            resp_value = "Unknown Command"
                            state = "return"
                        elif resp & 0xF0 == 0x20:
                            resp_value = "Illegal arg values"
                            state = "return"
                        elif resp & 0xF0 == 0x30:
                            resp_value = "Table full"
                            state = "return"
                        elif resp & 0xF0 == 0x40:
                            resp_value = "Insufficient args received"
                            state = "sendCmd"
                        elif resp & 0xF0 == 0x50:
                            resp_value = "Busy"
                            state = "return"
                        LOGGER.debug("resp_value = %s", resp_value)
            else:
                LOGGER.debug("timeout waiting for expected response")
                # If we get here we had a timeout
                state = "sendCmd"

        # If we expect the device to send us another response after the ACK
        # e.g. SW version, we spin here until we get a value or we timeout
        elif state == "valueExpected":
            if time.time() < timeout:
                if not RX_QUEUE.empty():
                    resp_value = int.from_bytes(RX_QUEUE.get(), "big")
                    resp_state = True
                    state = "return"
            else:
                resp_value = "Timeout: Response value not recieved"
                state = "return"
            LOGGER.debug("resp_value = %s", resp_value)

        elif state == "return":
            return resp, resp_state, resp_value

        else:
            LOGGER.error("ERROR: Unkonwn state in send_command state machine")
            return resp, resp_state, resp_value

    return resp, resp_state, resp_value


def send_led_cmds(cmds):
    """Send LED commands to the device"""
    for cmd in cmds:
        resp, resp_state, resp_value = send_command(cmd)

        # Return early if any one of the commands fails
        if not resp_state:
            LOGGER.debug(
                "Cmd failed: cmd=%s, resp=%s, resp_value=%s", cmd, resp, resp_value
            )
            return resp_state, resp_value

    return resp_state, resp_value


# Pattern generator helpers
def time_to_bytes(my_time):
    """Convert time in ms to 2-bytes in little endian format
    min = 0s, max = 65.535s (i.e. 0xFFFF)
    """
    my_time_hex = f"{my_time:04x}"
    return [int(my_time_hex[2:4], 16), int(my_time_hex[0:2], 16)]


def leds_all_same_colour(colour):
    """Return led values for all 9 leds set to the wanted colour
    Colour is an RGB triplet in the form [0x01,0x02,0x03]
    """
    return colour * 9


def led_rotate_pattern(pattern, shift):
    """Returns the given list shifted right the given number of places."""
    my_pattern = pattern[:]
    shift = shift % len(my_pattern)
    head = my_pattern[:shift]
    del my_pattern[:shift]
    my_pattern.extend(head)
    return my_pattern


def led_left_shift_pattern(pattern, shift):
    """left shift the pattern by 'shift' led places"""
    shift = shift * 3
    pattern = pattern[shift:] + ([0x00] * shift)
    return pattern


def led_right_shift_pattern(pattern, shift):
    """right shift led pattern"""
    shift = shift * 3
    pattern = ([0x00] * shift) + pattern[: len(pattern) - shift]
    return pattern


def all_on_pattern(pattern):
    """Build a given fixed pattern"""
    row = build_led_row_cmd(pattern)
    return row


def chase_me(colour, direction=True):
    """dir=True for CW and False for CCW"""
    rows = []

    # First make an LED row with LED1 on, LED9 at 60% and LED8 at 30%
    led_dim_2 = [int(a * 0.01) for a in colour.value]
    led_dim_1 = [int(a * 0.3) for a in colour.value]

    if direction:
        leds = colour.value + Colours.OFF.value * 6 + led_dim_2 + led_dim_1
    else:
        leds = colour.value + led_dim_1 + led_dim_2 + Colours.OFF.value * 6

    # Now make 9 rows for the chase pattern
    fade_time = 0
    hold_time = 150
    for i in range(0, 9):
        if direction:
            i = -i
        pattern = led_rotate_pattern(leds, i * 3)
        row = build_led_row_cmd(pattern, fade_time, hold_time)
        rows.append(row)
    return rows


def build_led_row_cmd(row_pattern, fade_time=0, hold_time=HOLD_FOREVER):
    """Build a row command of the form:
    LED_CMD + Pattern + fade_time + hold_time + TERM

    Defaults of fade_time=0 and hold_time=0xFFFF give a static pattern
    """
    row = (
        LED_CMD
        + row_pattern
        + time_to_bytes(fade_time)
        + time_to_bytes(hold_time)
        + [TERM]
    )
    return row


# Pattern generator functions
def strobe(colour):
    """Build strobe pattern - double flash then off"""
    fade_time = 0
    hold_time = 100
    final_hold_time = 700

    patt_on = leds_all_same_colour(colour.value)
    patt_off = leds_all_same_colour(Colours.OFF.value)

    row_1 = build_led_row_cmd(patt_on, fade_time, hold_time)
    row_2 = build_led_row_cmd(patt_off, fade_time, hold_time)
    row_3 = build_led_row_cmd(patt_on, fade_time, hold_time)
    row_4 = build_led_row_cmd(patt_off, fade_time, final_hold_time)
    rows = [row_1, row_2, row_3, row_4]
    return rows


def breathing(colour):
    """Breathing pattern is...
    Fade to all on and hold
    Fade to all off and hold
    ...
    """
    fade_time = 2000
    hold_time = 100
    my_led_dim = [int(a / 20) for a in colour.value]
    patt_dim = leds_all_same_colour(my_led_dim)
    patt_same = leds_all_same_colour(colour.value)
    row_1 = build_led_row_cmd(patt_dim, fade_time, hold_time)
    row_2 = build_led_row_cmd(patt_same, fade_time, hold_time)
    rows = [row_1, row_2]
    return rows


def chase_cw(colour):
    """Chase pattern clockwise"""
    return chase_me(colour, True)


def chase_ccw(colour):
    """Chase pattern counter clockwise"""
    return chase_me(colour, False)


def clock(colour):
    """Build the clock pattern
    All on, then 1off, then 1 and 2 off, then 1,2,3 off etc..
    Final state is #9 on only.
    """
    pattern = leds_all_same_colour(colour.value)
    rows = []
    fade_time = 0
    hold_time = 500
    for i in range(0, 8):
        patt = led_right_shift_pattern(pattern, i)
        rows.append(build_led_row_cmd(patt, fade_time, hold_time))
    # Last row is hold forever
    row_pattern = [0x00, 0x00, 0x00] * 8 + colour.value
    rows.append(build_led_row_cmd(row_pattern, fade_time, HOLD_FOREVER))
    return rows


def all_on(colour):
    """Build all on with a given colour"""
    rows = [build_led_row_cmd(leds_all_same_colour(colour.value))]
    return rows


def no_delays(colour):
    """Top LED on at 50%, all others off"""
    rows = [build_led_row_cmd(Colours.OFF.value * 8 + colour.value)]
    return rows


COLOUR_PATTERNS = {
    "STROBE": strobe,
    "BREATHING": breathing,
    "CHASECW": chase_cw,
    "CHASECCW": chase_ccw,
    "CLOCK": clock,
    "ALL_ON": all_on,
    "NO_DELAYS": no_delays,
}


def rgb_funk():
    """Build RGB funk pattern"""
    row_1_leds = (
        Colours.RED.value * 3 + Colours.GREEN.value * 3 + Colours.BLUE.value * 3
    )
    row_2_leds = (
        Colours.GREEN.value * 3 + Colours.BLUE.value * 3 + Colours.RED.value * 3
    )
    row_3_leds = (
        Colours.BLUE.value * 3 + Colours.RED.value * 3 + Colours.GREEN.value * 3
    )

    fade_time = 100
    hold_time = 100

    row_1 = build_led_row_cmd(row_1_leds, fade_time, hold_time)
    row_2 = build_led_row_cmd(row_2_leds, fade_time, hold_time)
    row_3 = build_led_row_cmd(row_3_leds, fade_time, hold_time)
    rows = [row_1, row_2, row_3]
    return rows


def rgb_rotate():
    """Build RGB rotate pattern"""
    leds = Colours.RED.value * 3 + Colours.GREEN.value * 3 + Colours.BLUE.value * 3
    rows = []
    fade_time = 0
    hold_time = 200
    for i in range(0, 9):
        patt = led_rotate_pattern(leds, i * 3)
        rows.append(build_led_row_cmd(patt, fade_time, hold_time))
    return rows


def all_on_funk(pattern=None):
    """Build the all_on_funk pattern"""
    if pattern is None:
        pattern = RAINBOW
    fade_time = 500
    hold_time = 100
    rows = []
    for i in range(0, 9):
        new_patt = led_rotate_pattern(pattern, i * -3)
        rows.append(build_led_row_cmd(new_patt, fade_time, hold_time))
    return rows


NON_COLOUR_PATTERNS = {
    "RGB_FUNK": rgb_funk,
    "RGB_ROTATE": rgb_rotate,
    "RAINBOW_FUNK": all_on_funk,
}


def unit_test():
    """Unit test all patterns and colours"""
    port = ""
    if port == "":
        print("ERROR: set port variable in unit_test()")
        sys.exit()
    baud = 115200
    start_serial_threads(port, baud)

    # First get the LED Board FW version
    _, resp_state, resp_value = send_command(VER_CMD, resp_value_expected=True)
    if resp_state:
        print(f"Version={resp_value}")
    else:
        print(f"Error: resp={resp_value}")

    for pattern in COLOUR_PATTERNS:
        for colour in Colours:
            print(f"Pattern={pattern}, Colour={colour.name}")
            show_pattern(pattern, colour, True)
            input("Check the pattern")

    for pattern in NON_COLOUR_PATTERNS:
        print(f"Pattern={pattern}")
        show_pattern(pattern, None, True)
        input("Check the pattern")


def show_pattern(pattern, colour, debug=False):
    """Show the given patten"""
    # Capture the error cases
    if pattern in COLOUR_PATTERNS and colour is None:
        LOGGER.error(
            (
                "Colour pattern specified but no colour given.  "
                "pattern=%s, colour=%s",
                pattern,
                colour,
            )
        )
        return False

    if pattern in NON_COLOUR_PATTERNS and colour:
        LOGGER.info(
            (
                "Non-Colour pattern specified but a colour was specified.  "
                "Colour was ignored.  pattern=%s, colour=%s",
                pattern,
                colour,
            )
        )

    if COLOUR_PATTERNS.get(pattern):
        cmds = COLOUR_PATTERNS[pattern](colour)

    elif NON_COLOUR_PATTERNS.get(pattern):
        cmds = NON_COLOUR_PATTERNS[pattern]()

    else:
        LOGGER.error("Pattern was not found in COLOUR_PATTERNS")
        return False

    LOGGER.info("Pattern=%s, Colour=%s", pattern, colour)
    for cmd in cmds:
        LOGGER.debug(cmd)

    if debug is False:
        send_led_cmds(cmds)
        send_command(START_CMD)

    return True


def main():
    """Main Program"""
    port, baud, pattern, colour, debug = read_args()
    if not debug:
        logging.basicConfig(level=logging.INFO)
        start_serial_threads(port, baud)

    show_pattern(pattern, colour, debug)


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    # unit_test()

    logging.basicConfig(level=logging.INFO)
    main()
