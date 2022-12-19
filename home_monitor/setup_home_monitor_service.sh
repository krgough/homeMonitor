# Setup train-d-cator home_monitor service as a systemd service
echo "Setting up home_monitor.service..."
sudo cp home_monitor.service /etc/systemd/system/
sudo systemctl enable home_monitor.service
sudo systemctl start home_monitor.service
sudo systemctl status home_monitor.service

