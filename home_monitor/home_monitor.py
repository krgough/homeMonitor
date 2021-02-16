#!/usr/bin/env python3
'''
Created on 7 Nov 2018

@author: Keith.Gough

Application to Monitor train departures and indicate delays

Indication is by setting a pattern on an attached HH360 LED board or,
by setting a Hive colour bulb to e.g. RED and ON.

User can then use an associated ZigBee button to trigger a voice announcement
for the delayed train services.

25/11/2019 Keith Gough
PEP8 Updates.

'''


import os
import sys
import getopt
import json
import time
import datetime
import threading
import queue
from textwrap import dedent
import logging.config
import yaml

import udpcomms.hot_water_udp_client as udp_cli
import zigbeetools.threaded_serial as at

import train_times as tt
import led_pattern_generator as led
import button_listener as bl
import config as cfg
# import api_methods as api  # old hive API's (now closed down)
import zigbee_methods as api  # Control using Zigbee AT commands
import gpio_monitor as gm


CHECK_THREAD_STOP = threading.Event()
THREAD_POOL = []
DELAY_CHECK_SLEEP_TIME = 5 * 60


def get_args():
    """ Read command line parameters
    """
    # NOTE to self - Cannot use f strings in python ver < 3.6
    help_string = dedent("""
    USAGE: {} [-h] [-l] [-b] [-g] [-z] -t to_station -f from_station

    Use these command line options:

    -h                      Print this help
    -l                      Show delays on HH360 LED indicator board

    -b                      Show delays on hive colour bulb
                            See apiConfig.py for login details

    -g                      Monitor gpio button presses
                            Make announcement if button presssed)

    -z                      Announce delays on zigbee button press

    -t 'to' stationId       CRS code for station e.g. wat for Waterloo
    -f 'from' stationId     CRS code for station
    """.format(os.path.basename(__file__)))

    to_station = None
    from_station = None
    use_leds = False
    use_hive = False
    use_gpios = False
    zigbee_button = False

    opts = getopt.getopt(sys.argv[1:], "hlgbzt:f:")[0]

    for opt, arg in opts:
        # print(opt, arg)
        if opt == '-h':
            print(help_string)
            sys.exit()
        if opt == '-t':
            to_station = arg
        if opt == '-f':
            from_station = arg
        if opt == '-l':
            use_leds = True
        if opt == '-b':
            use_hive = True
        if opt == '-z':
            zigbee_button = True
        if opt == '-g':
            use_gpios = True

    if not to_station:
        print("Error: toStation was not specified")
        print(help_string)
        sys.exit()

    if not from_station:
        print("Error: fromStation was not specified")
        print(help_string)
        sys.exit()

    return (to_station, from_station, use_leds, use_gpios,
            use_hive, zigbee_button)


def configure_logger(logger_name, log_path=None):
    """ Logger configuration function
        If log_path given then log to console and to the file
        else to console only.
    """
    version = 1
    disable_existing_loggers = False
    formatters = {'default':
                  {'format': '%(asctime)s,%(levelname)s,%(name)s,%(message)s',
                             'datefmt': '%Y-%m-%d %H:%M:%S'}
                  }

    console_handler = {'level': 'DEBUG',
                       'class': 'logging.StreamHandler',
                       'formatter': 'default',
                       'stream': 'ext://sys.stdout'}

    file_handler = {'level': 'DEBUG',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'formatter': 'default',
                    'filename': log_path,
                    'maxBytes': 100000,
                    'backupCount': 3}

    if log_path:
        logging.config.dictConfig({
            'version': version,
            'disable_existing_loggers': disable_existing_loggers,
            'formatters': formatters,
            'handlers': {'file': file_handler},
            'loggers': {'': {'level': 'DEBUG', 'handlers': ['file']}}
        })
    else:
        logging.config.dictConfig({
            'version': version,
            'disable_existing_loggers': disable_existing_loggers,
            'formatters': formatters,
            'handlers': {'console': console_handler},
            'loggers': {'': {'level': 'DEBUG', 'handlers': ['console']}}
        })

    logging.getLogger('requests').setLevel(logging.WARNING)

    return logging.getLogger(logger_name)


def timestamp_from_time_string(time_string):
    """ Takes a time_string of the form HH:MM and returns seconds
    """
    hours, minutes = time_string.split(":")
    seconds = (int(hours) * 60 * 60) + (int(minutes) * 60)
    return seconds


def flush_queue(my_queue):
    """ Flush the give queue
    """
    while not my_queue.empty():
        my_queue.get()


# Train functions
def get_station_name(crs_code):
    """ Get the station name for the given crs code
    """
    station_name = None
    # Get all the crs codes
    resp_status, resp = tt.get_stations()
    if resp_status:
        stations = json.loads(resp.text)
        for station in stations:
            if crs_code.upper() == station['crsCode']:
                return station['stationName']
    return station_name


