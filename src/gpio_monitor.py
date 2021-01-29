#!/usr/bin/env python3
'''
Created on 26 Nov 2018

@author: Keith.Gough

GPIO Monitor - Checks to see if a button connected to GPIOx has been pushed.
If it has been pushed then we play the train delay announcements.

We set the internal pullup on the GPIO and then setup button to pull low.

25/11/2019
Edited to comply with PEP8 (pylint).

'''
import time
import logging

import RPi.GPIO as GPIO  # @UnresolvedImport

from home_monitor import Voice

LOGGER = logging.getLogger(__name__)

GPIO_CHANNEL = 4
MIN_BUTTON_PRESS_DURATION = 0.15
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_CHANNEL, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# GPIO.setup(25, GPIO.OUT, initial=GPIO.LOW)
# GPIO.add_event_detect(4, GPIO.FALLING, callback=my_callback, bouncetime=200)


def my_callback(_, voice_strings):
    """ RPi.GPIO Callback

        First unused parameter above is required by RPi.GPIO to work
        GPIO.add_event_detect passes channel as first parameter
    """
    timeout = time.time() + MIN_BUTTON_PRESS_DURATION
    # Ignore glitches. Button press must be > MIN_BUTTON_PRESS_DURATION
    button_count = 0
    while time.time() < timeout:
        if GPIO.input(GPIO_CHANNEL):
            button_count += 1
        else:
            button_count = 0
        if button_count >= 10:
            print("Button press")
            # voice_strings = load_voice_strings(TRAIN_DELAY_STRINGS)
            voice_strings.play()
        time.sleep(0.01)


def main(voice_strings):
    """ Main Program """
    # Attach the callback function.  Note the debounce value

    # event_detect always passes channel as the first parameter so even if we
    # don't user channel we must allow it to be passed...
    # cb = lambda channel, arg1=valueToPass: functionToCall(arg1)
    callback = lambda channel, vs=voice_strings: my_callback(channel, vs)

    GPIO.add_event_detect(GPIO_CHANNEL,
                          GPIO.RISING,
                          callback=callback,
                          bouncetime=2000)

    while True:
        time.sleep(100)


if __name__ == "__main__":
    VOICE_STRINGS = Voice()
    VOICE_STRINGS.strings = ['This is a test.']
    logging.basicConfig(level=logging.DEBUG)
    main(VOICE_STRINGS)
