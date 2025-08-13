"""
Created on 21 Feb 2021

@author: keithgough

"""

import logging
from queue import Queue
import time
import threading

import home_monitor.config as cfg
from home_monitor.config import SystemEvents


LOGGER = logging.getLogger(__name__)

# Dummy schedules for testing
NIGHT = [("23:58", "23:59")]
DAY = [("00:01", "23:59")]

TEST_DELAY = 0.1
THREAD_SLEEP = 0.001


# pylint: disable=too-few-public-methods
class Bulb:
    """Test Bulb"""
    def __init__(self):
        self.colour = 'white'
        self.bulb_on = True

    def is_white_off(self):
        """Check if bulb is white and off"""
        return self.colour == 'white' and not self.bulb_on

    def is_white(self):
        """Check if bulb is white"""
        return self.colour == 'white'

    def is_green(self):
        """Check if bulb is green"""
        return self.colour == 'green'

    def is_blue(self):
        """Check if bulb is blue"""
        return self.colour == 'blue'

    def set_blue(self):
        """Set bulb colour to blue"""
        self.colour = 'blue'

    def set_green(self):
        """Set bulb colour to green"""
        self.colour = 'green'

    def set_white(self):
        """Set bulb to white"""
        self.colour = 'white'

    def set_white_off(self):
        """Set bulb to white and off"""
        self.colour = 'white'
        self.bulb_on = False


class Sensor:
    """Test Sensor"""
    def __init__(self, temperature_high: bool, online: bool):
        self.temperature_high = temperature_high
        self.online = online


class State:
    """ Provides utility functions for the individual states within the state machine. """

    def __init__(self, event_queue, sensor, long_press_received=False):
        self.event_queue = event_queue
        self.sensor = sensor
        self.long_press_received = long_press_received
        LOGGER.info('Entering state: %s', str(self))

    def on_event(self):
        """Handle events that are delegated to this State."""

    def __repr__(self):
        """Usess the __str__ method to describe the State."""
        return self.__str__()

    def __str__(self):
        """Returns the name of the State."""
        return self.__class__.__name__


class TempNormal(State):
    """Temperature is normal"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_queue.put(SystemEvents.FREEZER_ALARM_TEMP_NORMAL)

    def on_event(self):
        """Handle the events"""
        # If no recent reports then transition to state=SensorOffline
        schedule = cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE
        if not self.sensor.online:
            if cfg.schedule_check(schedule):
                return OfflineDay
            return OfflineNight

        # If online and too hot then transition to state=TempHigh
        if self.sensor.temperature_high:
            return TempHigh

        return self


class TempHigh(State):
    """ Temperature is too high.
    Show a blue light and wait for a long button press to acknowledge the error state
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        LOGGER.info("Freezer Alarm - setting bulb blue")
        self.event_queue.put(SystemEvents.FREEZER_ALARM_TEMP_HIGH)
        self.long_press_received = False

    def on_event(self):
        if self.long_press_received:
            LOGGER.info("Disable requested with long press.")
            self.long_press_received = False
            return Disabled
        return self