def schedule_check():
    """ Returns true if current time is an ON time for indications else false
    """
    now = datetime.datetime.now()
    seconds_since_midnight = (now - now.replace(hour=0,
                                                minute=0,
                                                second=0,
                                                microsecond=0)).total_seconds()

    for time_slot in cfg.TRAIN_DELAY_INDICATION_SCHEDULE:
        start_time = (int(time_slot[0].split(":")[0]) * 60 * 60) + \
                     (int(time_slot[0].split(":")[1]) * 60)
        stop_time = (int(time_slot[1].split(":")[0]) * 60 * 60) + \
                    (int(time_slot[1].split(":")[1]) * 60)
        if start_time <= seconds_since_midnight <= stop_time:
            return True
    return False


def load_debug_delays():
    """ Load debug delays from a yaml file
    """
    try:
        fdir = os.path.dirname(os.path.realpath(__file__))
        filename = os.path.join(fdir, 'test_delays.yaml')
        with open(filename, 'r') as file:
            return yaml.safe_load(file.read())

    except FileNotFoundError:
        return None


def check_for_delays(to_station, from_station, use_leds,
                     hive_indication, voice_strings):
    """ Check for delays and create voice strings for any delays
    """

    # Make sure the events used to stop threads are not set
    CHECK_THREAD_STOP.clear()

    # If led indication requested then start the led controller serial port
    if use_leds:
        led.start_serial_threads(cfg.LED_PORT, cfg.LED_BAUD)

    # If we are using a hive bulb as an indicator then create a data object
    # for the bulb.
    if hive_indication:
        colour_bulb = api.BulbObject(cfg.get_dev(cfg.INDICATOR_BULB))

    # Loop and sleep between runs
    while not CHECK_THREAD_STOP.isSet():
        # Turn off all the LEDs
        # if use_leds: led.show_pattern(LED_PORT,
        #                               LED_BAUD,
        #                               "NO_DELAYS",
        #                               led.colours.GREEN_DIM)

        # Get the delay data
        # Debug delays are in a file called debug_delays.yaml
        # If we rename/delete that file then we get the 'real'
        # delays using the api.  This means we can turn debugging
        # on/off by manipulating that file while this is running.
        delays = load_debug_delays()
        if not delays:
            delays = tt.get_delays(from_station,
                                   to_station,
                                   pretty_print=False)

        for delay in delays:
            LOGGER.debug(delay)

        # Turn on the LED warning pattern if we have a delay
        if delays and use_leds:
            led.show_pattern('CLOCK', led.Colours.RED)

        # Turn off the LED warning if we have no delays.
        if (not delays) and use_leds:
            led.show_pattern("NO_DELAYS", led.Colours.GREEN_DIM)

        # Hive Indication using an RGB bulb
        # Turn on alert if we ahve a delay
        # Calncel old alerts if no delays or if we exit schedule period
        if hive_indication:
            hive_bulb_checks(delays, colour_bulb)

        # Build voice strings for audio announcements and save them in a file
        # We'll play these if a user presses the zigbee button
        voice_strings.build_voice_string(delays, from_station, to_station)

        # Now sleep
        time.sleep(DELAY_CHECK_SLEEP_TIME)


def hive_bulb_checks(delays, colour_bulb):
    """ Turn a bulb on and red if there is a delay, set alert=True

        Cancel old alerts:
            Turn bulb white and off if no delays and alert is still active
            Turn bulb white and off if schedule=off and alert is still active

    """
    # Turn on the Hive bulb (to red) if we have a delay and the schedule
    # allows indications
    if delays and schedule_check() and (colour_bulb.alert_active is False):
        LOGGER.debug("Turn indicator bulb on.  Delays found & schedule is on")
        colour_bulb.set_red()
        colour_bulb.alert_active = True

    # Turn off the Hive bulb if no delays and we think we are
    # still showing an alert
    if (not delays) and colour_bulb.alert_active:
        colour_bulb.alert_active = False
        if colour_bulb.is_red():
            LOGGER.debug("Turn indicator bulb off.  No more delays")
            colour_bulb.set_white_off()

    # Turn off hive bulb if schedule is off and we think we are
    # still showing an alert
    if not schedule_check() and colour_bulb.alert_active:
        colour_bulb.alert_active = False
        if colour_bulb.is_red():
            LOGGER.debug("Schedule is off, "
                         "bulb is indicating delays so we turn it off")

            colour_bulb.set_white_off()


