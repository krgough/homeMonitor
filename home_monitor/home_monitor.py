#!/usr/bin/env python3

"""
Created on 7 Nov 2018

@author: Keith.Gough

Application to Monitor train departures and indicate delays

Indication is by setting a pattern on an attached HH360 LED board or,
by setting a Hive colour bulb to e.g. RED and ON.

User can then use an associated ZigBee button to trigger a voice announcement
for the delayed train services.

25/11/2019 Keith Gough - PEP8 Updates.

"""

import os
import sys
import getopt
import time
import threading
import queue
import re
from textwrap import dedent
import logging.config

from home_monitor.udpcomms import hex_temp
from home_monitor.udpcomms import hot_water_udp_client as udp_cli
import zigbeetools.threaded_serial as at

from home_monitor import train_times as tt
import home_monitor.led_pattern_generator as led
import home_monitor.button_listener as bl
import home_monitor.config as cfg
from home_monitor import hive_alarm

import home_monitor.zigbee_methods as api  # Control using Zigbee AT commands
import home_monitor.gpio_monitor as gm
import home_monitor.freezer_alarm_fsm as fsm
from home_monitor.voice import Voice

CHECK_THREAD_STOP = threading.Event()
THREAD_POOL = []
DELAY_CHECK_SLEEP_TIME = 5 * 60

LOGGER = logging.getLogger(__name__)


def get_args():
    """Read command line parameters"""
    # NOTE to self - Cannot use f strings in python ver < 3.6
    help_string = dedent(
        f"""
    USAGE: {os.path.basename(__file__)} [-halbgz] -t to_station -f from_station

    Use these command line options:

    -h                      Print this help

    -a                      Arm/Disarm alarm based on schedule (in config)

    -l                      Show delays on HH360 LED indicator board

    -b                      Show delays on hive colour bulb
                            See apiConfig.py for login details

    -g                      Monitor gpio button presses
                            Make announcement if button presssed)

    -z                      Announce delays on zigbee button press

    -t 'to' stationId       CRS code for station e.g. wat for Waterloo
    -f 'from' stationId     CRS code for station
    """
    )

    args = {
        "to_station": None,
        "from_station": None,
        "use_leds": False,
        "use_hive": False,
        "use_gpios": False,
        "zigbee_button": False,
        "set_alarm": False,
    }

    opts = getopt.getopt(sys.argv[1:], "halgbzt:f:")[0]

    for opt, arg in opts:
        # print(opt, arg)
        if opt == "-h":
            print(help_string)
            sys.exit()
        if opt == "-a":
            args["set_alarm"] = True
        if opt == "-t":
            args["to_station"] = arg
        if opt == "-f":
            args["from_station"] = arg
        if opt == "-l":
            args["use_leds"] = True
        if opt == "-b":
            args["use_hive"] = True
        if opt == "-z":
            args["zigbee_button"] = True
        if opt == "-g":
            args["use_gpios"] = True

    if not args["to_station"]:
        print("Error: toStation was not specified")
        print(help_string)
        sys.exit()

    if not args["from_station"]:
        print("Error: fromStation was not specified")
        print(help_string)
        sys.exit()

    return args


