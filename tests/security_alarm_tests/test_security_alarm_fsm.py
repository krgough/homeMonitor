"""

Tests for SecurityAlarmFSM

"""

from datetime import datetime, timedelta
import logging
import time

from home_monitor.security_alarm_fsm import SecurityAlarmFSM, Armed, Disarmed, Triggered, Deactivated

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


# pylint: disable=too-few-public-methods
class TestQueue():
    """ Simulate a receiving system event queue """
    def put(self, event, name):
        """ Pretend to put shiz on a queue """
        LOGGER.info("Event received: %s from %s", event, name)


def test():
    """ Test Hive Alarm """

    # Create a test schedule
    start_time = (datetime.now() + timedelta(seconds=60)).replace(second=0, microsecond=0) + timedelta(minutes=1)

    test_schedule = [
        (
            start_time.strftime("%H:%M"),
            (start_time + timedelta(minutes=1)).strftime("%H:%M")
        ),
        (
            (start_time + timedelta(minutes=2)).strftime("%H:%M"),
            (start_time + timedelta(minutes=3)).strftime("%H:%M")
        )
    ]
    LOGGER.info("Test schedule: %s", test_schedule)

    alarm = SecurityAlarmFSM(name="Hive Alarm", event_q=TestQueue(), schedule=test_schedule)

    # In DISARMED check that setting deactivated has no effect
    assert isinstance(alarm.state, Disarmed)
    time.sleep(2)
    assert isinstance(alarm.state, Disarmed)
    LOGGER.info("Setting deactivated")
    alarm.state.toggle_deactivate()
    time.sleep(2)
    assert isinstance(alarm.state, Deactivated)
    LOGGER.info("Cancelling deactivated")
    alarm.state.toggle_deactivate()
    time.sleep(2)
    assert isinstance(alarm.state, Disarmed)

    # Wait for Schedule to set us in armed
    LOGGER.info("Waiting for schedule to set alarm state to ARMED")
    while True:
        if isinstance(alarm.state, Armed):
            break
        time.sleep(1)

    LOGGER.info("Setting deactivated")
    alarm.state.toggle_deactivate()
    time.sleep(2)
    assert isinstance(alarm.state, Deactivated)

    LOGGER.info("Re-activate during ARMED state")
    alarm.state.toggle_deactivate()
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

    LOGGER.info("Set Deactived during TRIGGERED")
    alarm.state.toggle_deactivate()
    time.sleep(2)
    assert isinstance(alarm.state, Deactivated)

    LOGGER.info("Re-activate during ARMED period while TRIGGERED is set")
    alarm.state.trigger = True
    alarm.state.toggle_deactivate()
    time.sleep(2)
    assert isinstance(alarm.state, Triggered)

    LOGGER.info("Waiting for schedule to return us to Disarmed")
    while True:
        if isinstance(alarm.state, Disarmed):
            break
        time.sleep(1)
    assert isinstance(alarm.state, Disarmed)