def button_press(cmd, colour_bulb, sitt_group, freezer_sensor, voice_strings):
    """ Take actions based on the button press type:

        Short press:  Toggle lights on/off

        Double press: Bulb=red, play delay announcements,
                      return bulb to original state

        Long press:   Play water level annoucement,
                      If bulb_green or bulb_blue then Bulb=white,
                      toggle freezer alarm enable/disable
                      Leave bulb white - part of disable

    """
    # short press: Toggle the sitting room group all on or all off
    if cmd['msgCode'] == "04":
        LOGGER.debug("Button Short Press: Toggling lights")
        sitt_group.toggle()

    # double press or long press
    elif cmd['msgCode'] in ["08", "10"]:

        # Play train notifications
        if cmd['msgCode'] == '08':
            LOGGER.debug("Button Double Press: Playing voice strings")
            voice_strings.play()
            # play_voice_strings([voice_strings])

        # Play hot water level and toggle the freezer alarm setting
        elif cmd['msgCode'] == '10':
            LOGGER.debug("Button Long Press: Playing msg")

            uwl = udp_cli.send_cmd(udp_cli.UWL_MESSAGE,
                                   udp_cli.UWL_RESP,
                                   udp_cli.ADDRESS)

            messages = ["KG traindicator 9000.",
                        "This is Robo Dad.  Go and have a shower!",
                        "Hot water is at {}.".format(uwl)]

            LOGGER.debug("BLUE = %s", colour_bulb.is_blue())
            LOGGER.debug("GREEN = %s", colour_bulb.is_green())
            if colour_bulb.is_green() or colour_bulb.is_blue():
                colour_bulb.set_white(colour_temp=2700, value=100)

                freezer_sensor.alarm_enabled = not freezer_sensor.alarm_enabled

            if colour_bulb.freezer_alarm_enabled:
                fr_msg = "Freezer Alarm: Enabled."
            else:
                fr_msg = 'Freezer Alarm: Off.'

            LOGGER.debug(fr_msg)
            msg = [messages[2], fr_msg]

            voice_strings.play(msg)


def doorbell_press(colour_bulb):
    """ Action on doorbell press:

        Play doorbell sound and breifly turn bulb on/red.
    """
    # For any bell press change indicator bulb red and play the bell sound
    cmd = 'aplay {} &'.format(cfg.BELL_SOUND)
    my_pipe = os.popen(cmd, 'w')
    my_pipe.close()

    # While the bell is ringing we change the bulb colour briefly
    # Only use bulb if hive_indication and we can get the current bulb state
    bulb_state = colour_bulb.get_state()
    colour_bulb.set_red()
    time.sleep(1)  # Indication duration
    colour_bulb.set_state(*bulb_state)


def button_press_handler(button_press_queue, hive_indication, voice_strings):
    """ Check for button press events on the queue and action as appropriate
        See code for details of actions

    """
    # If we are using a hive bulb as an indicator then create a data object
    # for the bulb.
    colour_bulb = None
    sitt_group = None
    freezer_sensor = None

    if hive_indication:
        colour_bulb = api.BulbObject(cfg.get_dev(cfg.INDICATOR_BULB))
        sitt_group = api.Group([cfg.get_dev(dev) for dev in cfg.SITT_GROUP])
        freezer_sensor = api.SensorObject(colour_bulb)

    # Main thread loop
    while True:
        if not button_press_queue.empty():
            cmd = button_press_queue.get()
            print(cmd)

            # Handle main button presses
            # shortPress  = play latest train delay annoucement audio clip
            # doublePress = play annoucement and briefly change bulb colour
            # longPress   = play 'robodad' annoucement
            if cmd['nodeId'] == cfg.BUTTON_NODE_ID:
                button_press(cmd, colour_bulb, sitt_group,
                             freezer_sensor, voice_strings)

            # Handle doorbell button press
            if cmd["nodeId"] == cfg.BELL_BUTTON_ID:
                LOGGER.debug("Doorbell button press.  Playing doorbell sound.")
                doorbell_press(colour_bulb)

            # Set the bulb blue if temp threshold is crossed.
            # Start a timer.  Reset the bulb if the timer expires
            if cmd["nodeId"] == cfg.FREEZER_TEMP_ID:
                LOGGER.debug("TEMPERATURE REPORT %s", cmd['temperature'])
                freezer_sensor.set_temperature(cmd['temperature'])

            time.sleep(0.1)  # Delay to allow last command to take effect

            # Flush the queue here to avoid lots of bell ringing
            flush_queue(button_press_queue)
            print()

        # Update the freezer_sensor object
        # If disabled and temp has dropped to normal then re-enable the alarm
        # If no reports for some time the show the offline warning.
        # If freezer warm the show temp warning.s
        freezer_sensor.update()

        # Sleep to avoid while loop spinning in this thread
        time.sleep(0.1)


