#!/usr/bin/env python3

"""
Created on 7 Nov 2018
25/11/2019 Keith Gough - PEP8 Updates.
12/08/2025 Keith Gough - MajorRefactor
    - Allow use of threaded serial for multiple zigbee dongles
    - Support use of the Zigbee Siren on Home Zigbee now that it deprecated from Hive
    - Improved the Zigbee device management and event handling

Home Automation Application
- Monitor train departures and indicate delays. Use button to announce delays.
- Use ZB Button to control Hive Bulbs/Plugs
- Monitor Freezer Temp and alert if it gets hot. Use button to announce temperature.
- Use Siren and WDS Sensors to implement a security system
- Monitor DHW cylinder temperature and use button to announce level.


"""

from argparse import ArgumentParser
import os
import sys
import time
import threading
import logging.config
from typing import List, Union

import gpiozero

import zigbeetools.threaded_serial as at

import home_monitor.config as cfg
from home_monitor.config import SystemEvents

import home_monitor.zigbee_hive as zb_hive
import home_monitor.zigbee_home as zb_home

from home_monitor.security_alarm_fsm import SecurityAlarmFSM
from home_monitor.delay_check_fsm import DelayCheckerFSM
from home_monitor.freezer_alarm_fsm import FreezerAlarmFSM

