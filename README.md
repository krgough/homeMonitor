# homeMonitor

homeMonitor is setup to do the following:

1. Monitor train delays on a given route and indicate delays with a red alert using a zigbee bulb in the house
2. Freezer Alarm:
    - Indicate an unexpected defrost (Blue alert) using a zigbee bulb.
    - Sensor offline (Green alert) using a zigbee buld
    - Turn off freezer alerts if a LONG_PRESS is received.
3. Security Alarm
    - Automatically arm/disarm the Hive ZigBee alarm accoring to a given schedule
    - Toggle the alarm elabled/disabled if a LONG_PRESS in received.
4. Toggle a set of lights on/off if a zigbee button is pressed (SHORT_PRESS)
5. Read out the current train delays if a zigbee button is pressed (DOUBLE_PRESS)
6. Read out the hot water level and freezer temperature is a zigbee button is pressed (DOUBLE_PRESS)

Uses two zigbee dongles, one to send commands on the Hive ZB network and one too send commands to our additional "home" zigbee network. We have a speaker attached to the rPi audio port so that we can use a text to speech to read out train delay and other information.

We have a second rPi close the hot water cylinder that monitors temperature sensors on the cylinder. We then make an approximation of the 45'C level in the tank as a percentage. We have a UDP listener running on the rPi that will send the hot-water level on receipt of the command "uwl=?" (usable hot water level)

```bash
                       HIVE_ZIGBEE_USB < zigbee > HIVE DEVICES (Bulbs etc)
                     /
                    /
HOME_MONITOR_RPI - - - ZIGBEE_USB < zigbee > Button, Freezer Temp Sensor, Siren
                    \
                     \
                       HOT_WATER_UDP_CLIENT < udp command/response > RPI_HOT_WATER_UDP_SERVER <> Temperature sensors on cylinder
```


```bash
USAGE: home_monitor.py [-h] [-l] [-b] [-g] [-z] -t to_station -f from_station

Use these command line options:

-h                      Print this help
-l                      Show delays on HH360 LED indicator board
-b                      Show delays on hive colour bulb
                        See apiConfig.py for login details

-g                      Monitor gpio button presses
                        Make announcement if button presssed)

-z                      Announce delays on zigbee button press
-t 'to' stationId       CRS code for station e.g. wat for Waterloo
-f 'from' stationId     CRS code for station
```

## Hive API Access Setup

(Not currently being used, but retained in case we ever want to use it)

* Create a registered device using `hive.py`.  The device credentials are saved to `home_monitor/.device_creds.json`.  If you already have a registered device and have saved the credentials you can create this file manually
* Tokens are requested from Hive login api using these credentials.  The tokens are not saved to a file as these are ephemeral and can be requested as required.

## ZigBee USB Setup

We have 2 ZigBee USB devices attached to the rpi:

* One paired to the Hive network to allow us to send and receive commands on that network
* One setup as a co-ordinator for a separate network. We use this to monitor a button (for turning lights on/off)

We use our own network for the button because the ZigBee button uses an NXP device and SW stack. This device does not always work correctly when used in a network of SiLabs devices and can drop offline (particularly if routing through another device). Keeping the button on a separate small network seems to keep it online.

To setup the Hive ZB Dongle:

* Pair a USB stick to the Hive network but set the device type first to be 0x01 rather than 0x07 (SREG 49 should be set to 0x0001). This stops it appearing as a second hub (co-ordinator).  Note that this USB stick becomes our "HIVE" connected USB and will be plugged into the rPi.  If you need to reset the temp sensor then log into the rPi and connect to this USB using `screen` or `picocom` and follow the instructions below.
* `SetS61=0000` In order to prevent the TG stick acting as as IAS CIA (Control and Indicating Equipment) on endpoint 0x02.  This setting prevents auto enrollment for devices.


## Pairing Devices to the Home Zigbee network

```bash
source venv/bin/activate
python3 -m home_monitor.pair_device -h

usage: pair_device.py [-h] -d {siren,wds} [-n node_id] -p port [-b baud]

Device Pairing Tool

To setup the device:
- Put the device in pairing mode and run the script.
- Script sets the required cluster bindings and attribute reporting configurations

optional arguments:
  -h, --help            show this help message and exit
  -d {siren,wds}, --device {siren,wds}
                        Device type to pair.
  -n node_id            Device Node Id (DUT). If not provided we open the network and wait for a device to join
  -p port               Serial port e.g. /dev/tty.xxxx
  -b baud               Baud rate (default is 115200)

```

