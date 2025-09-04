"""

Fixture for FreezerAlarmFSM

"""

import logging
import pytest


from home_monitor import freezer_alarm_fsm
from home_monitor.config import SystemEventQueue


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for all tests."""
    # Set the root logger's level to DEBUG to capture all messages
    logging.basicConfig(level=logging.DEBUG, force=True)


@pytest.fixture
def fsm():
    """A pytest fixture that creates and returns a FreezerAlarmFSM object."""
    return freezer_alarm_fsm.FreezerAlarmFSM(name="FreezerAlarmFSM", event_q=SystemEventQueue())
