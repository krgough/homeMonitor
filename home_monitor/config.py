'''
Created on 21 Aug 2016

@author: keith
'''
# USERNAME = username-here
# PASSWORD = password-here
# URL = 'https://api-prod.bgchprod.info'

BELL_SOUND = None
BELL_BUTTON_ID = None

INDICATOR_BULB = "Sitt Colour"
TRAIN_DELAY_INDICATION_SCHEDULE = [("06:00", "08:00")]
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

BUTTON_NODE_ID = "7967"   # Black Button
FREEZER_TEMP_ID = "C23A"  # Freezer temperature sensor
FREEZER_TEMP_THOLD = -10  # Freezer temperature alert threshold

SITT_GROUP = ['Sitt Front', 'Sitt Rear', 'Sitt Colour']

DEVS = {
    'Sitt Colour': {'eui': '00158D00012E2189', 'ep': '01'},
    'Sitt Front': {'eui': '00158D00012E2CF1', 'ep': '01'},
    'Sitt Rear': {'eui': '001E5E09021AEBD6', 'ep': '09'},
    'Stair Plug': {'eui': '001E5E09020F2F53', 'ep': '09'},
    'Bed LEDs': {'eui': '001E5E0902171636', 'ep': '09'},
    'Garage Plug': {'eui': '001E5E09020DA01E', 'ep': '09'},
    'Temperature Sensor': {'eui': '', 'ep': '06'}
}


def get_dev(dev_name):
    """ Get the wanted device from DEVS and return a dict
        add the name of the device to the dict.
    """
    dev = DEVS.get(dev_name)
    dev['name'] = dev_name
    return dev
