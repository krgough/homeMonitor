"""

Manage the devices on the Home Zigbee network (alternative to Hive Zigbee) and handle events.

- Provide Device class objects which represent the various Zigbee devices in the network.
- Match node id to eui for each device and keep track if node id changes
- Handling for incomming attribute reports, checkins, and other events.

"""
from enum import Enum
import logging
import time
import threading
import queue

import zigbeetools.threaded_serial as at
import zigbeetools.zigbee_clusters as zcl
import home_monitor.config as cfg
from home_monitor.config import SystemEvents


LOGGER = logging.getLogger(__name__)


OFFLINE_TIMEOUT = 60 * 21  # 21 minutes = to allow for 2 reports + 1min


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


def int8_to_dec(hex_value):
    """Convert hex string signed 8 bit number to decimal"""
    val = int(hex_value, 16)
    if val >= 128:  # If bit 7 is set (negative number)
        val -= 256  # Convert from unsigned to signed
    return val


def int16_to_dec(hex_value):
    """Convert hex string signed 16 bit number to decimal"""
    val = int(hex_value, 16)
    if val >= 32768:  # If bit 15 is set (negative number)
        val -= 65536  # Convert from unsigned to signed
    return val


def parse_message(msg, pattern):
    """ Parse the message into a dict based on the given pattern """
    msg_fields = msg.replace(f"{pattern['name']}:", "").split(",")
    msg_dict = dict(zip(pattern["fields"], msg_fields))
    return msg_dict


def find_device_by_node_id(node_id, devices):
    """Find a device in the devices dictionary by node_id"""
    for _, device in devices.items():
        if device.node_id == node_id:
            return device
    return None


def find_device_by_eui(eui, devices):
    """Find a device in the devices dictionary by eui."""
    for _, device in devices.items():
        if device.eui == eui:
            return device
    return None


def zb_update_worker(coordinator: at.ZigbeeCmdNode, device_list: list):
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
                    handle_message(coordinator, data, device_list)
                    break

        # Check if any devices have gone offline
        for _, device in device_list.items():
            device.online_offline_event()

        time.sleep(1)


def handle_message(coordinator: at.ZigbeeCmdNode, msg_data: dict, device_list: list):
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
                LOGGER.info("Found device %s with eui %s", dev.name, resp_value)
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

    # We must aquire a lock before using the at commands
    # Only one instance at a time can send/receive commands
    lock = threading.RLock()

    def __init__(self, coordinator: at.ZigbeeCmdNode, dev: dict, event_q: queue.Queue):
        self.coordinator = coordinator
        self._event_q = event_q

        self.name = dev["name"]
        self.eui = dev["eui"]
        self.ep_id = dev["ep_id"]

        self.online = False
        self.temp_high = False

        self.node_id = None  # We will set this when we dicover the node
        self.node = None  # Placeholder until we find the node

    def attribute_report_event(self, cluster, attribute, value):
        """Handle attribute report events"""

    def zone_status_event(self, zone_status):
        """Handle zone status events"""

    def put_event(self, event):
        """ Put and event on the event queue """
        LOGGER.info('Putting event %s on queue from %s', event, self.name)
        self._event_q.put(event, self.name)

    def exec_zb_cmd(self, zb_func, **kwargs):
        """ Wrapper for at commands

            In order to handle offline devices or other command failures we wrap the
            zigbee command calls with this handler.

            If we have no node_id then we try to find one before executing the command.

            If a command fails then device is either offline or node_id has changed so
            we set node_id to None and fail gracefully so that the next command call
            results in us trying to find the node_id again.

        """
        # If node is not initialised then try to find the node_id and setup
        # the node object.

        # We grab a thread lock to try and make each at command atomic

        with self.lock:
            if self.node is None:
                LOGGER.info("Renewing node_id for %s", self.name)
                resp_state, _, resp_value = self.coordinator.at_cmds.get_id(self.eui)

                if resp_state:
                    self.node_id = resp_value
                    self.node = at.node_object(node_id=self.node_id, ep_id=self.ep_id, manuf_id=None, eui=self.eui)
                else:
                    LOGGER.error("ERROR: Node ID was not found. %s", self.name)
                    # LOGGER.error(resp_value)
                    return None

            # Try to execute the command
            # If we fail then destroy the node object so that we re-initialise
            # on the next command attempt.
            resp_value = None
            if self.node:
                resp_status, _, resp_value = zb_func(node=self.node, **kwargs)
                if not resp_status:
                    LOGGER.error("Error in %s", zb_func)
                    self.node_id = None
                    self.node = None
                    return None

        return resp_value


