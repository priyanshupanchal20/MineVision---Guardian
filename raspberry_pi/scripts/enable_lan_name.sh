#!/bin/bash
# Stable dashboard name on any DHCP Wi-Fi: http://minevision.local:8000
set -e
sudo apt-get update
sudo apt-get install -y avahi-daemon avahi-utils
sudo systemctl enable --now avahi-daemon
echo "mDNS ready. After the hub starts, open:"
echo "  http://minevision.local:8000"
echo "  http://$(hostname).local:8000"
hostname -I
