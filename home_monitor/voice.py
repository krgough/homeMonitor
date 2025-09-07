"""

Voice Class used to create voice announcements from text

"""

import logging
import subprocess
import tempfile
from typing import List, Union

from gtts import gTTS

from home_monitor import train_times as tt

LOGGER = logging.getLogger(__name__)


def timestamp_from_time_string(time_string):
    """Takes a time_string of the form HH:MM and returns seconds"""
    hours, minutes = time_string.split(":")
    seconds = (int(hours) * 60 * 60) + (int(minutes) * 60)
    return seconds


def build_delay_voice_strings(args):
    """Build the voice strings"""
    voice_strings = []
    delays = tt.get_delays(from_crs=args.from_station, to_crs=args.to_station)
    to_station = tt.get_station_name(crs_code=args.to_station)
    from_station = tt.get_station_name(crs_code=args.from_station)

    for delay in delays:
        voice_string = (
            f"The {delay['std']} from {from_station} to {to_station} is "
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
            else:
                voice_string += "."

            if delay["delayReason"]:
                voice_string += f" {delay['delayReason']}."

        voice_strings.append(voice_string)

    # Null voice string for no-delays situation
    if not delays:
        voice_strings.append(f"No delays listed for trains from {from_station} to {to_station}.")

    return voice_strings


def play(msgs: Union[str, List[str]]):
    """Play the given voice strings"""

    if isinstance(msgs, str):
        msgs = [msgs]

    msgs = " ".join(msgs)
    LOGGER.info(msgs)

    # Create a gTTS object. 'lang' specifies the language of the text. 'en' is for English.
    tts = gTTS(text=msgs, lang='en')

    # Save the generated audio to a temp file
    # Play the file with mpg123
    with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
        tts.save(temp_file.name)
        subprocess.run(['mpg123', '-f', '10000', '-q', temp_file.name], check=True)
