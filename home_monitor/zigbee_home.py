"""

Manage the devices on the Home Zigbee network (alternative to Hive Zigbee) and handle events.

- Provide Device class objects which represent the various Zigbee devices in the network.
- Match node id to eui for each device and keep track if node id changes
- Handling for incomming attribute reports, checkins, and other events.

"""
from enum import Enum
import logging
import queue
import time
import threading

import zigbeetools.threaded_serial as at
import zigbeetools.zigbee_clusters as zcl
import home_monitor.config as cfg
from home_monitor.config import SystemEvents

LOGGER = logging.getLogger(__name__)


OFFLINE_TIMEOUT = 60 * 21  # 21 minutes = to allow for 2 reports + 1min


class OpenClosedState(Enum):
    """ WDS Open/Closed States """
    CLOSED = 0
    OPEN = 1


class LastClickType(Enum):
    """ Button press types """
    SHORT_PRESS = "04"
    DOUBLE_PRESS = "08"
    LONG_PRESS = "10"


MATCH_PATTERNS = [
    {"name": "REPORTATTR",  "fields": ['node_id', 'ep', 'clust_id', 'attr_id', 'type', 'value']},
    {"name": "REPORTMATTR", "fields": ['node_id', 'ep', 'manuf_id', 'clust_id', 'attr_id', 'type', 'value']},
    {"name": "CHECKIN",     "fields": ['node_id', 'ep']},
    {"name": "ZONESTATUS",  "fields": ['node_id', 'ep', 'zone_status', 'extended_status', 'zone_id', 'delay']},
    {"name": "SED",         "fields": ['eui', 'node_id']},
]

# REPORTATTR:3E16,06,0402,0000,29,0ABE
# REPORTMATTR:7967,01,1039,0006,FD03,18,04
# CHECKIN:3E16,06
# ZONESTATUS:58FD,06,0061,00,06,0000
# SED:00124B00160561DE,3E16

MAX_SEND_ATTEMPTS = 3
SEND_RETRY_TIMEOUT = 5  # seconds


def hex_to_signed_int8(hex_value):
    """Convert hex string to signed int8 using two's complement"""
    val = int(hex_value, 16)
    if val >= 128:  # If bit 7 is set (negative number)
        val -= 256  # Convert from unsigned to signed
    return val


def parse_message(msg, pattern):
    """ Parse the message into a dict based on the given pattern """
    msg_fields = msg.replace(f"{pattern['name']}:", "").split(",")
    msg_dict = dict(zip(pattern["fields"], msg_fields))
    return msg_dict


def find_device_by_node_id(node_id, devices):
    """Find a device in the devices dictionary by node_id"""
    for device in devices:
        if device.node_id == node_id:
            return device
    return None


def find_device_by_eui(eui, devices):
    """Find a device in the devices dictionary by eui."""
    for device in devices:
        if device.eui == eui:
            return device
    return None


def zb_update_worker(coordinator: at.ZigbeeDevice, device_list: list):
    """Handle incoming Zigbee messages and update the device """
    while True:

        # Process incomming messages from the devices
        while not coordinator.listener_q.empty():
            msg = coordinator.listener_q.get()
            LOGGER.debug("Received message: %s", msg)

            for pattern in MATCH_PATTERNS:
                if msg.startswith(pattern["name"]):
                    data = parse_message(msg, pattern)
                    data["msg_type"] = pattern["name"]
                    LOGGER.debug("Matched pattern: %s, node_id: %s", pattern["name"], data["node_id"])
                    handle_attribute_update(coordinator, data, device_list)
                    break

        # Check if any devices have gone offline
        for device in device_list:
            device.online_offline_event()

        time.sleep(0.1)


def handle_attribute_update(coordinator: at.ZigbeeDevice, msg_data: dict, device_list: list):
    """ Get the device by node_id
    If node_id not found then try to get the eui and lookup the device by eui and update the node_id
    Then update the device with the attribute report
    """
    dev = find_device_by_node_id(msg_data['node_id'], device_list)
    if not dev:
        LOGGER.info("Device with node_id %s not found, trying to find by eui", msg_data['node_id'])
        resp_state, _, resp_value = coordinator.at_cmds.get_eui(msg_data['node_id'], msg_data['node_id'])
        # AddrResp:00,8115,00124B001605777F
        if resp_state:
            dev = find_device_by_eui(resp_value, device_list)
            if dev:
                dev.node_id = msg_data['node_id']  # Update the node_id if found by eui
            else:
                LOGGER.error("Device with eui %s not found in device list", resp_value)
        else:
            LOGGER.error("Failed to get eui for node_id %s", msg_data['node_id'])

    if dev:
        if msg_data['msg_type'] in ["REPORTATTR", "REPORTMATTR"]:
            LOGGER.debug("Updating device %s with attribute report: %s", dev.name, msg_data)

            cluster = zcl.get_cluster_name_and_id(msg_data["clust_id"])[1]

            if msg_data['msg_type'] == "REPORTMATTR":
                msg_data["attr_id"] = msg_data["attr_id"] + "_msp"
            attribute = zcl.get_attribute_name_and_id(msg_data["clust_id"], msg_data["attr_id"])[1]

            dev.attribute_report_event(cluster, attribute, msg_data['value'])

        elif msg_data['msg_type'] == "ZONESTATUS":
            LOGGER.debug("Updating device %s zone_status: %s", dev.name, msg_data)
            dev.zone_status_event(msg_data["zone_status"])


