#!/bin/bash

# Change to this directory
cd "$(dirname "$0")"

# Load the environment vars from .profile
# This is required for cron jobs to work
source $HOME/.profile

TO_STATION="wat"
FROM_STATION="win"

# We define this as a command as we will use it more than once
# Could make this a function?
cmd="/bin/ps -ax | /bin/grep \"[h]ome_monitor.py\""
eval "$cmd"

if [ $? == 0 ]; then
  echo "home_monitor.py is already running"
else
  echo "Starting home_monitor.py"
  /home/pi/.pyenv/versions/3.9.7/bin/python3 /home/pi/repositories/homeMonitor/home_monitor/home_monitor.py -f $FROM_STATION -t $TO_STATION -zba &
  eval "$cmd"
fi