```bash
# Some example AT commands used to send bindings and attribute reporting configirations

# Set Bindings on the poll control cluster and the temperature reporting cluster
at+bind:{sensor_node_id},3,{sensor_eui},06,0020,{usb_eui},01
at+bind:{sensor_node_id},3,{sensor_eui},06,0402,{usb_eui},01

# Set reporting config for the measured temperature. 0x012C = 5*60 = 5mins
at+cfgrpt:{sensor_node_id},06,0,0402,0,0000,29,0001,012C,0001
```

## Configuration Files

* `home_monitor/Config.py` Edit this file as required with your configuration parameters for homeMonitor. Schedules, device details etc.
* If you are using Hive API call then create a file called `.env` With he required env vars sown below.

Contents of `.env`

```bash
# National Rail Token for API access
NATIONAL_RAIL_TOKEN='you-token-here'

# Hive Credentials 
HIVE_USERNAME='your-hive-username'
HIVE_PASSWORD='your-hive-password'
```

## Device States and Events

Devices are items like sensors, bulbs, sirens, buttons.  They have persistent state attributes (e.g battery voltage, temperature, online_state) and they can generate events such as button_presses, open or close events.  Any event that we want to treat as a trigger for some action can be classed as an event.

We also have state machines for e.g. the Freezer Alarm and the Security Alarm.  The FSMs manage the state of those functions and they generate Events where necessary to trigger an action.  FSM state variables are modified by Events.

## Module Descriptions

We have several module that can be used as follows:

* `home\_monitor.py` - The main program. Start this using the startWinToWatTrainMonotor.sh from CRON
* `gpio\_monitor.py` - Monitors a physical switch connection on a gpio line on the rPi. Can use this to trigger reports.
* `startGpioMonitor.sh` - script to check if gpio\_monitor.py is running (Use this from CRON)
* `button\_listener.py` - Listens for incoming commands or attribute reports on the private ZigBee network.
* `led\_pattern\_generator.py` - Generates nice patterns on a Hive Sense LED indicator ring. LED ring needs to be attached via UART to the rPi.
* `train\_times.py` - Use the Huxley API (wraps the Network Rail soap API with a rest API) to get train data.
* `test\_delays.yaml.old` - Test data in a yaml file. Rename to remove 'old' to use it.
* `zigbee\_methods.py` - Module that handles all the interactions with ZigBee devices on the Hive network.

## Text to Speach

### gTTs (Gooogle text to speach) and `mpg123`

`gTTs` is installed with pip and is rlisted in `requirements.txt`
`mpg123` can be installed with `sudo apt install mpg123`

### Pico2 wave - (Used in oder code versions) 

We use `pico2wave` which is part of `libttspico-utils` to generate a .wav file fomr text, we then use `aplay` to play the wav file through an attached speaker.

`pico2wave` Is not available in the raspian apt so we edit `sources.list` tempraraly to include
the necessary library

```bash
sudo nano /etc/apt/sources.list
```

Add the following:

```bash
# KG - Uncomment this to allow us to install pico2wave. Run apt update then sudo apt install libttspico-utils  
#deb [arch=armhf, trusted=yes] http://deb.debian.org/debian bookworm main contrib non-free
```

Then run the following:

```bash
sudo apt update
sudo apt install libttspico-utils
```

### Hot Water RPI Setup

```bash
# Clone the telemetry repo and then setup CRON to read the temperature values and run the UDP listener (server).
git clone https://github.com/krgough/telemetryModule.git

# Setup 1-Wire
sudo raspi-config
interfaces, enable w1

# CRONTAB Entries

# KG: Hot water cylinder data logging
*/10 * * * * /home/pi/repositories/telemetryModule/src/cylinder_read.py -s > /dev/null 2>&1

# KG: Hot water level UDP server
* * * * * /home/pi/repositories/telemetryModule/src/create_hot_water_udp_server.sh > /dev/null 2>&1
```
