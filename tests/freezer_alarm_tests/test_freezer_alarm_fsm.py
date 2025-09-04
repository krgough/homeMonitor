"""

Tests for FreezerAlarmFSM

"""


import time
import logging

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


TEST_DELAY = 0.2

# Dummy schedules for testing
NIGHT = [("23:58", "23:59")]
DAY = [("00:01", "23:59")]
logging.basicConfig(level=logging.DEBUG)


# pylint: disable=too-few-public-methods
class TestQueue():
    """ Simulate a receiving system event queue """
    def put(self, event):
        """ Pretend to put shiz on a queue """
        LOGGER.info("Event received: %s", event)


def temp_high_event(fsm):
    """Test event"""
    LOGGER.debug("Setting temp high")
    fsm.state.temp_high = True


def temp_low_event(fsm):
    """Test event"""
    LOGGER.debug("Setting temperature low")
    fsm.state.temp_high = False
    fsm.state.sensor_online = True


def temp_normal_event(fsm):
    """Test event"""
    LOGGER.debug("Setting temp low")
    fsm.state.temp_high = False
    fsm.state.sensor_online = True


def toggle_disabled(fsm):
    """Test event"""
    LOGGER.debug("Toggling disabled")
    fsm.state.disabled = not fsm.state.disabled


def sensor_offline_event(fsm):
    """Test event"""
    LOGGER.debug("Setting last_report to very old")
    fsm.state.sensor_online = False


def sensor_online_event(fsm):
    """Test event"""
    LOGGER.debug("Setting last_report to very new")
    fsm.state.sensor_online = True


def test1(fsm):
    """TEMP_NORMAL > OFFLINE_NIGHT > TEMP_NORMAL"""
    fsm.state.schedule = NIGHT
    # Goto offline night
    sensor_offline_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineNight'

    # Check we stay in OfflineNight
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineNight'

    # Now go back online night i.e. TempNormal
    sensor_online_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'


def test2(fsm):
    """TEMP_NORMAL > OFFLINE_DAY > OFFLINE_NIGHT > DISABLED > TEMP_NORMAL"""

    # Goto OfflineDay
    fsm.state.schedule = DAY
    sensor_offline_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineDay'

    # Check we stay in OfflineDay
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineDay'

    # Goto OfflineNight
    fsm.state.schedule = NIGHT
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineNight'

    # Check we stay in OfflineNight
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineNight'

    # Goto Disabled
    toggle_disabled(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'Disabled'

    # Check we stay in Disabled
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'Disabled'

    # Goto TempNormal from Disabled
    temp_low_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'

    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'

    LOGGER.info("Test 2 is complete")


def test3(fsm):
    """TEMP_NORMAL > OFFLINE_NIGHT > OFFLINE_DAY > DISARMED > TEMP_NORMAL"""

    # Goto OfflineNight
    fsm.state.schedule = NIGHT
    sensor_offline_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineNight'
    # Check we stay in OfflineNight
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineNight'

    # Goto OfflineDay
    fsm.state.schedule = DAY
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineDay'
    # Check we stay in OfflineDay
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineDay'

    # Goto Disabled
    toggle_disabled(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'Disabled'
    # Check we stay in Disabled
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'Disabled'

    # Goto TempNormal from Disabled
    temp_low_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'
    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'

    LOGGER.info("Test 3 is complete")


def test4(fsm):
    """TEMP_NORMAL > OFFLINE_DAY > TEMP_NORMAL"""

    # Goto OfflineDay
    fsm.state.schedule = DAY
    sensor_offline_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineDay'
    # Check we stay in OfflineDay
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'OfflineDay'

    # Goto TempNormal
    sensor_online_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'
    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'

    LOGGER.info("Test 4 is complete")


def test5(fsm):
    """TEMP_NORMAL > TEMP_HIGH > DISARMED > TEMP_NORMAL"""

    # Goto TempHigh
    sensor_online_event(fsm)
    fsm.state.schedule = DAY
    temp_high_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempHigh'
    # Check we stay in TempHigh∏
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempHigh'

    # Goto Disabled
    toggle_disabled(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'Disabled'
    # Check we stay in Disabled
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'Disabled'

    temp_normal_event(fsm)
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'
    # Check we stay in TempNormal
    time.sleep(TEST_DELAY)
    assert str(fsm.state) == 'TempNormal'

    LOGGER.info("Test 5 is complete")
