#!/bin/bash

# We define this as a command as we will use it more than once
# Could make this a function?
cmd="/bin/ps -ax | /bin/grep \"[g]pio_monitor.py\""
eval "$cmd"

if [ $? == 0 ]; then
  echo "gpio_monitor is already running"
else
  echo "Starting Train Monitor"
  /usr/bin/python3 /home/pi/repositories/train-monitor/gpio_monitor.py > /dev/null 2>&1 &
  eval "$cmd"
fi
