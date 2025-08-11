"""

Monitor the Home Zigbee network (alternative to Hive Zigbee) and handle events.

- Handle check-ins from devices. Keeo track of node ID vs eui.
- Log the freezer temperature and battery level
- Log the WDS states and battery levels
- Log the Siren state
- Implement a PANEL function to handle alarm ARM/DISARM and trigger siren if WDS opens during ARM state

"""

import logging
import queue
import time
import threading

import zigbeetools.threaded_serial as at
import home_monitor.config as cfg

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)  # Set default logging level to INFO

formatter = logging.Formatter('%(asctime)s:%(name)s,%(levelname)s,%(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

# SED:00124B00160561DE,3E16
# CHECKIN:3E16,06
# REPORTATTR:3E16,06,0402,0000,29,0ABE
# REPORTMATTR:7967,01,1039,0006,FD03,18,04
# ZONESTATUS:58FD,06,0061,00,06,0000


MATCH_PATTERNS = [
    {"name": "REPORTATTR",  "fields": ['node_id', 'ep', 'clust_id', 'attr_id', 'value', 'type', 'status']},
    {"name": "REPORTMATTR", "fields": ['node_id', 'ep', 'manuf_id', 'clust_id', 'attr_id', 'value', 'type', 'status']},
    {"name": "CHECKIN",     "fields": ['node_id', 'ep']},
    {"name": "ZONE_STATUS", "fields": ['node_id', 'ep', 'zone_status', 'extended_status', 'zone_id', 'delay']},
    {"name": "SED",         "fields": ['eui', 'node_id']},
]


MAX_SEND_ATTEMPTS = 3
SEND_RETRY_TIMEOUT = 5  # seconds


def parse_message(msg, pattern):
    """ Parse the message into a dict based on the given pattern """
    msg_fields = msg.split(',')
    msg_fields[0] = msg_fields[0].replace('REPORTMATTR:', '')  # Remove prefix
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
        while not coordinator.listener_q.empty():
            msg = coordinator.listener_q.get()
            LOGGER.debug("Received message: %s", msg)

            for pattern in MATCH_PATTERNS:
                if msg.startswith(pattern["name"]):
                    data = parse_message(msg, pattern)
                    LOGGER.debug("Matched pattern: %s, node_id: %s", pattern["name"], data["node_id"])
                    handle_attribute_update(coordinator, data, device_list)
                    break

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
        if resp_state:
            eui = resp_value.split(',')[1]
            dev = find_device_by_eui(eui, device_list)
            dev.node_id = msg_data['node_id']  # Update the node_id if found by eui

    if dev:
        LOGGER.info("Updating device %s with attribute report: %s", dev.name, msg_data)
        dev.attribute_report(msg_data['clust_id'], msg_data['attr_id'], msg_data['value'])
    else:
        LOGGER.error("Node_id %s or eui %s not found in device list", msg_data['node_id'], msg_data['eui'])


# pylint: disable=too-few-public-methods
class ZigbeeDevice:
    """Base class for Zigbee devices"""

    def __init__(self, eui, name, event_q):
        self.name = name
        self.eui = eui
        self.node_id = None  # Node ID will be set when the device is paired
        self.event_q = event_q
        self.online = False  # Default state, can be overridden by subclasses


class WindowDoorSensor(ZigbeeDevice):
    """Class for handling Window/Door Sensors"""

    def __init__(self, eui, name, event_q, freezer_sensor=False, alarm_sensor=False):
        super().__init__(eui, name, event_q)
        self.state = None
        self.battery_voltage = None
        self.temperature = None
        self.freezer_sensor = freezer_sensor
        self.alarm_sensor = alarm_sensor

        self.last_checkin = 0
        self.last_battery_report = 0
        self.last_temperature_report = 0

    def set_online_state(self):
        """Set the online state of the device"""
        offline_timeout = 60 * 5  # 5 minutes

        # Transition to offline
        if self.online:
            if self.last_temperature_report < (time.now() - offline_timeout):
                self.online = False
                LOGGER.warning("Device %s is offline", self.name)
                if self.freezer_sensor:
                    LOGGER.warning("Freezer sensor %s is offline", self.name)
                    self.event_q.put("FREEZER_SENSOR_OFFLINE")

        # Transition to online
        else:
            if self.last_temperature_report >= (time.time() - offline_timeout):
                self.online = True
                LOGGER.info("Device %s is now online", self.name)
                if self.freezer_sensor:
                    LOGGER.info("Freezer sensor %s is now online", self.name)
                    self.event_q.put("FREEZER_SENSOR_ONLINE")

    def attribute_report(self, cluster, attribute, value):
        """Set the battery voltage of the device"""

        if cluster == "Power Configuration Cluster" and attribute == "batteryVoltage":
            self.battery_voltage = value
            self.last_battery_report = time.time()
            LOGGER.debug("Battery voltage for %s: %s", self.name, value)

        elif cluster == "Temperature Measurement Cluster" and attribute == "measuredValue":
            new_temperature = value / 100.0
            self.last_temperature_report = time.time()
            LOGGER.info("Temperature for %s: %.2f °C", self.name, self.temperature)
            self.set_online_state()
            self.freezer_temp_event(new_temperature)

        else:
            LOGGER.error("Unhandled attribute update for %s: %s, %s = %s", self.name, cluster, attribute, value)

    def freezer_temp_event(self, new_temperature):
        """Handle freezer temperature event"""

        # Transition to LOW temp (Temp Normal)
        if self.temperature > cfg.FREEZER_TEMP_THOLD:
            if new_temperature < cfg.FREEZER_TEMP_THOLD:
                LOGGER.info("Freezer temperature for %s is below threshold: %.2f °C", self.name, new_temperature)
                self.event_q.put("FREEZER_TEMP_LOW")

        if self.freezer_sensor and self.temperature < cfg.FREEZER_TEMP_THOLD:
            LOGGER.warning("Freezer temperature for %s is below threshold: %.2f °C", self.name, self.temperature)
            self.event_q.put("FREEZER_TEMP_LOW")

            if self.freezer_sensor and self.temperature < cfg.FREEZER_TEMP_THOLD:
                LOGGER.warning("Freezer temperature for %s is below threshold: %.2f °C", self.name, self.temperature)
                self.event_q.put("FREEZER_TEMP_LOW")

        self.temperature = new_temperature
        self.last_temperature_report = time.time()


class Siren(ZigbeeDevice):
    """ Class for handling Siren devices """

    def __init__(self, eui, name):
        super().__init__(eui, name, event_q=None)
        self.warning_state = False  # Whether or not the siren is going off
        self.battery_voltage = None
        self.battery_temperature = None

    def attribute_report_event(self, clust, attr, value):
        """ Update the attribute """
        if clust.name == "Power Configuration Cluster" and attr.name == "batteryVoltage":
            self.battery_voltage = value
            LOGGER.info("Battery level for %s: %s", self.eui, value)
        else:
            LOGGER.error("Unhandled attribute update for %s: %s, %s = %s", self.eui, clust.name, attr.name, value)


def main():
    """ Entry point for tests """

    event_q = queue.Queue()

    device_list = [
        WindowDoorSensor(eui="00124B00160561DE", name="Garage RHS", event_q=event_q, freezer_sensor=True),
    ]

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
    main()
