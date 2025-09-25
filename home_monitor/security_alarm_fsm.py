#!/usr/bin/env python3

"""

Hive Alarm Class
Class object to handle setting the alarm state according to a schedule

"""

from enum import Enum
import logging
import time
import threading

import home_monitor.config as cfg

LOGGER = logging.getLogger(__name__)


class AlarmStates(Enum):
    """ States for the Alarm """
    ARMED = "armed"
    DISARMED = "disarmed"
    TRIGGERED = "triggered"
    DEACTIVATED = "deactivated"


# pylint: disable=too-few-public-methods, too-many-arguments, too-many-positional-arguments
class State:
    """ Provides utility functions for the individual states within the state machine. """

    def __init__(self, name, event_q, deactivated, trigger, schedule):
        self.name = name
        self.event_q = event_q
        self.deactivated = deactivated
        self.trigger = trigger
        self.schedule = schedule

        LOGGER.info('Entering state: %s', str(self))

    def on_event(self):
        """Handle events that are delegated to this State."""

    def schedule_state(self):
        """Get the wanted state based on the schedule"""
        if cfg.schedule_check(self.schedule):
            schedule_state = AlarmStates.ARMED
        else:
            schedule_state = AlarmStates.DISARMED
        return schedule_state

    def toggle_deactivate(self):
        """ Toggle the deactivated state """
        self.deactivated = not self.deactivated

    def __repr__(self):
        """Usess the __str__ method to describe the State."""
        return self.__str__()

    def __str__(self):
        """Returns the name of the State."""
        return self.__class__.__name__

    def event_put(self, event):
        """Put an event onto the event queue."""
        LOGGER.info('Putting event %s on queue from %s', event, self.name)
        self.event_q.put(event, self.name)


class Disarmed(State):
    """ State when the alarm is disarmed """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_put(cfg.SecurityEvents.ALARM_DISARMED)

    def on_event(self):
        """Handle events when the alarm is disarmed."""

        # Check if schedule wants us to be armed
        schedule_state = self.schedule_state()

        if self.deactivated:
            return Deactivated

        if schedule_state == AlarmStates.ARMED:
            return Armed

        return self


class Armed(State):
    """ State when the alarm is armed """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_put(cfg.SecurityEvents.ALARM_ARMED)

    def on_event(self):
        """Handle events when the alarm is armed."""

        # Check if schedule wants us to be disarmed
        schedule_state = self.schedule_state()

        if self.deactivated:
            return Deactivated

        if schedule_state == AlarmStates.DISARMED:
            return Disarmed

        if self.trigger:
            return Triggered

        return self


class Triggered(State):
    """ State when the alarm has been triggered """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Start a siren warning on entry to this state
        LOGGER.warning("ALARM TRIGGERED. SIREN ACTIVATED")
        self.event_put(cfg.SecurityEvents.ALARM_TRIGGERED)

    def on_event(self):
        """Handle events when the alarm is triggered"""
        schedule_state = self.schedule_state()

        if schedule_state == AlarmStates.DISARMED:
            return Disarmed

        if self.deactivated:
            return Deactivated

        return self


class Deactivated(State):
    """ State when we want to deactivate any warnings or mode changes """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_put(cfg.SecurityEvents.ALARM_DEACTIVATED)

    def on_event(self):
        """ Handle events when in deactivated """
        # If we are no longer deactivated then we go back to disarmed
        if not self.deactivated:
            self.event_put(cfg.SecurityEvents.ALARM_ACTIVATED)
            return Disarmed
        return self


class SecurityAlarmFSM():
    """Class to manage the Security Alarm state based on a schedule

    BUTTON_LONG_PRESS toggles the deactivated state.
    If `deactivated` is set then state is set to DEACTIVATED and we silence any warning

    """
    def __init__(self, name, event_q, schedule=None):

        self.name = name
        self.event_q = event_q
        if schedule is None:
            schedule = cfg.SECURITY_ALARM_ON_SCHEDULE

        self.state = Disarmed(
            name=self.name,
            event_q=self.event_q,
            deactivated=False,
            trigger=False,
            schedule=schedule
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

        # If a next state is not current state then initialise the new state
        if next_state != self.state:
            self.state = next_state(
                name=self.name,
                event_q=self.state.event_q,
                deactivated=self.state.deactivated,
                trigger=self.state.trigger,
                schedule=self.state.schedule
            )


def fsm_worker(alarm_fsm: SecurityAlarmFSM):
    """ Worker thread for the FSM """
    while True:
        alarm_fsm.on_event()
        time.sleep(0.1)
