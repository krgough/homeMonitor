#!/usr/bin/env python3

"""
Hive Alarm Class

Class object to handle setting the alarm state according to a schedule

"""
import logging

import config as cfg
import hive

LOGGER = logging.getLogger(__name__)


class HiveAlarm():
    """Class to manage the Hive Alarm state based on a schedule"""
    def __init__(self) -> None:
        self.acct = hive.Account(hive.AUTH_DATA)
        self.home_id = self.acct.homes[0]["id"]
        self.state = self.acct.get_alarm_state(self.home_id)

    def set_schedule_state(self):
        """Set alarm state according to the schedule"""
        self.state = self.acct.get_alarm_state(self.home_id)

        # If sched is on and alarm is off the arm the system
        if cfg.schedule_check(cfg.HIVE_ALARM_ON_SCHEDULE) and self.state == "home":
            self.acct.set_alarm_state(home_id=self.home_id, alarm_state="away")

        if not cfg.schedule_check(cfg.HIVE_ALARM_ON_SCHEDULE) and self.state == 'away':
            self.acct.set_alarm_state(self.acct.homes[0]["id"], alarm_state='home')

        self.state = self.acct.get_alarm_state(self.home_id)
        return self.state

    def __str__(self):
        """Return the acct object as a string"""
        return self.acct.__str__()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    alarm = HiveAlarm()
    LOGGER.debug(alarm)
