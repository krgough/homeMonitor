"""
Test config for security alarm FSM
"""

import logging
import pytest


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for all tests."""
    # Set the root logger's level to DEBUG to capture all messages
    logging.basicConfig(level=logging.DEBUG, force=True)