# pylint: disable=too-few-public-methods,too-many-instance-attributes
# pylint: disable=too-many-arguments,too-many-positional-arguments
class ZigbeeDevice:
    """Base class for Zigbee devices"""

    def __init__(self, eui, name, event_q):
        self.name = name
        self.eui = eui
        self.node_id = None  # Node ID will be set when the device is paired
        self.event_q = event_q
        self.online = False  # Default state, can be overridden by subclasses

    def attribute_report_event(self, cluster, attribute, value):
        """Handle attribute report events"""

    def zone_status_event(self, zone_status):
        """Handle zone status events"""


class WindowDoorSensor(ZigbeeDevice):
    """Class for handling Window/Door Sensors"""

    def __init__(self, eui, name, event_q, freezer=False, alarm=False):
        super().__init__(eui, name, event_q)
        self.state = OpenClosedState.CLOSED  # Default state
        self.battery_voltage = 0
        self.temperature = 0
        self.freezer_sensor = freezer
        self.alarm_sensor = alarm

        self.last_checkin = 0
        self.last_battery_report = 0
        self.last_temperature_report = 0

    def online_offline_event(self):
        """Set the online state of the device"""

        # Transition to offline
        if self.online:
            if self.last_temperature_report < (time.time() - OFFLINE_TIMEOUT):
                self.online = False
                LOGGER.warning("%s: offline", self.name)
                if self.freezer_sensor:
                    self.event_q.put("FREEZER_SENSOR_OFFLINE")

        # Transition to online
        else:
            if self.last_temperature_report >= (time.time() - OFFLINE_TIMEOUT):
                self.online = True
                LOGGER.info("%s: online", self.name)
                if self.freezer_sensor:
                    self.event_q.put("FREEZER_SENSOR_ONLINE")

    def attribute_report_event(self, cluster, attribute, value):
        """Set the battery voltage of the device"""

        if cluster == "Power Configuration Cluster" and attribute == "batteryVoltage":
            self.battery_voltage = int(value, 16) / 10
            self.last_battery_report = time.time()
            LOGGER.info("%s: Battery voltage %s", self.name, self.battery_voltage)

        elif cluster == "Temperature Measurement Cluster" and attribute == "measuredValue":
            new_temperature = int(value, 16) / 100.0
            LOGGER.info("%s: Temperature %.2f°C", self.name, new_temperature)

            self.last_temperature_report = time.time()
            self.online_offline_event()

            self.temperature_event(new_temperature)
            self.temperature = new_temperature

        else:
            LOGGER.error("Unhandled attribute update for %s: %s, %s = %s", self.name, cluster, attribute, value)

    def zone_status_event(self, zone_status):
        """Handle zone status events"""
        # Bitmask AND zone status to deterine if zone is open/closed
        new_state = OpenClosedState(int(zone_status) & 0x01)

        if self.state == OpenClosedState.CLOSED and new_state == OpenClosedState.OPEN:
            LOGGER.info("%s: open", self.name)
            if self.alarm_sensor:
                self.event_q.put(SystemEvents.ALARM_SENSOR_OPEN)
            self.state = new_state

        elif self.state == OpenClosedState.OPEN and new_state == OpenClosedState.CLOSED:
            LOGGER.info("%s: closed", self.name)
            if self.alarm_sensor:
                self.event_q.put(SystemEvents.ALARM_SENSOR_CLOSED)
            self.state = new_state

    def temperature_event(self, new_temperature):

        """ Handle sending freezer temperature events """
        if self.freezer_sensor:
            # Transition to Temp Normal to Temp High
            if self.temperature < cfg.FREEZER_TEMP_THOLD and new_temperature > cfg.FREEZER_TEMP_THOLD:
                LOGGER.warning("%s: Freezer temperature is above threshold: %.2f °C", self.name, new_temperature)
                self.event_q.put(SystemEvents.FREEZER_ALARM_TEMP_HIGH)

            # Transition from High Temp to Temp Normal
            if self.temperature > cfg.FREEZER_TEMP_THOLD and new_temperature < cfg.FREEZER_TEMP_THOLD:
                LOGGER.warning("%s: Freezer temperature is below threshold: %.2f °C", self.name, self.temperature)
                self.event_q.put(SystemEvents.FREEZER_ALARM_TEMP_NORMAL)