class WindowDoorSensor(ZigbeeDevice):
    """Class for handling Window/Door Sensors"""

    def __init__(self, coordinator, dev, event_q):
        super().__init__(coordinator, dev, event_q)
        self.open = False
        self.battery_voltage = 0
        self.temperature = 0
        self.freezer_sensor = dev["freezer"]
        self.alarm_sensor = dev["alarm"]

        self.last_checkin = 0
        self.last_battery_report = 0
        self.last_temperature_report = 0

    def online_offline_event(self):
        """Set the online state of the device"""

        # Transition to offline
        if self.online:
            if self.last_temperature_report < (time.time() - OFFLINE_TIMEOUT):
                self.online = False
                self.event_q.put(SystemEvents.DEVICE.DEVICE_OFFLINE, self.name)
                LOGGER.warning("%s: offline", self.name)

        # Transition to online
        else:
            if self.last_temperature_report >= (time.time() - OFFLINE_TIMEOUT):
                self.online = True
                self.put_event(SystemEvents.DEVICE.DEVICE_ONLINE)
                LOGGER.info("%s: online", self.name)

    def attribute_report_event(self, cluster, attribute, value):
        """Set the battery voltage of the device"""

        if cluster == "Power Configuration Cluster" and attribute == "batteryVoltage":
            self.battery_voltage = int(value, 16) / 10
            self.last_battery_report = time.time()
            LOGGER.info("%s: Battery voltage %sv", self.name, self.battery_voltage)

        elif cluster == "Temperature Measurement Cluster" and attribute == "measuredValue":
            self.temperature = int16_to_dec(value) / 100
            LOGGER.info("%s: Temperature %.2f°C", self.name, self.temperature)

            self.last_temperature_report = time.time()

            if self.freezer_sensor:
                if self.temperature > cfg.FREEZER_TEMP_THOLD:
                    self.temp_high = True
                    self.put_event(SystemEvents.DEVICE.DEVICE_TEMP_HIGH)
                    LOGGER.warning("%s: Freezer temperature high %.2f°C", self.name, self.temperature)
                elif self.temp_high and self.temperature <= cfg.FREEZER_TEMP_THOLD:
                    self.temp_high = False
                    self.put_event(SystemEvents.DEVICE.DEVICE_TEMP_NORMAL)
                    LOGGER.info("%s: Freezer temperature normal %.2f°C", self.name, self.temperature)

        else:
            LOGGER.error("Unhandled attribute update for %s: %s, %s = %s", self.name, cluster, attribute, value)

    def zone_status_event(self, zone_status):
        """Handle zone status events"""
        # Bitmask AND zone_status to deterine if zone is open/closed
        new_state = bool(int(zone_status) & 0x01)

        if self.open is False and new_state is True:
            LOGGER.info("%s: open", self.name)
            if self.alarm_sensor:
                self.put_event(SystemEvents.SECURITY.ALARM_SENSOR_OPEN)
            self.open = True

        elif self.open is True and new_state is False:
            LOGGER.info("%s: closed", self.name)
            if self.alarm_sensor:
                self.put_event(SystemEvents.SECURITY.ALARM_SENSOR_CLOSED)
            self.open = False


