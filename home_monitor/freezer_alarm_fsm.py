'''
Created on 21 Feb 2021

@author: keithgough

TODO: Deal with red light conflict - No conf
TODO: Move out of hours times to cfg

'''
import datetime
import time
import logging
import config as cfg

LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class Sensor:
    """ Test Sensor """
    def __init__(self):
        self.last_report = time.time()
        self.temp_high = False
        self.long_press_received = False


class Bulb:
    """ Test Bulb """
    def __init__(self):
        self.colour = 'white'
        self.bulb_on = True

    def is_white(self):
        """ thing """
        return self.colour == 'white'

    def is_green(self):
        """ thing """
        return self.colour == 'green'

    def is_blue(self):
        """ thing """
        return self.colour == 'blue'

    def set_blue(self):
        """ thing """
        self.colour = 'blue'

    def set_green(self):
        """ thing """
        self.colour = 'green'

    def set_white(self):
        """ thing """
        self.colour = 'white'

    def set_white_off(self):
        """ thing """
        self.colour = 'white'
        self.bulb_on = False


class State:
    """
    We define a state object which provides some utility functions for the
    individual states within the state machine.
    """

    def __init__(self, bulb, sensor):
        self.sensor = sensor
        self.bulb = bulb
        LOGGER.debug('Entering state: %s', str(self))

    def on_event(self):
        """ Handle events that are delegated to this State. """

    def __repr__(self):
        """ Usess the __str__ method to describe the State. """
        return self.__str__()

    def __str__(self):
        """ Returns the name of the State. """
        return self.__class__.__name__


class TempNormal(State):
    """ Temperature is normal """
    def on_event(self):
        """ Handle the events """
        # We should recieve temperature reports every 5mins

        # If too hot the transition to state=TempHigh
        if self.sensor.temp_high:
            return TempHigh

        # If not recent reports then transition to state=SensorOffline
        if time.time() - self.sensor.last_report > (60 * 60):
            return SensorOffline

        return self


class TempHigh(State):
    """ Temperature is too high.
        Show a blue light and wait for a long button
        press to acknowledge the error state

    """
    def __init__(self, bulb, sensor):
        super().__init__(bulb, sensor)
        LOGGER.debug("Freezer Alarm - setting bulb blue")
        self.bulb.set_blue()

    def on_event(self):
        if self.sensor.long_press_received:
            LOGGER.debug("Exiting TempHigh setting bulb to white_on")
            self.sensor.long_press_received = False
            self.bulb.set_white()
            return Disabled
        return self


class Disabled(State):
    """ We wait in disabled until the temperarture
        drops to normal then we re-enble by jumping
        to state=TempNormal

        We use 1'C hysteresis from threshold to reset
    """
    def on_event(self):
        if (self.sensor.temp_high is False and
                time.time() - self.sensor.last_report < (60 * 12)):
            LOGGER.debug("Temp is normal - enabling alarm")
            return TempNormal
        return self


class SensorOffline(State):
    """ Show a green light (Unless it's the middle of the night)
        Exit if long button press or if sensor comes back online
    """
    def __init__(self, bulb, sensor):
        super().__init__(bulb, sensor)

        # If bulb is not green and schedule allows then show_green
        schedule = cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE
        if cfg.schedule_check(schedule) and not self.bulb.is_green():
            LOGGER.debug("Sensor Offline - setting bulb green")
            self.bulb.set_green()

        else:
            LOGGER.debug("Sensor Offline - but out of hours, so no light")

    def on_event(self):
        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        state = None
        if time.time() - self.sensor.last_report < (60 * 5):
            state = TempNormal

        # If we have a long_press on the button then we are
        # disabling/acknowleging the error condition so
        # transition to state=Disabled
        elif self.sensor.long_press_received:
            state = Disabled

        # If we are exiting this state then we may want to turn
        # the bulb off or set it to white
        if state:
            if self.bulb.is_green:
                LOGGER.debug("Setting bulb white_on")
                self.bulb.set_white()
            elif self.bulb.get_on_state == 0:
                LOGGER.debug("Setting bulb white_off")
                self.bulb.set_white_off()

            return state

        # If we are staying here then we may need to turn the bulb
        # green (we may have moved from out of hours to inside
        # hours.
        schedule = cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE
        if cfg.schedule_check(schedule) and not self.bulb.is_green():
            LOGGER.debug("Sensor Offline - setting bulb green")
            self.bulb.set_green()

        return self


