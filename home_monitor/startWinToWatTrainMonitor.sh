#!/bin/bash

# Change to this directory so we can find .tokens.json
cd "$(dirname "$0")"

# Add path to pyenv shims and bin so root can run python
export PATH=/home/pi/.pyenv/shims:/home/pi/.pyenv/bin:"$PATH"

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
  /home/pi/repositories/homeMonitor/home_monitor/home_monitor.py -f $FROM_STATION -t $TO_STATION -zba &
  eval "$cmd"
fi
