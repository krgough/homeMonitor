#!/usr/bin/env python3

"""
Hive Alarm Class

Class object to handle setting the alarm state according to a schedule

We save the sched_state as a variable and we check on each iteration
if the schedule state should change.  If it does then we send the
relevant state change command to Hive.  We don't check if it works.

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

        if self.acct.get_alarm_state(self.acct.homes[0]["id"]) == 'away':
            self.state = True
        else:
            self.state = False

    def set_schedule_state(self):
        """Set alarm state according to the schedule"""
        new_state = cfg.schedule_check(cfg.HIVE_ALARM_ON_SCHEDULE)

        # If existing state does not match new_state then we need to change state
        if self.state != new_state:

            if new_state:
                self.acct.set_alarm_state(home_id=self.home_id, alarm_state="away")
                LOGGER.info("ARMING Hive Alarm")
            else:
                self.acct.set_alarm_state(self.acct.homes[0]["id"], alarm_state='home')
                LOGGER.info("DISARMING Hive Alarm")

        self.state = new_state

    def __str__(self):
        """Return the acct object as a string"""
        return self.acct.__str__()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    alarm = HiveAlarm()
    LOGGER.debug(alarm)
    alarm.set_schedule_state()
