"""

Voice Class used by multiple other modules so placed here so both can import.

"""
import logging
import os

from home_monitor import train_times2 as tt

LOGGER = logging.getLogger(__name__)


def timestamp_from_time_string(time_string):
    """Takes a time_string of the form HH:MM and returns seconds"""
    hours, minutes = time_string.split(":")
    seconds = (int(hours) * 60 * 60) + (int(minutes) * 60)
    return seconds


class Voice:
    """Class for creating and playing voice announcements"""

    def __init__(self):
        self.strings = []

    def build_voice_string(self, delays, from_station, to_station):
        """Build the voice strings"""
        self.strings = []
        for delay in delays:
            to_station = tt.get_station_name(delay["to"])
            from_station = tt.get_station_name(delay["from"])

            voice_string = (
                f"The {delay['std']} from {from_station} to {to_station}, is "
            )

            if delay["isCancelled"]:
                if delay["cancelReason"]:
                    voice_string += f"cancelled. {delay['cancelReason']}."
                else:
                    voice_string += "cancelled."
            else:
                voice_string += "delayed"

                try:
                    etd = timestamp_from_time_string(delay["etd"])
                    std = timestamp_from_time_string(delay["std"])
                    delay_time = int((etd - std) / 60)
                # ValueError can occur if there's no colon in the time HH:MM
                # AttributeError occurs if any vars are None
                except (ValueError, AttributeError):
                    LOGGER.error("Could not parse etd|std from the delay")
                    LOGGER.error(delay)
                    delay_time = None

                if delay_time:
                    voice_string += f" by {delay_time} minutes."

                if delay["delayReason"]:
                    voice_string += f". {delay['delayReason']}."

            self.strings.append(voice_string)

        # Null voice string for no-delays situation
        if not delays:
            voice_string = "No delays listed for trains from {} to {}."
            self.strings.append(
                voice_string.format(
                    tt.get_station_name(from_station), tt.get_station_name(to_station)
                )
            )

    def play(self, msg=None):
        """Play the given voice strings"""

        voice_strings = msg if msg else self.strings
        voice_string = " . ".join(voice_strings) + " ."

        LOGGER.debug(voice_string)
        # Form the complete command
        temp_voice_file = "/tmp/voicefile.wav"
        cmd = "pico2wave -l en-GB -w {tvf} '{vs}' && aplay {tvf} &".format(
            tvf=temp_voice_file, vs=voice_string
        )

        my_pipe = os.popen(cmd, "w")
        my_pipe.close()
