#!/usr/bin/env python3
'''
Created on 08-Oct-2020

@author: Keith.Gough
'''

import logging
import time
import threading

import zigbeetools.threaded_serial as at

import config as cfg

LOGGER = logging.getLogger(__name__)
RETRY_TIMEOUT = 0.2


class OnOffObject:
    """ Class for managing on/off objects like plugs or bulbs """

    # We must aquire a lock before using the at commands
    # Only one instance at a time can send/receive commands
    lock = threading.RLock()

    def __init__(self, dev):
        self.name = dev['name']
        self.eui = dev['eui']
        self.ep_id = dev['ep']
        self.node_id = None
        self.node = None

    def exec_zb_cmd(self, zb_func, *args):
        """ Wrapper for at commands

            In order to handle offline devices or other command failures
            we wrap the zigbee command calls with this handler.

            If we have no node_id then we try to find one before executing
            the command.

            If a command fails then device is either offline or node_id has
            changed so we set node_id to None and fail gracefully so that the
            next command call results in us trying to find the node_id again.

        """
        # If node is not initialised then try to find the node_id and setup
        # the node object.

        # We grab a thread lock to try and make each at command atomic

        with self.lock:
            if self.node is None:
                LOGGER.info("Renewing node_id for %s", self.name)
                resp_state, _, resp_value = at.get_id(self.eui, RETRY_TIMEOUT)

                if resp_state:
                    self.node_id = resp_value
                    self.node = at.NodeObj(self.node_id, self.ep_id, False)
                else:
                    LOGGER.error("ERROR: Node ID was not found. %s", self.name)
                    # LOGGER.error(resp_value)
                    return None

            # Try to execute the command
            # If we fail then destroy the node object so that we re-initialise
            # on the next command attempt.
            resp_value = None
            if self.node:
                resp_status, _, resp_value = zb_func(self.node, *args)
                if not resp_status:
                    LOGGER.error("Error in %s", zb_func)
                    self.node_id = None
                    self.node = None
                    return None

        return resp_value

    def get_on_state(self):
        """ Get the on/off state of the device
        """
        cluster = at.cluster_object("On/Off Cluster", 'server')
        attribute = at.attribute_object("On/Off Cluster", "onOff")
        resp_value = self.exec_zb_cmd(at.get_attribute,
                                      cluster,
                                      attribute,
                                      RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error('Error in get_on_state(). %s', self.name)
            return None

        if resp_value == '01':
            resp_value = 1
        else:
            resp_value = 0

        return resp_value

    def set_on_off(self, state):
        """ Set device on/off state
            1=ON, 0=OFF
            Also accepts a boolean
        """
        # Turn bulb on/off
        send_mode = 0
        state = int(state)
        resp_value = self.exec_zb_cmd(at.on_off,
                                      send_mode,
                                      state,
                                      RETRY_TIMEOUT)
        if resp_value is None:
            LOGGER.error("Error in set_on_off(). %s", self.name)
            return None
        return resp_value


class BulbObject(OnOffObject):
    """ Class for managing bulb objects
    """
    def __init__(self, dev):
        super().__init__(dev)

        # If the bulb is red when we are initialising then likely this means we
        # crashed out and left it red so we make set the alert state now and it
        # will be cleared later if app confirms no alert state
        self.alert_active = self.is_red()

    def get_color_mode(self):
        """ Find out if bulb is in colour mode or in white mode
        """
        cluster = at.cluster_object("Color Control Cluster", "server")
        attribute = at.attribute_object("Color Control Cluster", "colorMode")
        resp_value = self.exec_zb_cmd(at.get_attribute,
                                      cluster,
                                      attribute,
                                      RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error("Error getting COLOR_MODE")
            return None

        if resp_value == '02':
            resp_value = "WHITE"
        else:
            resp_value = "COLOUR"

        return resp_value

    def get_hue(self):
        """ Retrieve the current colour value (mireds)
        """
        cluster = at.cluster_object("Color Control Cluster", "server")
        attribute = at.attribute_object("Color Control Cluster", "currentHue")
        resp_value = self.exec_zb_cmd(at.get_attribute,
                                      cluster,
                                      attribute,
                                      RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error("Error getting currentHue")
            return None

        resp_value = int(resp_value, 16)

        return resp_value

    def get_colour_temp(self):
        """ Retrieve the colour temperature value (mireds)
        """
        cluster = at.cluster_object("Color Control Cluster", "server")
        attribute = at.attribute_object(
            "Color Control Cluster", "colorTemperature")
        resp_value = self.exec_zb_cmd(at.get_attribute,
                                      cluster,
                                      attribute,
                                      RETRY_TIMEOUT)
        if resp_value is None:
            LOGGER.error("Error getting colourTemperature")
            return None

        # Convert from Hex mireds to degrees Kelvin
        mireds = int(resp_value, 16)
        if mireds == 0:
            LOGGER.error("Colour temperature error. Reported value is 0")
            return None

        colour_temp = int(1000000 / mireds)

        return colour_temp

    def get_level(self):
        """ Retrieve the brightness level
        """
        cluster = at.cluster_object("Level Control Cluster", "server")
        attribute = at.attribute_object(
            "Level Control Cluster", "currentLevel")
        resp_value = self.exec_zb_cmd(at.get_attribute,
                                      cluster,
                                      attribute,
                                      RETRY_TIMEOUT)
        if resp_value is None:
            LOGGER.error("Error getting currentLevel")
            return None

        resp_value = int(100 * int(resp_value, 16) / 254)

        return resp_value

    def get_state(self):
        """ Return bulb state
        """

        # Get the on_off state, colour mode, colour and brightness
        on_off_state = self.get_on_state()
        colour_mode = self.get_color_mode()
        hue = self.get_hue()
        colour_temp = self.get_colour_temp()
        brightness = self.get_level()

        resp = {'state': on_off_state,
                'c_mode': colour_mode,
                'hue': hue,
                'c_temp': colour_temp,
                'value': brightness
                }

        # If any of the above fail then return None
        for attr in resp:
            if resp[attr] is None:
                LOGGER.error("Error getting %s", attr)
                return None

        return resp

    def set_state(self, attrs):
        """ Set the given state
            attrs is a dict as follows:
                {'state': on_off_state,
                'c_mode': colour_mode,
                'hue': hue,
                'c_temp': colour_temp,
                'value': brightness)
        """
        if attrs is None:
            LOGGER.error("Cannot set state.  Attrs are NONE")
            return

        if attrs['c_mode'] == "COLOUR":
            self.set_colour(attrs['hue'], attrs['value'])
        else:
            self.set_white(attrs['c_temp'], attrs['value'])

        self.set_on_off(attrs['state'])

    def set_colour(self, hue, value):
        """ Turn bulb on with given hue and value (brightness)
            Hue: R=0, G=120, B=240 (colour wheel)
            Value: 0-100
        """
        send_mode = 0
        sat = 'FE'  # Max saturation
        resp_value = self.exec_zb_cmd(at.move_to_hue_and_sat,
                                      send_mode,
                                      hue,
                                      sat,
                                      value,
                                      RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error("Error setting bulb color/level")

    def set_white(self, colour_temp, value):
        """ colour_temp: 2700 = warm white, 4000 = cool white
            value (brightness): 0-100
        """
        # Set colour temperature
        send_mode = 0
        duration = 0
        resp_value = self.exec_zb_cmd(
            at.colour_temperature,
            send_mode,
            colour_temp,
            duration,
            RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error("Error setting bulb color temperature.")
            return

        # Set level
        resp_value = self.exec_zb_cmd(
            at.move_to_level,
            send_mode,
            value,
            duration,
            RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error("Error setting bulb level.")

    def set_white_off(self):
        """ Turn bulb off and reset to white
        """

        # Turn off
        self.set_on_off(0)

        # Set to white
        send_mode = 0
        duration = 0
        colour_temp = 2700

        resp_value = self.exec_zb_cmd(
            at.colour_temperature,
            send_mode,
            colour_temp,
            duration,
            RETRY_TIMEOUT)

        if resp_value is None:
            LOGGER.error("Error setting bulb to white.")
            return

        if resp_value is None:
            LOGGER.error("Error setting bulb level")

        return

    def set_red(self):
        """ Turn bulb on and set it to red at 100%

            Hue: R=0, G=120, B=240 (colour wheel)
        """
        # Turn bulb on
        self.set_on_off(1)

        # Set the colour
        self.set_colour(hue=0, value=100)

    def is_red(self):
        """ Check if the bulb is red
        """
        state = self.get_state()
        if state is None:
            LOGGER.error("Bulb state check failed in is_red()")
            return False

        if (state['c_mode'] == 'COLOUR'
                and state['hue'] == 0
                and state['state'] == 1):
            return True
        return False


class Group:
    """ Class for managing a group of devices """
    def __init__(self, device_name_list):

        self.nodes = []
        for dev in device_name_list:
            self.nodes.append(OnOffObject(dev))

    def get_state(self):
        """ Get the state of the group.  If one or more devices
            if the group are ON then treat the group state as ON.
        """
        state = False
        for node in self.nodes:
            if node.get_on_state():
                state = True
        return state

    def toggle(self):
        """ Toggle all devices ON>OFF or OFF>ON
        """
        new_state = not self.get_state()

        for node in self.nodes:
            node.set_on_off(new_state)

    def group_on(self):
        """ Turn all devices in the group ON
        """
        for node in self.nodes:
            node.set_on_off(1)

    def group_off(self):
        """ Turn all devices in the group OFF
        """
        for node in self.nodes:
            node.set_on_off(0)


def main():
    """ Main Program - runs tests on a colour bulb and a group of devices
    """

    test_delay = 5

    LOGGER.info("Getting colour bulb state")
    colour_bulb = BulbObject(cfg.get_dev("Sitt Colour"))
    state = colour_bulb.get_state()

    LOGGER.info("Set bulb to white")
    colour_bulb.set_white(colour_temp=2700, value=100)
    time.sleep(test_delay)

    LOGGER.info("Set bulb to red")
    colour_bulb.set_red()
    time.sleep(test_delay)

    LOGGER.info("Return bulb to original state")
    colour_bulb.set_state(state)
    time.sleep(test_delay)

    # Group Tests
    group_names = [cfg.get_dev('Sitt Colour'),
                   cfg.get_dev('Sitt Rear'),
                   cfg.get_dev('Sitt Front'),
                   ]

    group = Group(group_names)

    LOGGER.info("Turning Group Off")
    group.group_off()
    time.sleep(test_delay)

    LOGGER.info("Turning Group On")
    group.group_on()
    time.sleep(test_delay)

    LOGGER.info("Toggle Group Off")
    group.group_off()
    time.sleep(test_delay)

    LOGGER.info("Toggle Group On")
    group.group_on()
    time.sleep(test_delay)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    THREADS = at.start_serial_threads(port=cfg.HIVE_ZB_PORT,
                                      baud=cfg.ZB_BAUD,
                                      print_status=False,
                                      rx_q=True)

    main()