class SensorStateMachine:
    """ A simple state machine
    """

    def __init__(self, bulb, sensor):
        """ Initialize the components.

        """
        self.bulb = bulb
        self.sensor = sensor
        # Start with a default state.
        self.state = TempNormal(bulb, sensor)

    def on_event(self):
        """  This is the state machine handler.  If the conditions
             for exiting a state are met then we return the new
             state class.
        """
        # The next state will be the result of the on_event function.
        next_state = self.state.on_event()

        # Reset any long press events
        self.sensor.long_press_received = False

        # If a next state is not current state then initialise the new state
        if next_state != self.state:
            self.state = next_state(self.bulb, self.sensor)


def temp_high_event(sensor):
    """ Test event """
    LOGGER.debug("Setting temp high")
    sensor.temp_high = True


def temp_low_event(sensor):
    """ Test event """
    LOGGER.debug("Setting temperature low")
    sensor.temp_high = False
    sensor.last_report = time.time()


def temp_normal_event(sensor):
    """ Test event """
    LOGGER.debug("Setting temp low")
    sensor.temp_high = False
    sensor.last_report = time.time()


def long_press_event(sensor):
    """ Test event """
    LOGGER.debug("Settinglong_press")
    sensor.long_press_received = True


def sensor_offline_event(sensor):
    """ Test event """
    LOGGER.debug("Setting last_report to very old")
    sensor.last_report = 0


def sensor_online_event(sensor):
    """ Test event """
    LOGGER.debug("Setting last_report to very new")
    sensor.last_report = time.time()


def tests():
    """ Some test calls """
    sensor = Sensor()
    bulb = Bulb()

    sensor_sm = SensorStateMachine(bulb, sensor)

    while True:

        # TempNormal to Temp High
        temp_high_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'TempHigh'
        LOGGER.debug("State = %s", sensor_sm.state)

        # Remain in TempHigh even if temp resets
        temp_normal_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'TempHigh'
        assert bulb.is_blue()
        LOGGER.debug("State = %s", sensor_sm.state)

        # Exit TempHigh to Disabled/Acknowledged
        # Set temp high to make sure we stay in Disabled
        temp_high_event(sensor)
        long_press_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'Disabled'
        assert not sensor.long_press_received
        assert bulb.is_white()
        LOGGER.debug("State = %s", sensor_sm.state)

        # Remain in Disabled
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'Disabled'
        LOGGER.debug("State = %s", sensor_sm.state)

        # Auto re-enable when temp drops again
        temp_low_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'TempNormal'
        LOGGER.debug("State = %s", sensor_sm.state)

        # Take sensor offline
        sensor_offline_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'SensorOffline'
        assert bulb.is_green()
        LOGGER.debug("State = %s", sensor_sm.state)

        # Take sensor back online
        sensor_online_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'TempNormal'
        assert bulb.is_white()
        LOGGER.debug("State = %s", sensor_sm.state)

        # Take sensor offline
        sensor_offline_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'SensorOffline'
        assert bulb.is_green()
        LOGGER.debug("State = %s", sensor_sm.state)

        # Goto Disabled
        long_press_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'Disabled'
        assert bulb.is_white()
        assert not sensor.long_press_received
        LOGGER.debug("State = %s", sensor_sm.state)

        # Re-enable
        temp_low_event(sensor)
        sensor_sm.on_event()
        assert str(sensor_sm.state) == 'TempNormal'
        assert bulb.is_white()
        LOGGER.debug("State = %s", sensor_sm.state)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tests()
