#! /usr/bin/env bash

set -e

# Setup the python environment
echo "Creating python venv..."
python3 -m venv venv
echo "Activating venv..."
. ./venv/bin/activate
echo "Installing dependencies from requirements.txt"
python3 -m pip install -r requirements.txt
