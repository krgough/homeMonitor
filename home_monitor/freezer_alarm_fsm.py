'''
Created on 21 Feb 2021

@author: keithgough

TODO: Deal with red light conflict - Is there one?

'''
import time
import logging
import config as cfg

LOGGER = logging.getLogger(__name__)

# Dummy schedules for testing
NIGHT = [("23:58", "23:59")]
DAY = [("00:01", "23:59")]


# pylint: disable=too-few-public-methods
class Sensor:
    """ Test Sensor """
    def __init__(self):
        self.last_report = time.time()
        self.temp_high = False
        self.long_press_received = False

    def online(self):
        """ Sensor online check """
        return time.time() - self.last_report < cfg.SENSOR_OFFLINE_TIME


class Bulb:
    """ Test Bulb """
    def __init__(self):
        self.colour = 'white'
        self.bulb_on = True

    def is_white_off(self):
        """ thing """
        return self.colour == 'white' and not self.bulb_on

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

        # If no recent reports then transition to state=SensorOffline
        schedule = cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE
        if not self.sensor.online():
            if cfg.schedule_check(schedule):
                return OfflineDay

            return OfflineNight

        # If online and too hot then transition to state=TempHigh
        if self.sensor.temp_high:
            return TempHigh

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
        if self.sensor.online() and not self.sensor.temp_high:
            LOGGER.debug("Temp is normal - enabling alarm")
            return TempNormal
        return self


class OfflineDay(State):
    """ Show a green light (Unless it's the middle of the night)
        Exit if long button press or if sensor comes back online
    """
    def __init__(self, bulb, sensor):
        super().__init__(bulb, sensor)

        # It's daytime so we can show green
        LOGGER.debug("Sensor Offline - setting bulb green")
        self.bulb.set_green()

    def on_event(self):

        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        if self.sensor.online():
            self.bulb.set_white_off()
            return TempNormal

        # If we have a long_press on the button then we are
        # disabling/acknowleging the error condition so
        # transition to state=Disabled
        if self.sensor.long_press_received:
            self.bulb.set_white_off()
            return Disabled

        # If it is now night then switch to OfflineNight
        if not cfg.schedule_check(cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE):
            self.bulb.set_white_off()
            return OfflineNight

        return self


class OfflineNight(State):
    """ Show a green light (Unless it's the middle of the night)
        Exit if long button press or if sensor comes back online
    """
    def __init__(self, bulb, sensor):
        super().__init__(bulb, sensor)

        LOGGER.debug("Sensor Offline - but out of hours, so no light")

    def on_event(self):
        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        if self.sensor.online():
            return TempNormal

        # If it is now day then switch to OfflineDay
        if cfg.schedule_check(cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE):
            return OfflineDay

        # If we have a long_press on the button then we are
        # disabling/acknowleging the error condition so
        # transition to state=Disabled
        if self.sensor.long_press_received:
            return Disabled

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


# TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL
# TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISARMED > TEMP_NORMAL
# TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL
# TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL
# TEMP_NORMAL > DISARMED > TEMP_NORMAL


def test1(ssm, sensor, bulb):
    """ TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL """
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = NIGHT
    bulb.bulb_on = False
    bulb.colour = 'white'

    sensor_offline_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'OfflineNight'
    assert bulb.is_white_off()

    ssm.on_event()
    assert str(ssm.state) == 'OfflineNight'

    sensor_online_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'


def test2(ssm, sensor, bulb):
    """ TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISABLED > TEMP_NORMAL """
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = DAY
    sensor_offline_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'OfflineDay'
    assert bulb.is_green()
    ssm.on_event()
    assert str(ssm.state) == 'OfflineDay'

    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = NIGHT
    ssm.on_event()
    assert str(ssm.state) == 'OfflineNight'
    assert bulb.is_white_off()
    ssm.on_event()
    assert str(ssm.state) == 'OfflineNight'

    long_press_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'Disabled'
    ssm.on_event()
    assert str(ssm.state) == 'Disabled'

    temp_low_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'


def test3(ssm, sensor, bulb):
    """ TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL """
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = NIGHT
    sensor_offline_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'OfflineNight'
    ssm.on_event()
    assert str(ssm.state) == 'OfflineNight'

    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = DAY
    ssm.on_event()
    assert str(ssm.state) == 'OfflineDay'
    assert bulb.is_green()
    ssm.on_event()
    assert str(ssm.state) == 'OfflineDay'

    long_press_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'Disabled'
    assert bulb.is_white_off()
    ssm.on_event()
    assert str(ssm.state) == 'Disabled'

    temp_low_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'


def test4(ssm, sensor, bulb):
    """ TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL """
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = DAY
    sensor_offline_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'OfflineDay'
    assert bulb.is_green()
    ssm.on_event()
    assert str(ssm.state) == 'OfflineDay'

    sensor_online_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'
    assert bulb.is_white_off()
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'


def test5(ssm, sensor, bulb):
    """ TEMP_NORMAL > TEMP_HIGH > DISARMED > TEMP_NORMAL """
    temp_high_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'TempHigh'
    assert bulb.is_blue()
    ssm.on_event()
    assert str(ssm.state) == 'TempHigh'

    long_press_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'Disabled'
    assert bulb.is_white_off()
    ssm.on_event()
    assert str(ssm.state) == 'Disabled'

    temp_normal_event(sensor)
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'
    assert bulb.is_white_off()
    ssm.on_event()
    assert str(ssm.state) == 'TempNormal'


def tests():
    """ Some test calls - To try and test all possible transitions

    TEST1 - TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL
    TEST2 - TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISARMED > TEMP_NORMAL
    TEST3 - TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL
    TEST4 - TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL
    TEST5 - TEMP_NORMAL > TEMP_HIGH > DISARMED > TEMP_NORMAL

    """
    sensor = Sensor()
    bulb = Bulb()

    ssm = SensorStateMachine(bulb, sensor)

    test1(ssm, sensor, bulb)
    test2(ssm, sensor, bulb)
    test3(ssm, sensor, bulb)
    test4(ssm, sensor, bulb)
    test5(ssm, sensor, bulb)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tests()
