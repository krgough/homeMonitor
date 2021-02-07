# homeMonitor

Uses ZigBee USB running AT command App to monitor and control ZigBee devices in the home.   We have a speaker attached to the rPi audio port so that we can use a text to speach

We have implemented the following functions:

*   shortPress on ZigBee button - Toggle sitting room lights on/off
*   doublePress on ZigBee button - Read out the current delays status (we 

### ZigBee USB Setup:

We have 2 ZigBee USB devices attached to the rpi:

*   One paired to the Hive network to allow us to send and receive commands on that network
*   One setup as a co-ordinator for a separate network.  We use this to monitor a button (for turning lights on/off) and a temperature sensor (contact sensor in freezer).

We use our own network for the button and the temperature sensor to prevent the Hive hub code overwriting the attributes that we have set on those devices.  Note also the the ZigBee button uses an NXP device and SW stack.  This device does not always work correctly when used in a network of SiLabs devices and can drop offline (particularly if routing through another device).  Keeping the button on a separate small network seems to keep it online.

### Configuration

Config.py contains all the configuration.

We have several module that can be used as follows:

*   home\_monitor.py - The main program.  Start this using the startWinToWatTrainMonotor.sh from CRON
*   gpio\_monitor.py - Monitors a physical switch connection on a gpio line on the rPi.  Can use this to trigger reports.
*   startGpioMonitor.sh - script to check if gpio\_monitor.py is running and if not then start it (Use this from CRON to keep the monitor running)
*   button\_listener.py - Listens for incoming commands or attribute reports on the private ZigBee network.
*   led\_pattern\_generator.py - Generates nice patterns on a Hive Sense LED indicator ring.  LED ring needs to be attached via UART to the rPi.
*   train\_times.py - Use the Huxley API (wraps the Network Rail soap API with a rest API) to get train data.
*   test\_delays.yaml.old - Test data in a yaml file.  Rename to remove 'old' to use it.
*   zigbee\_methods.py - Module that handles all the interactions with ZigBee devices on the Hive network.