def configure_logger(logger_name, log_path=None):
    """Logger configuration function

    If log_path given then log to the file else to console only.
    """
    version = 1
    disable_existing_loggers = False
    formatters = {
        "default": {
            "format": "%(asctime)s,%(levelname)s,%(name)s,%(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    }

    console_handler = {
        "level": "DEBUG",
        "class": "logging.StreamHandler",
        "formatter": "default",
        "stream": "ext://sys.stdout",
    }

    file_handler = {
        "level": "INFO",
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "default",
        "filename": log_path,
        "maxBytes": 100000,
        "backupCount": 3,
    }

    if log_path:
        logging.config.dictConfig(
            {
                "version": version,
                "disable_existing_loggers": disable_existing_loggers,
                "formatters": formatters,
                "handlers": {"file": file_handler},
                "loggers": {
                    "": {"level": "DEBUG", "handlers": ["file"]}
                },
            }
        )
    else:
        logging.config.dictConfig(
            {
                "version": version,
                "disable_existing_loggers": disable_existing_loggers,
                "formatters": formatters,
                "handlers": {"console": console_handler},
                "loggers": {"": {"level": "DEBUG", "handlers": ["console"]}},
            }
        )

    # logging.getLogger("zigbeetools.threaded_serial").setLevel(file_handler["level"])
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    return logging.getLogger(logger_name)


def flush_queue(my_queue):
    """Flush the given queue"""
    while not my_queue.empty():
        my_queue.get()


def check_for_delays(args, voice_strings):
    """Check for delays and create voice strings for any delays"""

    # Make sure the events used to stop threads are not set
    CHECK_THREAD_STOP.clear()

    # If led indication requested then start the led controller serial port
    if args["use_leds"]:
        led.start_serial_threads(cfg.LED_PORT, cfg.LED_BAUD)

    # If we are using a hive bulb as an indicator then create a data object
    # for the bulb.
    if args["use_hive"]:
        colour_bulb = api.BulbObject(cfg.get_dev(cfg.INDICATOR_BULB))

    # Get a hive account object for controlling the alarm
    if args["set_alarm"]:
        alarm = hive_alarm.HiveAlarm()

    # Loop and sleep between runs
    while not CHECK_THREAD_STOP.is_set():
        # Turn off all the LEDs
        # if use_leds: led.show_pattern(LED_PORT,
        #                               LED_BAUD,
        #                               "NO_DELAYS",
        #                               led.colours.GREEN_DIM)

        # Get the delay data
        delays = tt.get_delays(args["from_station"], args["to_station"])

        for delay in delays:
            LOGGER.debug(delay)

        # Turn on the LED warning pattern if we have a delay
        if delays and args["use_leds"]:
            led.show_pattern("CLOCK", led.Colours.RED)

        # Turn off the LED warning if we have no delays.
        if (not delays) and args["use_leds"]:
            led.show_pattern("NO_DELAYS", led.Colours.GREEN_DIM)

        # Hive Indication using an RGB bulb
        # Turn on alert if we have a delay
        # Calncel old alerts if no delays or if we exit schedule period
        if args["use_hive"]:
            hive_bulb_checks(delays, colour_bulb)

        # Build voice strings for audio announcements and save in a file
        # We'll play these if a user presses the zigbee button
        voice_strings.build_voice_string(delays, args["from_station"], args["to_station"])

        # Check and set alarm state according to schedule
        if args["set_alarm"]:
            alarm.set_schedule_state()

        # Now sleep
        time.sleep(DELAY_CHECK_SLEEP_TIME)


def hive_bulb_checks(delays, colour_bulb):
    """Turn a bulb on and red if there is a delay, set alert=True

    Cancel old alerts:
        Turn bulb white and off if no delays and alert is still active
        Turn bulb white and off if schedule=off and alert is still active
    """
    # Turn on the Hive bulb (to red) if we have a delay and the schedule
    # allows indications
    sched = cfg.TRAIN_DELAY_INDICATION_SCHEDULE
    if delays and cfg.schedule_check(sched) and (not colour_bulb.alert_active):
        LOGGER.info("Turn indicator bulb on.  Delays found & schedule is on")
        colour_bulb.set_red()
        colour_bulb.alert_active = True

    # Turn off the Hive bulb if no delays and we think we are
    # still showing an alert
    if (not delays) and colour_bulb.alert_active:
        LOGGER.info("No more delays.  Alert active.  Attempting to cancel alert..")
        if colour_bulb.is_red():
            LOGGER.info("Bulb is red so set it to white")
            colour_bulb.set_white_off()
            if not colour_bulb.is_red():
                LOGGER.info("Bulb is not red.  Alert cancelled")
                colour_bulb.alert_active = False
            else:
                LOGGER.error("Bulb set to white failed.  Alert still active.")
        else:
            LOGGER.info("Bulb is not red.  Alert cancelled")
            colour_bulb.alert_active = False

    # Turn off hive bulb if schedule is off and we think we are
    # still showing an alert
    if not cfg.schedule_check(sched) and colour_bulb.alert_active:
        LOGGER.info("Schedule OFF, Alert Active.  Attempting to cancel alert...")
        if colour_bulb.is_red():
            LOGGER.info("Bulb is red so set it to white and off")
            colour_bulb.set_white_off()
            if not colour_bulb.is_red():
                LOGGER.info("Bulb is not red.  Alert canceled.")
                colour_bulb.alert_active = False
            else:
                LOGGER.error("Bulb set to white failed.  Alert still active.")
        else:
            LOGGER.info("Bulb is not red.  Alert canceled.")
            colour_bulb.alert_active = False


def button_press(cmd, sitt_group, freezer_sensor, voice_strings):
    """Take actions based on the button press type:

    Short press:  Toggle lights on/off

    Double press: Bulb=red, play delay announcements,
                    return bulb to original state

    Long press:   Play water level annoucement,
                    If bulb_green or bulb_blue then Bulb=white,
                    toggle freezer alarm enable/disable
                    Leave bulb white - part of disable
    """
    # short press: Toggle the sitting room group all on or all off
    if cmd["msgCode"] == "04":
        LOGGER.info("Button Short Press: Toggling lights")
        sitt_group.toggle()

    # double press or long press
    elif cmd["msgCode"] in ["08", "10"]:

        # Play train notifications
        if cmd["msgCode"] == "08":
            LOGGER.info("Button Double Press: Playing voice strings")
            voice_strings.play()
            # play_voice_strings([voice_strings])

        # Play hot water level and toggle the freezer alarm setting
        elif cmd["msgCode"] == "10":
            LOGGER.info("Button Long Press: Playing msg")

            uwl = udp_cli.send_cmd(udp_cli.UWL_MESSAGE, udp_cli.UWL_RESP, udp_cli.ADDRESS)
            hw_msg = f"Hot water is at {uwl}"

            freezer_sensor.long_press_received = True
            fr_msg = f" Freezer Temperature is {freezer_sensor.temp}"
            msg = [hw_msg, fr_msg]
            voice_strings.play(msg)


def doorbell_press(colour_bulb):
    """Action on doorbell press:
    Play doorbell sound and briefly turn bulb on/red.
    """
    # For any bell press change indicator bulb red and play the bell sound
    cmd = f"aplay {cfg.BELL_SOUND} &"
    my_pipe = os.popen(cmd, "w")
    my_pipe.close()

    # While the bell is ringing we change the bulb colour briefly
    # Only use bulb if hive_indication and we can get the current bulb state
    bulb_state = colour_bulb.get_state()
    colour_bulb.set_red()
    time.sleep(1)  # Indication duration
    colour_bulb.set_state(*bulb_state)


def button_press_handler(button_press_queue, hive_indication, voice_strings):
    """Check for button press events on the queue and action as appropriate
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
        freezer_sensor = api.SensorObject()
        freezer_alarm = fsm.SensorStateMachine(colour_bulb, freezer_sensor)

    # Main thread loop
    while True:
        if not button_press_queue.empty():
            cmd = button_press_queue.get()

            # Handle main button presses
            # shortPress  = play latest train delay annoucement audio clip
            # doublePress = play annoucement and briefly change bulb colour
            # longPress   = play 'robodad' annoucement
            if cmd["nodeId"] == cfg.BUTTON_NODE_ID:
                button_press(cmd, sitt_group, freezer_sensor, voice_strings)

            # Handle doorbell button press
            if cmd["nodeId"] == cfg.BELL_BUTTON_ID:
                LOGGER.info("Doorbell button press.  Playing doorbell sound.")
                doorbell_press(colour_bulb)

            # # Save the temperature and update the state_machine
            # if cmd["nodeId"] == cfg.FREEZER_TEMP_ID:
            #     LOGGER.debug("TEMPERATURE REPORT %s", cmd['temperature'])
            #     freezer_sensor.temp = cmd['temperature']
            #     freezer_alarm.on_event()

            time.sleep(0.1)  # Delay to allow last command to take effect

            # Flush the queue here to avoid lots of bell ringing
            flush_queue(button_press_queue)

        # If we have a temperature report then update the object
        # If we have a check-in from the sensor and we have not had a recent
        # temperature report then attempt to reset the report config
        while not at.LISTNER_QUEUE.empty():
            msg = at.LISTNER_QUEUE.get()

            # Temperaure report
            # REPORTATTR:2F28,06,0402,0000,29,08E3
            regex = "REPORTATTR:[0-9a-fA-F]{4},06,0402,0000,29"
            if re.match(regex, msg):
                node_id = msg.split(":")[1][:4]
                temperature = msg.split(",")[-1]
                temperature = hex_temp.convert_s16(temperature) / 100
                freezer_sensor.update_temperature(temperature)

                LOGGER.info("TEMPERATURE, %s, %s", node_id, freezer_sensor.temp)

            # CHECKIN:2F28,06,00
            regex = "CHECKIN:[0-9a-fA-F]{4},06"
            if re.match(regex, msg):
                freezer_sensor.set_temp_rpt_cfg(msg)

        # Update the freezer_sensor object
        # If disabled and temp has dropped to normal then re-enable the alarm
        # If no reports for some time the show the offline warning.
        # If freezer warm the show temperature warning.
        freezer_alarm.on_event()

        # Sleep to avoid while loop spinning in this thread
        time.sleep(0.1)


def check_usb_dongles():
    """Check we have symlinks to correct USB devices in /dev.
    See config.py for instaructions on how to set these up using udevadm.
    """
    dongles = [cfg.HIVE_ZB_PORT, cfg.ZB_PORT]

    for dongle in dongles:
        if not os.path.exists(dongle):
            msg = (
                f"Dongle port {dongle} does not exist. See config.py "
                "for instructions on how to configure"
            )
            LOGGER.error(msg)
            return False
    return True


def start_thread(thread_func, args, thread_name, thread_pool):
    """Start the thread and return it"""
    thread = threading.Thread(target=thread_func, args=args)
    thread.daemon = True
    thread.start()
    thread.name = thread_name
    LOGGER.info("%s thread started.", thread_name)
    thread_pool.append(thread)


def main():
    """Main program"""

    # First check the ZigBee USB dongles are mapped to symlinks in /dev
    if not check_usb_dongles():
        print("ERROR: Zigbee dongle issue. Check logs for details")
        sys.exit()

    args = get_args()
    thread_pool = []

    voice_strings = Voice()

    # Start the Hive Zigbee thread
    if args["use_hive"]:
        at_threads = at.start_serial_threads(
            port=cfg.HIVE_ZB_PORT,
            baud=cfg.ZB_BAUD,
            print_status=False,
            rx_q=True,
            listener_q=True,
        )

        at_threads[0].name = "Hive Zigbee - read thread"
        at_threads[1].name = "Hive Zigbee - write thread"
        thread_pool = thread_pool + at_threads

    # Start ZigBee button press listener thread and button_press_handler queue
    # If button press then listener puts event on the ButtonPressQueue
    # button_press_handler takes events from the queue and processes them
    if args["zigbee_button"]:
        button_press_queue = queue.Queue()

        # Start the button press listener
        start_thread(
            bl.main,
            (cfg.ZB_PORT, cfg.ZB_BAUD, button_press_queue),
            "Button Listener",
            thread_pool,
        )

        # Start the button press handler
        start_thread(
            button_press_handler,
            (button_press_queue, args["use_hive"], voice_strings),
            "Button Handler",
            thread_pool,
        )

    if args["use_gpios"]:
        start_thread(gm.main, (voice_strings), "GPIO Monitor", thread_pool)

    # Start delay checker thread
    # Check for delays, build any voice strings and set led patterns
    start_thread(
        check_for_delays,
        (args, voice_strings),
        "Delay checker",
        thread_pool,
    )

    # Check the threads are all still running
    while True:
        for thd in thread_pool:
            if not thd.is_alive():
                LOGGER.error("ERROR: THREAD HAS STOPPED: %s", thd.name)
                LOGGER.error("Exiting program to allow clean restart")
                sys.exit()

        time.sleep(0.1)


if __name__ == "__main__":
    LOGGER = configure_logger("home-monitor", cfg.LOGFILE)
    main()
