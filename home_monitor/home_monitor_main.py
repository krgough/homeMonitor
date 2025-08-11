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

from argparse import ArgumentParser
import os
import sys
import time
import threading
import queue
import re
import logging.config

import zigbeetools.threaded_serial as at

# from home_monitor.udpcomms import hex_temp
from home_monitor.udpcomms import hot_water_udp_client as udp_cli, hex_temp
from home_monitor import train_times as tt
import home_monitor.led_pattern_generator as led
import home_monitor.button_listener as bl
import home_monitor.config as cfg
from home_monitor import hive_alarm
import home_monitor.zigbee_hive as zb_hive
import home_monitor.zigbee_home as zb_home
import home_monitor.gpio_monitor as gm
import home_monitor.freezer_alarm_fsm as freezer_alarm
from home_monitor.voice import Voice

CHECK_THREAD_STOP = threading.Event()
THREAD_POOL = []
DELAY_CHECK_SLEEP_TIME = 5 * 60

LOGGER = logging.getLogger(__name__)


def get_args():
    """Read command line parameters"""
    parser = ArgumentParser(description="Home Monitor - Train-d-cator")

    parser.add_argument(
        "-i", "--indication",
        choices=["led", "hive"],
        default="hive",
        help="Use HH360 LED board to indicate delays"
    )

    parser.add_argument(
        "-g", "--use_gpios",
        action="store_true",
        default=False,
        help="Monitor GPIO button presses"
    )

    parser.add_argument(
        "-r", "--freezer_alarm",
        action="store_true",
        default=False,
        help="Enable freezer alarm"
    )

    parser.add_argument(
        "-a", "--house_alarm",
        action="store_true",
        default=False,
        help="Set alarm state based on schedule"
    )

    parser.add_argument(
        "-t", "--to_station",
        required=True,
        type=str,
        help="CRS code for destination station"
    )
    parser.add_argument(
        "-f", "--from_station",
        required=True,
        type=str,
        help="CRS code for origin station"
    )

    args = parser.parse_args()

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


# def flush_queue(my_queue):
#     """Flush the given queue"""
#     while not my_queue.empty():
#         my_queue.get()


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

        # If we are using the LED board to indicate delays the hanlde that here
        if args["use_leds"]:
            led_delay_indication(delays)


        # Hive Indication using an RGB bulb
        # Turn on alert if we have a delay
        # Calncel old alerts if no delays or if we exit schedule period
        if args["use_hive"]:
            hive_bulb_indication(delays, colour_bulb)

        # Build voice strings for audio announcements and save in a file
        # We'll play these if a user presses the zigbee button
        voice_strings.build_voice_string(delays, args["from_station"], args["to_station"])

        # Check and set alarm state according to schedule
        if args["set_alarm"]:
            alarm.set_schedule_state()

        # Now sleep
        time.sleep(DELAY_CHECK_SLEEP_TIME)


def led_delay_indication(delays):
    """ Indicate delays using the HH360 LED board """
    # Turn on the LED warning pattern if we have a delay
    if delays:
        led.show_pattern("CLOCK", led.Colours.RED)
    else:
        # Turn off the LED warning if we have no delays.
        led.show_pattern("NO_DELAYS", led.Colours.GREEN_DIM)


def hive_bulb_indication(delays, colour_bulb):
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

            announce_dhw_level(voice_strings)
            announce_freezer_temp(freezer_sensor, voice_strings)

            # Disable freezer alarm by setting long press on the freezer sensor
            freezer_sensor.long_press_received = True



def announce_dhw_level(voice_strings):
    """Announce the current hot water level"""
    uwl = udp_cli.send_cmd(udp_cli.UWL_MESSAGE, udp_cli.UWL_RESP, udp_cli.ADDRESS)
    msg = f"Hot water is at {uwl}"
    voice_strings.play([msg])


def announce_freezer_temp(freezer_sensor, voice_strings):
    """Announce the current freezer temperature"""
    if freezer_sensor.temp is not None:
        msg = f"Freezer Temperature is {freezer_sensor.temp}"
        voice_strings.play([msg])
    else:
        LOGGER.warning("Freezer temperature not available")


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


def event_thread_handler(args, button_press_queue, hive_indication, voice_strings):
    """ Handles the period checks:
     
    - Check for and indicate train delays
    - Check freezer alarm state and update as appropriate
    - Check for house alarm state vs schedule and update as appropriate

     """
    
    events = {
        "TOGGLE_LIGHTS": {"event_name": "Toggle Lights", "func": sitt_group.toggle, "args": []},
        "PLAY_VOICE_STRINGS": {"event_name": "Play Voice Strings", "func": voice_strings.play, "args": []},
        "PLAY_HOT_WATER": {"event_name": "Play Hot Water Level", "func": udp_cli.send_cmd, "args": [udp_cli.UWL_MESSAGE, udp_cli.U
    }    ]


    # Check for delays

    # Update the House Alarm state

    # Check freezer alarm events

    # Check for button presses

    if args.indication == "hive":
        colour_bulb = zb_hive.BulbObject(cfg.get_dev(cfg.INDICATOR_BULB))
        sitt_group = zb_hive.Group([cfg.get_dev(dev) for dev in cfg.SITT_GROUP])
        freezer_sensor = zb_hive.SensorObject()
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
    """ Main program """

    # First check the ZigBee USB dongles are mapped to symlinks in /dev
    if not check_usb_dongles():
        print("ERROR: Zigbee dongle issue. Check logs for details")
        sys.exit()

    args = get_args()
    thread_pool = []

    voice_strings = Voice()


    # Start the Hive Zigbee threads
    if args["use_hive"]:
        zb_hive = at.ZigbeeDevice(name="Hive Zigbee", port=cfg.get_dev(cfg.HIVE_ZB_PORT))
        for thd in zb_hive.thread_pool:
            thread_pool.append(thd)

    # Start the Home Zigbee threads
    zb_home = at.ZigbeeDevice(name="Home Zigbee", port=cfg.get_dev(cfg.ZB_PORT))
    for thd in zb_home.thread_pool:
        thread_pool.append(thd)

    if args["use_gpios"]:
        start_thread(gm.main, (voice_strings), "GPIO Monitor", thread_pool)

    # Start delay checker thread
    start_thread(check_for_delays, (args, voice_strings), "Delay checker", thread_pool)

    # Start the freezer alarm thread
    if args["freezer_alarm"]:
        freezer_sensor = zb_home.SensorObject(cfg.FREEZER_TEMP_ID)
        freezer_alarm = freezer_alarm.SensorStateMachine(
            zb_hive.BulbObject(cfg.get_dev(cfg.INDICATOR_BULB)), freezer_sensor
        )
        start_thread(freezer_alarm.run, (), "Freezer Alarm", thread_pool)

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
