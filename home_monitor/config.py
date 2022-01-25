'''
Created on 21 Aug 2016

@author: keith
'''
import datetime
import pytz

BELL_SOUND = None
BELL_BUTTON_ID = None

INDICATOR_BULB = "Sitt Colour"
TIMEZONE = 'Europe/London'
TRAIN_DELAY_INDICATION_SCHEDULE = [("06:00", "08:00")]
FREEZER_SENSOR_OFFLINE_SCHEDULE = [("08:01", "22:00")]

FREEZER_TEMP_THOLD = -10       # Freezer temperature alert threshold
SENSOR_OFFLINE_TIME = 60 * 60  # Time in seconds before we declare offline

LOGFILE = "/tmp/home_monitor.log"

LED_PORT = "/dev/ttyS0"
LED_BAUD = 115200
GPIO_CHANNEL = 4

# Zigbee dongles need to be named properly so we don't confuse the two.
# The names (USB0, USB1) get assigned randomly at boot so we need to
# discover them using their serial numbers and then create symlinks to
# the device in /dev.  We do this using udevadm as follows...

# Add the following rules to create symlinks to the correct dongles in /dev
# Edit /etc/udev/rules.d/nano 99-com.rules to include the lines shown.
# The links will then be setup at boot or with the following command
# sudo udevadm trigger
# To discover the device serial numbers use the following command
# udevadm info --name=/dev/ttyUSB0 --attribute-walk | grep serial
# SUBSYSTEM=="tty", ATTRS{serial}=="01001DAD", SYMLINK+="BUTTON_DONGLE"
# SUBSYSTEM=="tty", ATTRS{serial}=="04000A0B", SYMLINK+="HIVE_DONGLE"
ZB_PORT = "/dev/BUTTON_DONGLE"
HIVE_ZB_PORT = "/dev/HIVE_DONGLE"
HIVE_EUI = "000D6F000C44F290"
ZB_BAUD = 115200

BUTTON_NODE_ID = "7967"       # Black Button

SITT_GROUP = ['Sitt Front', 'Sitt Rear', 'Sitt Colour']

DEVS = {
    'Sitt Colour': {'eui': '00158D00012E2189', 'ep': '01'},
    'Sitt Front': {'eui': '00158D00012E2CF1', 'ep': '01'},
    'Sitt Rear': {'eui': '001E5E09021AEBD6', 'ep': '09'},
    'Stair Plug': {'eui': '001E5E09020F2F53', 'ep': '09'},
    'Bed LEDs': {'eui': '001E5E0902171636', 'ep': '09'},
    'Garage Plug': {'eui': '001E5E09020DA01E', 'ep': '09'},
    'Temperature Sensor': {'eui': '00124B000DEF311B', 'ep': '06'}
}

# pylint: disable=invalid-name


def get_dev(dev_name):
    """ Get the wanted device from DEVS and return a dict
        add the name of the device to the dict.
    """
    dev = DEVS.get(dev_name)
    dev['name'] = dev_name
    return dev


def tz_aware(dt):
    """ Check if datetime is tz_aware """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def is_dst(dt):
    """ Check if DST is set for given datetime """
    return dt.tzinfo._dst.seconds != 0  # pylint: disable=protected-access


def local_time(dt=None, timezone=TIMEZONE):
    """ Take a given datetime and convert to local time in wanted timezone

        If given DT is naive then assume it is UTC.
        Make it TZ aware and then convert it to time in the wanted zone.

    """
    if dt is None:
        dt = datetime.datetime.utcnow()

    # If dt is naive then make it tz aware (we assume UTC to begin with)
    if not tz_aware(dt):
        dt = pytz.timezone('UTC').localize(dt)

    # Shift to wanted timezone
    dt = dt.astimezone(pytz.timezone(timezone))
    return dt


def schedule_check(schedule, check_time=None):
    """ Check time is between begin and end
        If check_time is not given then use current UTC time

        Returns true if current time is between one of the schedule slots i.e.

        True if slotstart <= current_time <= slot_end

        We also handle the case where a slot straddles midnight.

    """
    in_sched = False
    for time_slot in schedule:
        begin_time = datetime.time(int(time_slot[0].split(":")[0]),
                                   int(time_slot[0].split(":")[1]))

        end_time = datetime.time(int(time_slot[1].split(":")[0]),
                                 int(time_slot[1].split(":")[1]))

        # If check time is not given, default to current London time.
        check_time = check_time or local_time()
        check_time = check_time.time()
        if begin_time < end_time:
            if begin_time <= check_time <= end_time:
                in_sched = True

        else:
            # Else checktime is crossing midnight
            if check_time >= begin_time or check_time <= end_time:
                in_sched = True

    print(schedule, check_time, in_sched)
    return in_sched


def tests():
    """ Run a few tests """

    lond = 'Europe/London'
    rome = 'Europe/Rome'

    # System time is UTC so we convert our UCT times to local
    # before comparing to the local schedule.
    test_list = [
        # Before DST
        {'dt': (2021, 1, 1, 5, 59), 'tz': lond, 'result': False},
        {'dt': (2021, 1, 1, 6, 0), 'tz': lond, 'result': True},
        {'dt': (2021, 1, 1, 8, 0), 'tz': lond, 'result': True},
        {'dt': (2021, 1, 1, 8, 1), 'tz': lond, 'result': False},

        # During DST
        {'dt': (2021, 6, 1, 4, 59), 'tz': lond, 'result': False},
        {'dt': (2021, 6, 1, 5, 0), 'tz': lond, 'result': True},
        {'dt': (2021, 6, 1, 7, 0), 'tz': lond, 'result': True},
        {'dt': (2021, 6, 1, 7, 1), 'tz': lond, 'result': False},

        # Rome before DST
        {'dt': (2021, 1, 1, 4, 59), 'tz': rome, 'result': False},
        {'dt': (2021, 1, 1, 5, 0), 'tz': rome, 'result': True},
        {'dt': (2021, 1, 1, 7, 0), 'tz': rome, 'result': True},
        {'dt': (2021, 1, 1, 7, 1), 'tz': rome, 'result': False},

        # Rome during DST
        {'dt': (2021, 6, 1, 3, 59), 'tz': rome, 'result': False},
        {'dt': (2021, 6, 1, 4, 0), 'tz': rome, 'result': True},
        {'dt': (2021, 6, 1, 6, 0), 'tz': rome, 'result': True},
        {'dt': (2021, 6, 1, 7, 1), 'tz': rome, 'result': False},
        ]

    sched = TRAIN_DELAY_INDICATION_SCHEDULE
    for test in test_list:
        dt = datetime.datetime(*test['dt'])
        dt = local_time(dt, timezone=test['tz'])
        assert schedule_check(sched, dt) == test['result']

    print(local_time())
    schedule_check(sched)

    print('All done.  All tests passed')


if __name__ == "__main__":
    tests()
