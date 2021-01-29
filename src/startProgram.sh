#!/bin/bash

APP_NAME=$1

# Use basename to get program name with no path or arguments
# pgrep used later to find this requires no path
appBaseName=$(basename $APP_NAME)

if [ -z APP_NAME ]; then
  echo
  echo "Usage: $0 program"
  echo "<program> is the path to the program you want to run"
  echo "This script checks if it's running and if not the starts it"
  echo
fi

# Command to check if the app is running
cmd="/usr/bin/pgrep -l $appBaseName"
eval "$cmd"

if [ $? == 0 ]; then
  echo "$APP_NAME is already running"
else
  echo "Starting $APP_NAME..."
  $APP_NAME &
  eval "$cmd" 
fi