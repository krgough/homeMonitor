# homeMonitor

Uses ZigBee USB devices running AT command firmware to monitor and control ZigBee devices in the home.   We have a speaker attached to the rPi audio port so that we can use a text to speech to read out train delay and other information.

We have a second rPi close the hot water cylinder that monitors temperature sensors on the cylinder.  We then make an approximation of the 45'C level in the tank as a percentage.  We have a UDP listener running on the rPi that will send the hot-water level on receipt of the command "uwl=?" (usable hot water level)

```
                      HIVE_ZIGBEE_USB < zigbee > HIVE DEVICES (Bulbs etc)
                     /
                    /
HOME_MONITOR_RPI - - - BUTTON-ZIGBEE_USB < zigbee > Button, Garage Plug (to act as range extended), Freezer Temp Sensor
                    \
                     \
                      < udp command/response > HOT_WATER_RPI <> Temperature sensors on cylinder
```

On the home monitoring system we have implemented the following functions that are triggered by presses of the ZigBee button:

*   shortPress on ZigBee button - Toggle sitting room lights on/off
*   doublePress on ZigBee button - Announce current delays status.
*   longPress on ZigBee button - Announce the hot water level.

```
USAGE: home_monitor.py [-h] [-l] [-b] [-g] [-z] -t to_station -f from_station

Use these command line options:

-h                      Print this help
-l                      Show delays on HH360 LED indicator board
-b                      Show delays on hive colour bulb
                        See apiConfig.py for login details

-g                      Monitor gpio button presses
                        Make announcement if button presssed)

-z                      Announce delays on zigbee button press
-t 'to' stationId       CRS code for station e.g. wat for Waterloo
-f 'from' stationId     CRS code for station
```

### ZigBee USB Setup:

We have 2 ZigBee USB devices attached to the rpi:

*   One paired to the Hive network to allow us to send and receive commands on that network
*   One setup as a co-ordinator for a separate network.  We use this to monitor a button (for turning lights on/off) and a temperature sensor (contact sensor in freezer).

We use our own network for the button and the temperature sensor to prevent the Hive hub code overwriting the attributes that we have set on those devices.  Note also the the ZigBee button uses an NXP device and SW stack.  This device does not always work correctly when used in a network of SiLabs devices and can drop offline (particularly if routing through another device).  Keeping the button on a separate small network seems to keep it online.

### Configuration

Config.py contains all the configuration parameters.

We have several module that can be used as follows:

*   home\_monitor.py - The main program.  Start this using the startWinToWatTrainMonotor.sh from CRON
*   gpio\_monitor.py - Monitors a physical switch connection on a gpio line on the rPi.  Can use this to trigger reports.
*   startGpioMonitor.sh - script to check if gpio\_monitor.py is running (Use this from CRON)
*   button\_listener.py - Listens for incoming commands or attribute reports on the private ZigBee network.
*   led\_pattern\_generator.py - Generates nice patterns on a Hive Sense LED indicator ring.  LED ring needs to be attached via UART to the rPi.
*   train\_times.py - Use the Huxley API (wraps the Network Rail soap API with a rest API) to get train data.
*   test\_delays.yaml.old - Test data in a yaml file.  Rename to remove 'old' to use it.
*   zigbee\_methods.py - Module that handles all the interactions with ZigBee devices on the Hive network.

### Hot Water RPI Setup

```
# Clone the telemetry repo and then setup CRON to read the temperature values and run the UDP listener (server).
git clone https://github.com/krgough/telemetryModule.git

# CRONTAB Entries

# KG: Hot water cylinder data logging
*
/10 * * * * /home/pi/repositories/telemetry/cylinder_read.py -s > /dev/null 2>&1

# KG: Hot water level UDP server
* * * * * /home/pi/repositories/telemetry/create_hot_water_udp_server.sh > /dev/null 2>&1
```

d
