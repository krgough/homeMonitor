"""

Check for train delays and if there are any then emit a system event
We have a schedule defined for indicating train delays so we only emit events during those times.

"""

import logging
import time
from typing import Optional
import threading

import home_monitor.led_pattern_generator as led
import home_monitor.train_times as tt
import home_monitor.config as cfg
from home_monitor.zigbee_hive import BulbObject
from home_monitor.voice import Voice


LOGGER = logging.getLogger(__name__)

TRAIN_DELAYS_CHECK_INTERVAL = 60 * 10


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-few-public-methods
class State:
    """ Provides utility functions for the individual states within the state machine. """

    def __init__(
                self,
                from_station: str,
                to_station: str,
                voice: Optional[Voice],
                bulb: Optional[BulbObject] = None,
                use_led: bool = False
            ):
        self.from_station = from_station
        self.to_station = to_station
        self.bulb = bulb
        self.use_led = use_led
        self.voice = voice
        LOGGER.info('Entering state: %s', str(self))

    def on_event(self):
        """Handle events that are delegated to this State."""

        delays = tt.get_delays(self.from_station, self.to_station)
        sched_on = cfg.schedule_check(cfg.TRAIN_DELAY_INDICATION_SCHEDULE)

        for delay in delays:
            LOGGER.debug(delay)

        self.voice.build_voice_string(delays, self.from_station, self.to_station)

        return delays, sched_on

    def __repr__(self):
        """Usess the __str__ method to describe the State."""
        return self.__str__()

    def __str__(self):
        """Returns the name of the State."""
        return self.__class__.__name__


class NoDelays(State):
    """ No Delays state """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Turn off any indications
        LOGGER.info("No more delays.  Attempting to cancel alert")

        if self.use_led:
            led.show_pattern("NO_DELAYS", led.Colours.GREEN_DIM)

        if self.bulb:
            if self.bulb.is_red():
                LOGGER.info("Bulb is red so set it to white")
                self.turn_off_bulb_alert()
            else:
                LOGGER.info("Bulb is not red.  Alert cancelled")

    def turn_off_bulb_alert(self):
        """ Try to turn off the bulb """
        self.bulb.set_white_off()
        if not self.bulb.is_red():
            LOGGER.info("Bulb is not red.  Alert sucessfully cancelled")
        else:
            LOGGER.error("Bulb set to white failed.  Alert still active.")

    def on_event(self):
        """Handle events that are delegated to this State."""

        delays, sched_on = super().on_event()

        if delays and sched_on:
            return Delays

        # If we have delay indications still active then try to cancel them
        if self.bulb and self.bulb.is_red():
            LOGGER.info("Bulb is red.  Alert still active")
            self.turn_off_bulb_alert()

        return self


class Delays(State):
    """ Delays state """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Turn on any indications
        LOGGER.info("Delays detected.  Activating alert")

        if self.use_led:
            led.show_pattern("CLOCK", led.Colours.RED)

        if self.bulb:
            self.bulb.set_red_on()

    def on_event(self):
        """Handle events that are delegated to this State."""

        delays, sched_on = super().on_event()

        if not delays:
            return NoDelays

        if not sched_on:
            return NoDelays

        return self


class DelayCheckerFSM():
    """ Finite State Machine to check for train delays and manage alerts """
    def __init__(
            self,
            from_station: str,
            to_station: str,
            voice: Voice,
            bulb: Optional[BulbObject] = None,
            use_led: bool = False
            ):
        self.state = NoDelays(from_station=from_station, to_station=to_station, voice=voice, bulb=bulb, use_led=use_led)

        worker_thread = threading.Thread(
            target=fsm_worker,
            args=(self,),
            daemon=True)
        worker_thread.start()
        self.threadpool = [worker_thread]

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
                from_station=self.state.from_station,
                to_station=self.state.to_station,
                voice=self.state.voice,
                bulb=self.state.bulb,
                use_led=self.state.use_led
            )


def fsm_worker(fsm):
    """Worker thread to run the state machine."""
    while True:
        fsm.on_event()
        time.sleep(TRAIN_DELAYS_CHECK_INTERVAL)


class TestBulb:
    """ Test object to mimic a bulb """
    def __init__(self):
        self.red = False

    def set_red_on(self):
        """ Turn red on """
        self.red = True

    def set_white_off(self):
        """ Turn reed off """
        self.red = False

    def is_red(self):
        """Check if the bulb is red """
        return self.red


def tests():
    """Run the tests for the FSM."""
    _ = DelayCheckerFSM(
        from_station="EDB",
        to_station="EGY",
        voice=Voice(),
        bulb=TestBulb(),
        use_led=False
    )

    while True:
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('zeep').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('home_monitor.train_times').setLevel(logging.ERROR)
    tests()