class Siren(ZigbeeDevice):
    """ Class for handling Siren devices """

    def __init__(self, coordinator, dev, event_q):
        super().__init__(coordinator, dev, event_q)
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
            self.battery_temperature = int8_to_dec(value)
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
                self.put_event(SystemEvents.DEVICE.DEVICE_OFFLINE)
                LOGGER.warning("%s: offline", self.name)

        # Transition to online
        else:
            if self.last_battery_report >= (time.time() - OFFLINE_TIMEOUT):
                self.online = True
                self.put_event(SystemEvents.DEVICE.DEVICE_ONLINE)
                LOGGER.info("%s: online", self.name)

    def start_warning(self, duration=60):
        """ Start the siren warning """
        LOGGER.warning("%s: siren warning started", self.name)
        self.warning_state = True
        self.exec_zb_cmd(
            self.coordinator.iaswd_cmds.start_warning,
            mode=zcl.WarningMode.STOP,
            sound_level=zcl.SirenLevel.LOW,
            strobe_level=zcl.SirenLevel.HIGH,
            duration=duration
        )

    def stop_warning(self):
        """ Stop the siren warning """
        LOGGER.warning("%s: siren warning stopped", self.name)
        self.warning_state = False
        self.exec_zb_cmd(self.coordinator.iaswd_cmds.stop_warning)


class Button(ZigbeeDevice):
    """ Class for handling Button devices """

    def __init__(self, coordinator, dev, event_q):
        super().__init__(coordinator, dev, event_q)
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
            if self.last_click_type == LastClickType.SHORT_PRESS:
                self.put_event(SystemEvents.BUTTON.BTN_SHORT_PRESS)
            elif self.last_click_type == LastClickType.DOUBLE_PRESS:
                self.put_event(SystemEvents.BUTTON.BTN_DOUBLE_PRESS)
            elif self.last_click_type == LastClickType.LONG_PRESS:
                self.put_event(SystemEvents.BUTTON.BTN_LONG_PRESS)
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


def build_device_dict(coordinator, devices, event_q):
    """ Use the config file to build the wanted device object instances """
    if devices is None:
        devices = cfg.HOME_ZB_DEVICES
    devs = {}

    for dev in devices:

        if dev["type"] == "WindowDoorSensor":
            devs[dev["name"]] = WindowDoorSensor(coordinator=coordinator, dev=dev, event_q=event_q)

        elif dev["type"] == "Siren":
            devs[dev["name"]] = Siren(coordinator=coordinator, dev=dev, event_q=event_q)

        elif dev["type"] == "Button":
            devs[dev["name"]] = Button(coordinator=coordinator, dev=dev, event_q=event_q)

        else:
            LOGGER.error("Unknown device type in config.py %s for eui %s", dev["type"], dev["eui"])

    return devs


class ZigbeeHome:
    """ Class for interacting with zigbee devices on 'home' network """
    def __init__(self, name, event_q):

        self.coordinator = at.ZigbeeCmdNode(name="zb_home", port=cfg.HOME_ZB_PORT)
        self.name = name
        self.event_q = event_q
        self.last_battery_report = 0

        self.device_list = build_device_dict(
            coordinator=self.coordinator,
            devices=cfg.HOME_ZB_DEVICES,
            event_q=self.event_q
        )

        self.thread = threading.Thread(
            target=zb_update_worker,
            args=(self.coordinator, self.device_list),
            daemon=True
        )
        self.thread.start()
        self.thread_pool = [self.thread]


def tests():
    """ Entry point for tests

    Turn on siren strobe - get user to confirm it is working
    Turn it off - get user to confirm it is off

    Wait for freezer sensor temp
    Wait for button press events
    Wait for door open/close events

    """

    zb_home = ZigbeeHome(name="zb_home", event_q=queue.Queue())

    zb_home.device_list["Siren"].start_warning()

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
