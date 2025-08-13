#!/usr/bin/env python3

"""
Hive Alarm Class

Class object to handle setting the alarm state according to a schedule

We save the sched_state as a variable and we check on each iteration
if the schedule state should change.  If it does then we send the
relevant state change command to Hive.  We don't check if it works.

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
    OVERRIDE = "override"


# pylint: disable=too-few-public-methods, too-many-arguments, too-many-positional-arguments
class State:
    """ Provides utility functions for the individual states within the state machine. """

    def __init__(self, override, trigger, siren):
        self.override = override
        self.trigger = trigger
        self.siren = siren

        LOGGER.info('Entering state: %s', str(self))

    def on_event(self):
        """Handle events that are delegated to this State."""

    def schedule_state(self):
        """Get the wanted state based on the schedule"""
        if cfg.schedule_check(cfg.SECURITY_ALARM_ON_SCHEDULE):
            schedule_state = AlarmStates.ARMED
        else:
            schedule_state = AlarmStates.DISARMED
        return schedule_state

    def __repr__(self):
        """Usess the __str__ method to describe the State."""
        return self.__str__()

    def __str__(self):
        """Returns the name of the State."""
        return self.__class__.__name__


class Disarmed(State):
    """ State when the alarm is disarmed """

    def on_event(self):
        """Handle events when the alarm is disarmed."""

        # Check if schedule wants us to be armed
        schedule_state = self.schedule_state()

        if self.override:
            return Override

        elif schedule_state == AlarmStates.ARMED:
            return Armed

        return self


class Armed(State):
    """ State when the alarm is armed """

    def on_event(self):
        """Handle events when the alarm is armed."""

        # Check if schedule wants us to be disarmed
        schedule_state = self.schedule_state()

        if self.override:
            return Override

        elif schedule_state == AlarmStates.DISARMED:
            return Disarmed

        elif self.trigger:
            return Triggered

        return self


class Triggered(State):
    """ State when the alarm has been triggered """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Start a siren warning on entry to this state
        LOGGER.warning("ALARM TRIGGERED. SIREN ACTIVATED")
        self.siren.start_warning()

        # Cancel the trigger
        self.trigger = False

    def on_event(self):
        """Handle events when the alarm is triggered"""
        schedule_state = self.schedule_state()

        if schedule_state == AlarmStates.DISARMED:
            return Disarmed

        elif self.override:
            return Override

        return self


class Override(State):
    """ State when we want to overide and warnings or modes """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Turn off any warnings
        self.siren.stop_warning()

    def on_event(self):
        """ Handle events when in override """
        if not self.override:
            # If we are no longer overriding then we go back to disarmed
            return Disarmed
        return self


# pylint: disable=too-few-public-methods
class SecurityAlarmFSM():
    """Class to manage the Security Alarm state based on a schedule

    BUTTON_LONG_PRESS toggles the override state.
    If an override is set then state is set to DISARMED and we silence any warning

    """
    def __init__(self, name, siren):

        self.name = name
        self.state = Disarmed(override=False, trigger=False, siren=siren)

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
                override=self.state.override,
                trigger=self.state.trigger,
                siren=self.state.siren
            )


def fsm_worker(alarm_fsm: SecurityAlarmFSM):
    """ Worker thread for the FSM """
    while True:
        alarm_fsm.on_event()
        time.sleep(0.1)


class Siren:
    """ Class to act a a siren obeject for testing only """
    def __init__(self):
        pass

    def start_warning(self):
        """Send a warning signal"""
        LOGGER.info("Siren activated")

    def stop_warning(self):
        """Stop the siren warning"""
        LOGGER.info("Siren deactivated")


def tests():
    """ Test Hive Alarm """

    alarm = SecurityAlarmFSM(name="Hive Alarm", siren=Siren())

    # In DISARMED check that setting override has no effect
    assert isinstance(alarm.state, Disarmed)
    time.sleep(2)
    assert isinstance(alarm.state, Disarmed)
    LOGGER.info("Setting override")
    alarm.state.override = True
    time.sleep(2)
    assert isinstance(alarm.state, Override)
    LOGGER.info("Cancelling override")
    alarm.state.override = False
    time.sleep(2)
    assert isinstance(alarm.state, Disarmed)

    # Wait for Schedule to set us in armed
    LOGGER.info("Waiting for schedule to set alarm state to ARMED")
    while True:
        if isinstance(alarm.state, Armed):
            break
        time.sleep(1)

    LOGGER.info("Setting override")
    alarm.state.override = True
    time.sleep(2)
    assert isinstance(alarm.state, Override)

    LOGGER.info("Clear override during ARMED state")
    alarm.state.override = False
    time.sleep(2)
    assert isinstance(alarm.state, Armed)

    LOGGER.info("Waiting for Schedule to return us to DISARMED")
    while True:
        if isinstance(alarm.state, Disarmed):
            break
        time.sleep(1)

    LOGGER.info("Wait for schedule to return us to ARMED")
    while True:
        if isinstance(alarm.state, Armed):
            break
        time.sleep(1)

    LOGGER.info("Trigger during ARMED")
    alarm.state.trigger = True
    time.sleep(2)
    assert isinstance(alarm.state, Triggered)

    LOGGER.info("Set override during TRIGGERED")
    alarm.state.override = True
    time.sleep(2)
    assert isinstance(alarm.state, Override)

    LOGGER.info("Clear override during TRIGGERED")
    alarm.state.override = False
    alarm.state.trigger = True
    time.sleep(2)
    assert isinstance(alarm.state, Triggered)

    LOGGER.info("Waiting for schedule to return us to Disarmed")
    while True:
        if isinstance(alarm.state, Disarmed):
            break
        time.sleep(1)
    assert isinstance(alarm.state, Disarmed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tests()
