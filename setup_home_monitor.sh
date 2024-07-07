#! /usr/bin/env bash

set -e

# Checking for pico2wave
if ! $(pico2wave -w "/tmp/junk.wav" "test"); then
  echo -e "ERROR: pico2wave not installed.  Stopping setup\n"
  exit 1
else
  echo -e "pico2wave command found"
fi

# Setup the python environment
echo "Creating python venv..."
python3 -m venv venv
echo "Activating venv..."
. ./venv/bin/activate
echo "Installing dependencies from requirements.txt"
python3 -m pip install -q -r requirements.txt

# Create a systemd service file for the secure tunnel manager with correct path names
echo "Creating home_monitor.servce file"
path=$(pwd)
cmd="$path/venv/bin/python3 -m home_monitor.home_monitor -f win -t wat -zba"
cat > "home_monitor.service"<< EOF
[Unit]
Description=Train-d-cator home_monitor service
StartLimitIntervalSec=0
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
Restart=always
RestartSec=10s
WorkingDirectory=$path
ExecStart=$cmd

[Install]
WantedBy=multi-user.target
EOF

# Setup home_monitor so it starts as a systemd service
echo "Setting up home_monitor service..."
sudo mv home_monitor.service /etc/systemd/system/
sudo systemctl enable home_monitor.service
sudo systemctl start home_monitor.service
sudo systemctl status home_monitor.service