from home_monitor import hot_water_udp_client as udp_cli
from home_monitor import voice

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
        "-w", "--dhw",
        action="store_true",
        default=False,
        help="Enable hot water announcements"
    )

    parser.add_argument(
        "-r", "--freezer_alarm",
        action="store_true",
        default=False,
        help="Enable freezer alarm"
    )

    parser.add_argument(
        "-a", "--security_alarm",
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
        "level": "DEBUG",
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
    logging.getLogger("zeep").setLevel(logging.WARNING)
    logging.getLogger("gtts").setLevel(logging.WARNING)

    return logging.getLogger(logger_name)


def announce_dhw_level_action():
    """Announce the current hot water level"""
    uwl = udp_cli.send_cmd(udp_cli.UWL_MESSAGE, udp_cli.UWL_RESP, udp_cli.ADDRESS)
    msg = f"Hot water is at {uwl}"
    voice.play([msg])


def announce_freezer_temp_action(home_devs):
    """Announce the current freezer temperature"""
    freezer_sensor = home_devs["Freezer Sensor"]
    if freezer_sensor.temperature is not None:
        voice.play(f"Freezer Temperature is {freezer_sensor.temperature}°C")
    else:
        voice.play("Freezer Temperature is not available")


def doorbell_press_action(colour_bulb):
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


def button_event_action(event, args, sitt_group, home_devs, fsm_dict):
    """Take actions based on the button press type:

    Short press:  Toggle lights on/off

    Double press: Play delay announcements

    Long press:   Play freezer temp and water level annoucements
                  Set long_press on Freezer alarm (disable)
                  Set long_press on Security alarm (disable)
    """

    if event["event"] == SystemEvents.BUTTON.BTN_SHORT_PRESS:
        LOGGER.info("Button short press: Toggling lights")
        sitt_group.toggle()

    elif event["event"] == SystemEvents.BUTTON.BTN_DOUBLE_PRESS:
        LOGGER.info("Button double press: Announcing delays...")
        voice.play(voice.build_delay_voice_strings(args))

    elif event["event"] == SystemEvents.BUTTON.BTN_LONG_PRESS:
        LOGGER.info("Button long press: Making announcements and enabling/disabling alarms")

        # Make announcements...
        if args.dhw:
            announce_dhw_level_action()

        # Announce the freezer temp and Set the freezer alarm to disabled.
        # Will auto re-enable when temp is normal and sensor is online
        if args.freezer_alarm:
            announce_freezer_temp_action(home_devs)
            freezer_alarm_fsm = fsm_dict["FreezerAlarmFSM"]
            if freezer_alarm_fsm.state.disabled:
                voice.play(msgs="Enabling freezer alarm...")
                freezer_alarm_fsm.state.disabled = False
            elif freezer_alarm_fsm.state.temp_high:
                voice.play(msgs="Disabling freezer alarm...")
                freezer_alarm_fsm.state.enabled = True

        # Toggle the security alarm state
        if args.security_alarm:
            security_alarm_fsm = fsm_dict["SecurityAlarmFSM"]
            if security_alarm_fsm.state.deactivated:
                voice.play(msgs="Enabling security alarm...")
                security_alarm_fsm.state.deactivated = False
            else:
                voice.play(msgs="Disabling security alarm...")
                security_alarm_fsm.state.deactivated = True


def freezer_event_action(event, hive_devs: List[Union[zb_hive.BulbObject, zb_hive.Group]]):
    """ Take actions based on freezer events """
    hive_bulb = hive_devs["hive_bulb"]
    if event["event"] == cfg.SystemEvents.FREEZER.FREEZER_ALARM_TEMP_HIGH:
        hive_bulb.set_blue()
    elif event["event"] == cfg.SystemEvents.FREEZER.FREEZER_ALARM_TEMP_NORMAL:
        if hive_bulb.is_green() or hive_bulb.is_blue():
            hive_bulb.set_white_off()
    elif event["event"] == cfg.SystemEvents.FREEZER.FREEZER_ALARM_SENSOR_OFFLINE_DAY:
        hive_bulb.set_green()
    elif event["event"] == cfg.SystemEvents.FREEZER.FREEZER_ALARM_SENSOR_OFFLINE_NIGHT:
        hive_bulb.set_white_off()
    elif event["event"] == cfg.SystemEvents.FREEZER.FREEZER_ALARM_DISABLED:
        hive_bulb.set_white_off()


def security_event_action(event, home_devs, fsm_dict):
    """ Take action based on security alarm events """
    # TODO: Add sending emails.
    security_fsm = fsm_dict["SecurityAlarmFSM"]
    siren = home_devs["Siren"]
    if event["event"] == cfg.SystemEvents.SECURITY.ALARM_ARMED:
        pass

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_DISARMED:
        pass

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_TRIGGERED:
        siren.start_warning()

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_DEACTIVATED:
        siren.stop_warning()

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_ACTIVATED:
        pass

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_SENSOR_OPEN:
        security_fsm.state.trigger = True

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_SENSOR_CLOSED:
        pass

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_SENSOR_OFFLINE:
        pass


def device_event_action(event, args, fsm_dict):
    """ Take action based on device events """
    # TODO: Add sending emails

    freezer_fsm = fsm_dict["FreezerAlarmFSM"]
    security_fsm = fsm_dict["SecurityAlarmFSM"]
    alarm_snsrs = ["Garage RHS", "Garage LHS"]

    if event["event"] == cfg.SystemEvents.DEVICE.DEVICE_OFFLINE:
        if event["name"] == "Freezer Sensor":
            freezer_fsm.state.sensor_online = False
        elif args.device_name in alarm_snsrs:
            pass
            # TODO: Handle alarm sensor offline event

    elif event["event"] == cfg.SystemEvents.DEVICE.DEVICE_ONLINE:
        if event["name"] == "Freezer Sensor":
            freezer_fsm.state.sensor_online = True
        elif event["name"] in alarm_snsrs:
            pass

    elif event["event"] == cfg.SystemEvents.DEVICE.DEVICE_TEMP_HIGH:
        if event["name"] == "Freezer Sensor":
            freezer_fsm.state.temp_high = True
        elif event["name"] in alarm_snsrs:
            pass

    elif event["event"] == cfg.SystemEvents.DEVICE.DEVICE_TEMP_NORMAL:
        if event["name"] == "Freezer Sensor":
            freezer_fsm.state.temp_high = False
        elif event["name"] in alarm_snsrs:
            pass

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_SENSOR_OPEN:
        security_fsm.state.trigger = True

    elif event["event"] == cfg.SystemEvents.SECURITY.ALARM_SENSOR_CLOSED:
        security_fsm.state.trigger = False


def train_event_action(event, hive_devs):
    """ Take action based on train events """
    hive_bulb = hive_devs["hive_bulb"]
    if event["event"] == cfg.SystemEvents.TRAIN.DELAYS:
        hive_bulb.alert = True
        hive_bulb.set_red()
    elif event["event"] == cfg.SystemEvents.TRAIN.NO_DELAYS:
        if hive_bulb.alert is True:
            hive_bulb.alert = False
            hive_bulb.set_white_off()


def system_event_handler(args, system_event_q, home_devs, hive_devs, fsm_dict):
    """ Take actions based on system events occurring """
    while True:
        while not system_event_q.empty():
            # Process system events
            event = system_event_q.get()

            if event["event"] in cfg.ButtonEvents:
                button_event_action(
                    event=event,
                    args=args,
                    sitt_group=hive_devs["hive_sitt_group"],
                    home_devs=home_devs,
                    fsm_dict=fsm_dict
                )

            elif event["event"] in cfg.SystemEvents.FREEZER:
                if args.freezer_alarm:
                    freezer_event_action(event, hive_devs)

            elif event["event"] in cfg.SystemEvents.SECURITY:
                if args.security_alarm:
                    security_event_action(event, home_devs, fsm_dict)

            # Online/Offline events - for Security and Freezer Sensors
            elif event["event"] in cfg.SystemEvents.DEVICE:
                device_event_action(event, args, fsm_dict)

            elif event["event"] in cfg.SystemEvents.TRAIN:
                train_event_action(event, hive_devs)

            else:
                LOGGER.error("Unhandled system event: %s", event)

        time.sleep(0.1)


def check_usb_dongles():
    """Check we have symlinks to correct USB devices in /dev.
    See config.py for instaructions on how to set these up using udevadm.
    """
    dongles = [cfg.HIVE_ZB_PORT, cfg.HOME_ZB_PORT]

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
    thread = threading.Thread(target=thread_func, args=args, name=thread_name, daemon=True)
    thread.start()
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
    system_event_q = cfg.SystemEventQueue()

    # Start the Hive Zigbee threads
    hive = at.ZigbeeCmdNode(name="Hive Zigbee", port=cfg.HIVE_ZB_PORT)
    hive_bulb = zb_hive.BulbObject(coordinator=hive, dev=cfg.get_hive_dev("Sitt Colour"))
    hive_sitt_group = zb_hive.Group(name="Hive Sitt Group", coordinator=hive, device_name_list=cfg.HIVE_SITT_GROUP)
    hive_devs = {"hive_bulb": hive_bulb, "hive_sitt_group": hive_sitt_group}

    # Start the Home Zigbee threads
    home = zb_home.ZigbeeHome(name="zb_home", event_q=system_event_q)

    # Start the FSMs
    freezer_alarm_fsm = FreezerAlarmFSM(name="FreezerAlarmFSM", event_q=system_event_q)
    security_alarm_fsm = SecurityAlarmFSM(name="SecurityAlarmFSM", event_q=system_event_q)

    delay_checker_fsm = DelayCheckerFSM(
        name="DelayCheckerFSM",
        event_q=system_event_q,
        from_station=args.from_station,
        to_station=args.to_station
    )

    # Get a list of all threads so we can monitor them
    fsm_dict = {
        "FreezerAlarmFSM": freezer_alarm_fsm,
        "SecurityAlarmFSM": security_alarm_fsm,
        "DelayCheckerFSM": delay_checker_fsm
    }
    for device in list(fsm_dict.values()) + [hive, home]:
        for thread in device.thread_pool:
            thread_pool.append(thread)

    # # Start the event checker thread
    start_thread(
        system_event_handler,
        (args, system_event_q, home.device_list, hive_devs, fsm_dict),
        "System Event Handler",
        thread_pool
    )

    if args.use_gpios:
        btn = gpiozero.Button(4)
        btn.when_pressed = lambda: system_event_q.put(cfg.SystemEvents.GPIO.BUTTON_PRESSED, "GPIO_BUTTON")

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

    logging.getLogger("home_monitor.zigbee_home").setLevel(logging.INFO)
    logging.getLogger("zigbeetools").setLevel(logging.INFO)
    logging.getLogger("home_monitor.train_times").setLevel(logging.INFO)
    main()