class Disabled(State):
    """We wait in disabled until the temperature drops to normal

    Then we re-enable by jumping to state=TempNormal
    We use 1'C hysteresis from threshold to reset
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_queue.put(SystemEvents.FREEZER_ALARM_DISABLED)

    def on_event(self):
        if self.sensor.online and not self.sensor.temperature_high:
            LOGGER.info("Temp is normal. Enabling alarm")
            return TempNormal
        return self


class OfflineDay(State):
    """Show a green light (Unless it's the middle of the night)
    Exit if long button press or if sensor comes back online
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # It's daytime so we can show green
        LOGGER.info("Sensor Offline - setting bulb green")
        self.event_queue.put(SystemEvents.FREEZER_ALARM_SENSOR_OFFLINE_DAY)

    def on_event(self):

        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        if self.sensor.online:
            return TempNormal

        # If we have a long_press on the button then we are
        # disabling/acknowleging the error condition so
        # transition to state=Disabled
        if self.long_press_received:
            return Disabled

        # If it is now night then switch to OfflineNight
        if not cfg.schedule_check(cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE):
            return OfflineNight

        return self


class OfflineNight(State):
    """ Show a green light (Unless it's the middle of the night)
    Exit if long button press or if sensor comes back online
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        LOGGER.info("Sensor Offline - but out of hours, so no light")
        self.event_queue.put(SystemEvents.FREEZER_ALARM_SENSOR_OFFLINE_NIGHT)

    def on_event(self):
        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        if self.sensor.online:
            return TempNormal

        # If it is now day then switch to OfflineDay
        if cfg.schedule_check(cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE):
            return OfflineDay

        # If we have a long_press on the button then we are
        # disabling/acknowleging the error condition so
        # transition to state=Disabled
        if self.long_press_received:
            return Disabled

        return self


class FreezerAlarmFSM:
    """A simple state machine"""

    def __init__(self, event_queue, sensor):
        """ Start with a default state """
        self.state = TempNormal(
            event_queue=event_queue,
            sensor=sensor,
            long_press_received=False
        )

        fsm_thread = threading.Thread(target=fsm_worker, args=(self,), daemon=True)
        fsm_thread.start()
        self.thread_pool = [fsm_thread]

    def on_event(self):
        """This is the state machine handler.

        If the conditions for exiting a state are met then we return the new
        state class.
        """
        # The next state will be the result of the on_event function.
        next_state = self.state.on_event()

        # Reset any long press events
        self.state.long_press_received = False

        # If a next state is not current state then initialise the new state
        if next_state != self.state:
            self.state = next_state(
                event_queue=self.state.event_queue,
                sensor=self.state.sensor,
                long_press_received=self.state.long_press_received
            )


def temp_high_event(sensor):
    """Test event"""
    LOGGER.debug("Setting temp high")
    sensor.temperature_high = True


def temp_low_event(sensor):
    """Test event"""
    LOGGER.debug("Setting temperature low")
    sensor.temperature_high = False
    sensor.online = True


def temp_normal_event(sensor):
    """Test event"""
    LOGGER.debug("Setting temp low")
    sensor.temperature_high = False
    sensor.online = True


def long_press_event(fsm):
    """Test event"""
    LOGGER.debug("Setting long_press")
    fsm.state.long_press_received = True


def sensor_offline_event(sensor):
    """Test event"""
    LOGGER.debug("Setting last_report to very old")
    sensor.online = False


def sensor_online_event(sensor):
    """Test event"""
    LOGGER.debug("Setting last_report to very new")
    sensor.online = True


# TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL
# TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISARMED > TEMP_NORMAL
# TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL
# TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL
# TEMP_NORMAL > DISARMED > TEMP_NORMAL

def queue_worker(event_queue, bulb):
    """ Process on the events we have in the queue"""
    while True:
        while event_queue.empty() is False:
            event = event_queue.get()

            # Process the event
            LOGGER.debug("Processing event: %s", event)
            if event == SystemEvents.FREEZER_ALARM_TEMP_NORMAL:
                bulb.set_white_off()
            elif event == SystemEvents.FREEZER_ALARM_TEMP_HIGH:
                bulb.set_blue()
            elif event == SystemEvents.FREEZER_ALARM_DISABLED:
                bulb.set_white_off()
            elif event == SystemEvents.FREEZER_ALARM_SENSOR_OFFLINE_DAY:
                bulb.set_green()
            elif event == SystemEvents.FREEZER_ALARM_SENSOR_OFFLINE_NIGHT:
                bulb.set_white_off()

        time.sleep(THREAD_SLEEP)  # Sleep to avoid busy waiting


def fsm_worker(ssm):
    """ Run the state machine worker in a thread"""
    while True:
        ssm.on_event()
        time.sleep(THREAD_SLEEP)  # Sleep to avoid busy waiting


def test1(ssm, bulb, sensor):
    """TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL"""
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = NIGHT
    bulb.bulb_on = False
    bulb.colour = 'white'
    # Goto offline night
    sensor_offline_event(sensor)
    time.sleep(0.5)
    assert str(ssm.state) == 'OfflineNight'
    assert bulb.is_white_off()

    # Check we stay in OfflineNight
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineNight'

    # Now go back online night i.e. TempNormal
    sensor_online_event(sensor)
    # ssm.on_event()
    # queue_worker(ssm.event_queue, bulb)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'
    LOGGER.info("Test 1 is complete")


def test2(ssm, bulb, sensor):
    """TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISABLED > TEMP_NORMAL"""

    # Goto OfflineDay
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = DAY
    sensor_offline_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineDay'
    assert bulb.is_green()

    # Check we stay in OfflineDay
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineDay'

    # Goto OfflineNight
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = NIGHT
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineNight'
    assert bulb.is_white_off()

    # Check we stay in OfflineNight
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineNight'

    # Goto Disabled
    long_press_event(ssm)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'Disabled'

    # Check we stay in Disabled
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'Disabled'

    # Goto TempNormal from Disabled
    temp_low_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'

    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'

    LOGGER.info("Test 2 is complete")


def test3(ssm, bulb, sensor):
    """TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL"""

    # Goto OfflineNight
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = NIGHT
    sensor_offline_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineNight'
    # Check we stay in OfflineNight
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineNight'

    # Goto OfflineDay
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = DAY
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineDay'
    assert bulb.is_green()
    # Check we stay in OfflineDay
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineDay'

    # Goto Disabled
    long_press_event(ssm)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'Disabled'
    assert bulb.is_white_off()
    # Check we stay in Disabled
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'Disabled'

    # Goto TempNormal from Disabled
    temp_low_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'
    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'

    LOGGER.info("Test 3 is complete")


def test4(ssm, bulb, sensor):
    """TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL"""

    # Goto OfflineDay
    cfg.FREEZER_SENSOR_OFFLINE_SCHEDULE = DAY
    sensor_offline_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineDay'
    assert bulb.is_green()
    # Check we stay in OfflineDay
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'OfflineDay'

    # Goto TempNormal
    sensor_online_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'
    assert bulb.is_white_off()
    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'

    LOGGER.info("Test 4 is complete")


def test5(ssm, bulb, sensor):
    """TEMP_NORMAL > TEMP_HIGH > DISARMED > TEMP_NORMAL"""

    # Goto TempHigh
    temp_high_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempHigh'
    assert bulb.is_blue()
    # Check we stay in TempHigh
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempHigh'

    # Goto Disabled
    long_press_event(ssm)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'Disabled'
    assert bulb.is_white_off()
    # Check we stay in Disabled
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'Disabled'

    temp_normal_event(sensor)
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'
    assert bulb.is_white_off()
    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(ssm.state) == 'TempNormal'

    LOGGER.info("Test 5 is complete")


def tests():
    """Some test calls - To try and test all possible transitions

    TEST1 - TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL
    TEST2 - TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISARMED > TEMP_NORMAL
    TEST3 - TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL
    TEST4 - TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL
    TEST5 - TEMP_NORMAL > TEMP_HIGH > DISARMED > TEMP_NORMAL
    """

    bulb = Bulb()
    sensor = Sensor(temperature_high=False, online=True)
    ssm_event_queue = Queue(maxsize=100)

    ssm = FreezerAlarmFSM(event_queue=ssm_event_queue, sensor=sensor)

    # fsm_thread = threading.Thread(target=fsm_worker, args=(ssm,), daemon=True)
    # fsm_thread.start()

    q_worker_thread = threading.Thread(target=queue_worker, args=(ssm_event_queue, bulb), daemon=True)
    q_worker_thread.start()

    LOGGER.info("Starting tests 1")
    test1(ssm, bulb, sensor)
    LOGGER.info("Starting tests 2")
    test2(ssm, bulb, sensor)
    LOGGER.info("Starting tests 3")
    test3(ssm, bulb, sensor)
    LOGGER.info("Starting tests 4")
    test4(ssm, bulb, sensor)
    LOGGER.info("Starting tests 5")
    test5(ssm, bulb, sensor)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tests()