class Voice():
    """ Class for creating and playing voice announcements """
    def __init__(self):
        self.strings = []

    def build_voice_string(self, delays, from_station, to_station):
        """ Build the voice strings
        """
        self.strings = []
        for delay in delays:
            to_station = get_station_name(delay['to'])
            from_station = get_station_name(delay['from'])

            try:
                etd = timestamp_from_time_string(delay['etd'])
                std = timestamp_from_time_string(delay['std'])
                delay_time = int((etd-std)/60)
            # ValueError can occur if there's no colon in the time HH:MM
            # AttributeError occurs if any vars are None
            except (ValueError, AttributeError):
                LOGGER.debug("Error parsing times in build_voice_string")
                delay_time = None

            voice_string = "The {} from {} to {}, is ".format(delay['std'],
                                                              from_station,
                                                              to_station)
            if delay['isCancelled']:

                if delay['cancelReason']:
                    voice_string += "cancelled. {}.".format(
                        delay['cancelReason'])
                else:
                    voice_string += "cancelled."
            else:
                voice_string += "delayed"
                if delay_time:
                    voice_string += " by {} minutes.".format(delay_time)

                if delay['delayReason']:
                    voice_string += ". {}.".format(delay['delayReason'])

            self.strings.append(voice_string)

        # Null voice string for no-delays situation
        if not delays:
            voice_string = "No delays listed for trains from {} to {}."
            self.strings.append(voice_string.format(
                get_station_name(from_station),
                get_station_name(to_station)))

    def play(self, msg=None):
        """ Play the given voice strings
        """

        voice_strings = msg if msg else self.strings
        voice_string = '. '.join(voice_strings)

        LOGGER.debug(voice_string)
        # Form the complete command
        temp_voice_file = '/tmp/voicefile.wav'
        cmd = 'pico2wave -l en-GB -w {tvf} "{vs}" && aplay {tvf} &'.format(
            tvf=temp_voice_file, vs=voice_string)

        my_pipe = os.popen(cmd, 'w')
        my_pipe.close()


def check_usb_dongles():
    """ Check we have the symlinks to the correct USB devices
        in /dev.  See config.py for instaructions on how to set
        these up using udevadm.

    """
    dongles = [cfg.HIVE_ZB_PORT, cfg.ZB_PORT]

    for dongle in dongles:
        if not os.path.exists(dongle):
            msg = ('Dongle port {} does not exist. See config.py '
                   'for instructions on how to configure'.format(dongle))
            LOGGER.error(msg)
            return False
    return True


def start_thread(thread_func, args, thread_name, thread_pool):
    """ Start the thread and return it
    """
    thread = threading.Thread(
        target=thread_func,
        args=args)
    thread.daemon = True
    thread.start()
    thread.name = thread_name
    LOGGER.debug("%s thread started.", thread_name)
    thread_pool.append(thread)


def main():
    """ Main program
    """

    # First check the ZigBee USB dongles are mapped to symlinks in /dev
    if not check_usb_dongles():
        sys.exit()

    to_station, from_station, leds, gpio, hive, zigbee = get_args()
    thread_pool = []

    voice_strings = Voice()

    # Start the Hive Zigbee thread
    if hive:
        at_threads = at.start_serial_threads(port=cfg.HIVE_ZB_PORT,
                                             baud=cfg.ZB_BAUD,
                                             print_status=False,
                                             rx_q=True)

        at_threads[0].name = 'Hive Zigbee - read thread'
        at_threads[1].name = 'Hive Zigbee - write thread'
        thread_pool = thread_pool + at_threads

    # Start ZigBee button press listener thread and button_press_handler queue
    # If button press then listener puts event on the ButtonPressQueue
    # button_press_handler takes events from the queue and processes them
    if zigbee:
        button_press_queue = queue.Queue()

        # Start the button press listener
        start_thread(bl.main,
                     (cfg.ZB_PORT, cfg.ZB_BAUD, button_press_queue),
                     'Button Listener',
                     thread_pool)

        # Start the button press handler
        start_thread(button_press_handler,
                     (button_press_queue, hive, voice_strings),
                     'Button Handler',
                     thread_pool)

    if gpio:
        start_thread(gm.main,
                     (voice_strings),
                     'GPIO Monitor',
                     thread_pool)

    # Start delay checker thread
    # Check for delays, build any voice strings and set led patterns
    start_thread(check_for_delays,
                 (to_station, from_station, leds, hive, voice_strings),
                 'Delay checker',
                 thread_pool)

    # Check the threads are all still running
    while True:
        for thd in thread_pool:
            if not thd.isAlive():
                LOGGER.debug("ERROR: THREAD HAS STOPPED: %s", thd.name)
                LOGGER.debug("Exiting program to allow clean restart")
                sys.exit()

        time.sleep(0.1)


if __name__ == "__main__":
    LOGGER = configure_logger("home-monitor", cfg.LOGFILE)
    main()
