"""
Created on 21 Feb 2021

@author: keithgough

"""

import logging
import time
import threading

import home_monitor.config as cfg
from home_monitor.config import SystemEvents, FREEZER_SENSOR_OFFLINE_SCHEDULE

LOGGER = logging.getLogger(__name__)

# Dummy schedules for testing
NIGHT = [("23:58", "23:59")]
DAY = [("00:01", "23:59")]


THREAD_SLEEP = 0.1

# pylint: disable=too-few-public-methods, too-many-arguments, too-many-positional-arguments


class State:
    """ Provides utility functions for the individual states within the state machine. """

    def __init__(self, name, event_q, schedule, sensor_online=False, temp_high=False, disabled=False):
        self.name = name
        self.schedule = schedule
        self.event_q = event_q
        self.sensor_online = sensor_online
        self.temp_high = temp_high
        self.disabled = disabled
        LOGGER.info('Entering state: %s', str(self))

    def on_event(self):
        """Handle events that are delegated to this State."""

    def __repr__(self):
        """Usess the __str__ method to describe the State."""
        return self.__str__()

    def __str__(self):
        """Returns the name of the State."""
        return self.__class__.__name__

    def put_event(self, event):
        """Put an event onto the event queue."""
        LOGGER.info('Putting event %s on queue from %s', event, self.name)
        self.event_q.put(event, self.name)


class TempNormal(State):
    """Temperature is normal"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.put_event(SystemEvents.FREEZER.FREEZER_ALARM_TEMP_NORMAL)

    def on_event(self):
        """Handle the events"""
        # If sensor is offline then goto the offline states
        if not self.sensor_online:
            if cfg.schedule_check(self.schedule):
                return OfflineDay
            return OfflineNight

        # If online and too hot then transition to state=TempHigh
        if self.temp_high:
            return TempHigh

        return self


class TempHigh(State):
    """ Temperature is too high
    Show a blue light and wait for a long button press to acknowledge the error state
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.put_event(SystemEvents.FREEZER.FREEZER_ALARM_TEMP_HIGH)

    def on_event(self):
        if self.disabled:
            return Disabled

        return self


class Disabled(State):
    """ Wait in disabled until the temperature drops to normal or we force enable with a button press
    We re-enable by jumping to state=TempNormal
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.put_event(SystemEvents.FREEZER.FREEZER_ALARM_DISABLED)

    def on_event(self):
        if self.sensor_online and not self.temp_high:
            self.disabled = False
            return TempNormal

        if self.disabled is False:
            return TempNormal

        return self


class OfflineDay(State):
    """Show a green light (Unless it's the middle of the night)
    Exit if long button press or if sensor comes back online
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.put_event(SystemEvents.FREEZER.FREEZER_ALARM_SENSOR_OFFLINE_DAY)

    def on_event(self):

        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        if self.sensor_online:
            return TempNormal

        # If we have a long_press on the button then we are
        # disabling/acknowleging the error condition so
        # transition to state=Disabled
        if self.disabled:
            return Disabled

        # If it is now night then switch to OfflineNight
        if not cfg.schedule_check(self.schedule):
            return OfflineNight

        return self


class OfflineNight(State):
    """ Show a green light (Unless it's the middle of the night)
    Exit if long button press or if sensor comes back online
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.put_event(SystemEvents.FREEZER.FREEZER_ALARM_SENSOR_OFFLINE_NIGHT)

    def on_event(self):
        # If we have a recent report then sensor is online
        # so tansition back to state=TempNormal
        if self.sensor_online:
            return TempNormal

        # If it is now day then switch to OfflineDay
        if cfg.schedule_check(self.schedule):
            return OfflineDay

        # If we have been set to disabled by a long button press then goto disabled state
        if self.disabled:
            return Disabled

        return self


def fsm_worker(ssm):
    """ Run the state machine worker in a thread"""
    while True:
        ssm.on_event()
        time.sleep(THREAD_SLEEP)  # Sleep to avoid busy waiting


class FreezerAlarmFSM:
    """A simple state machine"""

    def __init__(self, name, event_q, schedule=None, sensor_online=True, temp_high=False, disabled=False):
        """ Start with a default state """

        self.name = name
        self.event_q = event_q

        if schedule is None:
            schedule = FREEZER_SENSOR_OFFLINE_SCHEDULE

        self.state = TempNormal(
            name=name,
            event_q=event_q,
            schedule=schedule,
            sensor_online=sensor_online,
            temp_high=temp_high,
            disabled=disabled
        )

        fsm_thread = threading.Thread(target=fsm_worker, args=(self,), daemon=True)
        fsm_thread.start()
        self.thread_pool = [fsm_thread]

    def on_event(self):
        """This is the state machine handler.
        If the conditions for exiting a state are met then we return the new state class.
        """
        # The next state will be the result of the on_event function.
        next_state = self.state.on_event()

        # If a next state is not current state then initialise the new state
        if next_state != self.state:
            self.state = next_state(
                name=self.state.name,
                event_q=self.event_q,
                schedule=self.state.schedule,
                sensor_online=self.state.sensor_online,
                temp_high=self.state.temp_high,
                disabled=self.state.disabled
            )
