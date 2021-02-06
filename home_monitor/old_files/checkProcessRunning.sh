#!/bin/bash

# Check if a python app is runnning
P_NAME='/home/pi/repositories/logger/logAttributes.py'
PS_FILE='/tmp/ps.txt'

# Global var for the ps result check
PS_FOUND=0

function processRunning
# Dump ps -x into a file and grep for
# the wanted process
{
  ps -x > $PS_FILE
  cmd="/bin/grep -w $P_NAME $PS_FILE"
  eval "$cmd"

  if [ $? == 0 ]; then
    PS_FOUND=0
  else
    PS_FOUND=1
  fi
}

processRunning
if [ $PS_FOUND == 0 ]; then
  echo "$P_NAME is already running"
else
  echo "Starting $P_NAME"
  $P_NAME  > /dev/null 2>&1 &
  processRunning
fi