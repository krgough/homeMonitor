"""

Check for train delays and if there are any then emit a system event
We have a schedule defined for indicating train delays so we only emit events during those times.

"""

import logging
import time
import threading

import home_monitor.train_times as tt
import home_monitor.config as cfg


LOGGER = logging.getLogger(__name__)

TRAIN_DELAYS_CHECK_INTERVAL = 60 * 10


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-few-public-methods
class State:
    """ Provides utility functions for the individual states within the state machine. """

    def __init__(self, name, event_q, from_station: str, to_station: str):
        self.name = name
        self.event_q = event_q
        self.from_station = from_station
        self.to_station = to_station
        LOGGER.info('Entering state: %s', str(self))

    def on_event(self):
        """Handle events that are delegated to this State."""

        delays = tt.get_delays(self.from_station, self.to_station)
        sched_on = cfg.schedule_check(cfg.TRAIN_DELAY_INDICATION_SCHEDULE)

        for delay in delays:
            LOGGER.debug(delay)

        return delays, sched_on

    def put_event(self, event):
        """ Put the event on the system event queue """
        LOGGER.info('Putting event %s on queue from %s', event, self.name)
        self.event_q.put(event, self.name)

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
        self.put_event(cfg.TrainEvents.NO_DELAYS)

    def on_event(self):
        """Handle events that are delegated to this State."""

        delays, sched_on = super().on_event()

        if delays and sched_on:
            return Delays

        # Send this event every check cycle so if bulb state was left as red
        # we can trigger a check to try and turn it off again to cancel the old alert
        self.put_event(cfg.TrainEvents.NO_DELAYS)
        return self


class Delays(State):
    """ Delays state """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.put_event(cfg.TrainEvents.DELAYS)

    def on_event(self):
        """Handle events that are delegated to this State."""

        delays, sched_on = super().on_event()

        if not delays:
            return NoDelays

        if not sched_on:
            return NoDelays

        return self


def fsm_worker(fsm):
    """Worker thread to run the state machine."""
    while True:
        fsm.on_event()
        time.sleep(TRAIN_DELAYS_CHECK_INTERVAL)


class DelayCheckerFSM():
    """ Finite State Machine to check for train delays and manage alerts """
    def __init__(self, name, event_q, from_station: str, to_station: str):
        self.name = name
        self.event_q = event_q
        self.from_station = from_station
        self.to_station = to_station

        self.state = NoDelays(
            name=self.name,
            event_q=self.event_q,
            from_station=self.from_station,
            to_station=self.to_station
        )

        worker_thread = threading.Thread(target=fsm_worker, args=(self,), daemon=True)
        worker_thread.start()
        self.thread_pool = [worker_thread]

    def on_event(self):
        """This is the state machine handler.

        If the conditions for exiting a state are met then we return the new state class.
        """
        # The next state will be the result of the on_event function.
        next_state = self.state.on_event()

        # If a next state is not current state then initialise the new state
        if next_state != self.state:
            self.state = next_state(
                name=self.name,
                event_q=self.event_q,
                from_station=self.from_station,
                to_station=self.to_station
            )


# pylint: disable=too-few-public-methods
class TestQueue():
    """ Test Queue Object """
    def put(self, item):
        """ Puts an item in the queue """


def tests():
    """Run the tests for the FSM."""
    DelayCheckerFSM(
        name="delay_check_fsm",
        event_q=TestQueue(),
        from_station="GTW",
        to_station="RDH",
    )
    while True:
        time.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('zeep').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('home_monitor.train_times').setLevel(logging.ERROR)
    logging.getLogger('gtts').setLevel(logging.ERROR)
    tests()