class Siren(ZigbeeDevice):
    """ Class for handling Siren devices """

    def __init__(self, eui, name, event_q):
        super().__init__(eui, name, event_q=event_q)
        self.warning_state = False  # Whether or not the siren is going off
        self.battery_voltage = None
        self.battery_temperature = None
        self.battery_percentage_remaining = None

        self.last_battery_report = 0
        self.last_battery_temperature_report = 0
        self.last_battery_percentage_remaining_report = 0

    def attribute_report_event(self, cluster, attribute, value):
        """ Update the attribute """
        if cluster == "Power Configuration Cluster" and attribute == "batteryVoltage":
            self.battery_voltage = int(value, 16) / 10
            self.last_battery_report = time.time()
            LOGGER.info("%s: Battery level %s", self.name, self.battery_voltage)

        elif cluster == "Basic Cluster" and attribute == "batteryTemperature":
            self.battery_temperature = hex_to_signed_int8(value)
            self.last_battery_temperature_report = time.time()
            LOGGER.info("%s: Battery temperature %s°C", self.name, self.battery_temperature)

        elif cluster == "Power Configuration Cluster" and attribute == "batteryPercentageRemaining":
            self.battery_percentage_remaining = round(int(value, 16) / 2)
            self.last_battery_percentage_remaining_report = time.time()
            LOGGER.info("%s: Battery percentage remaining %s%%", self.name, self.battery_percentage_remaining)

        else:
            LOGGER.error("Unhandled attribute update for %s: %s, %s = %s", self.name, cluster, attribute, value)

    def online_offline_event(self):
        """ Set the online state of the device """
        # Transition to offline
        if self.online:
            if self.last_battery_report < (time.time() - OFFLINE_TIMEOUT):
                self.online = False
                LOGGER.warning("%s: offline", self.name)

        # Transition to online
        else:
            if self.last_battery_report >= (time.time() - OFFLINE_TIMEOUT):
                self.online = True
                LOGGER.info("%s: online", self.name)

    def start_warning(self):
        """ Start the siren warning """
        LOGGER.warning("%s: siren activated", self.name)

    def stop_warning(self):
        """ Stop the siren warning """
        LOGGER.warning("%s: siren deactivated", self.name)


class Button(ZigbeeDevice):
    """ Class for handling Button devices """

    def __init__(self, eui, name, event_q):
        super().__init__(eui, name, event_q=event_q)
        self.last_click_type = None
        self.battery_voltage = None

        self.last_battery_report = 0

    def attribute_report_event(self, cluster, attribute, value):
        """ Update the attribute
        SHORT_PRESS  - REPORTMATTR:7967,01,1039,0006,FD03,18,04
        DOUBLE_PRESS - REPORTMATTR:7967,01,1039,0006,FD03,18,08
        LONG_PRESS   - REPORTMATTR:7967,01,1039,0006,FD03,18,10
        """
        if cluster == "On/Off Cluster" and attribute == "lastClickType":
            self.last_click_type = LastClickType(value)
            LOGGER.info("%s: Button Click %s", self.name, self.last_click_type.name)
        else:
            LOGGER.error("Unhandled attribute update for %s: %s, %s = %s", self.name, cluster, attribute, value)

    def online_offline_event(self):
        """ Set the online state of the device """
        # Transition to offline
        if self.online:
            if self.last_battery_report < (time.now() - OFFLINE_TIMEOUT):
                self.online = False
                LOGGER.warning("%s: offline", self.name)

        # Transition to online
        else:
            if self.last_battery_report >= (time.time() - OFFLINE_TIMEOUT):
                self.online = True
                LOGGER.info("%s: online", self.name)


def build_device_list(event_q):
    """ Use the config file to build the wanted device object instances """
    devices = []
    for dev in cfg.HOME_ZB_DEVICES:
        if dev["type"] == "WindowDoorSensor":
            devices.append(
                WindowDoorSensor(
                    eui=dev["eui"],
                    name=dev["name"],
                    event_q=event_q,
                    alarm=dev["alarm"],
                    freezer=dev["freezer"]
                )
            )
        elif dev["type"] == "Siren":
            devices.append(
                Siren(
                    eui=dev["eui"],
                    name=dev["name"],
                    event_q=event_q
                )
            )
        elif dev["type"] == "Button":
            devices.append(
                Button(
                    eui=dev["eui"],
                    name=dev["name"],
                    event_q=event_q
                )
            )
        else:
            LOGGER.error("Unknown device type in config.py %s for eui %s", dev["type"], dev["eui"])

    return devices


def tests():
    """ Entry point for tests """

    event_q = queue.Queue()

    device_list = build_device_list(event_q)

    zb_home = at.ZigbeeDevice(name="zb_home", port=cfg.HOME_ZB_PORT)

    zb_home_update_thread = threading.Thread(
        target=zb_update_worker,
        args=(zb_home, device_list),
        daemon=True,
        name='zb_home_update_thread',
    )
    zb_home_update_thread.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    tests()
