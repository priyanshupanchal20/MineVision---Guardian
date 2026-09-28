#!/bin/bash
# One-time Pi setup: join any Wi-Fi later, keep dashboard on http://minevision.local:8000
# Run on the Pi:
#   cd ~/MineTruck/MineTruck\ Project
#   sudo bash raspberry_pi/scripts/setup-dashboard-autostart.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
USER_NAME="${SUDO_USER:-${USER:-darshan}}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
HOME_DIR="${HOME_DIR:-/home/$USER_NAME}"
VENV="$ROOT/.venv/bin/python"
UNIT="/etc/systemd/system/minevision.service"

echo "Project: $ROOT"
echo "User:    $USER_NAME"

if [[ ! -x "$VENV" ]]; then
  echo "Missing venv at $VENV"
  echo "Create it first: python3 -m venv .venv && .venv/bin/pip install -r raspberry_pi/requirements.txt"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  avahi-daemon avahi-utils \
  network-manager \
  pigpio python3-pigpio \
  i2c-tools \
  gcc \
  libopenjp2-7

systemctl enable --now NetworkManager || true
systemctl enable --now avahi-daemon
systemctl enable --now pigpiod || true

# Prefer NetworkManager for wlan (Bookworm-friendly). Ignore failures on older images.
rfkill unblock wifi || true
nmcli radio wifi on || true

# Stable LAN name used by laptop open-dashboard.bat and ESP32 GATEWAY_HOST.
hostnamectl set-hostname darshan || true
if [[ -f /etc/hosts ]]; then
  if ! grep -q "minevision" /etc/hosts; then
    echo "127.0.1.1  darshan minevision" >> /etc/hosts
  fi
fi

# Path has a space ("MineTruck Project") — systemd ExecStart breaks on spaces.
ln -sfn "$ROOT" "/home/$USER_NAME/minevision"
ROOT_LINK="/home/$USER_NAME/minevision"
VENV_LINK="$ROOT_LINK/.venv/bin/python"

cat > "$UNIT" <<EOF
[Unit]
Description=MineVision Guardian command dashboard
Wants=network-online.target avahi-daemon.service pigpiod.service
After=network-online.target avahi-daemon.service pigpiod.service

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$ROOT_LINK
ExecStart=$VENV_LINK $ROOT_LINK/raspberry_pi/run.py
Restart=always
RestartSec=3
Environment=MINEVISION_MODE=live
Environment=MINEVISION_TFT=1
Environment=MINEVISION_OV7670=1
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable minevision.service
systemctl restart minevision.service

chmod +x "$ROOT/raspberry_pi/scripts/join-wifi.sh" || true
chmod +x "$ROOT/raspberry_pi/scripts/enable_lan_name.sh" || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "=== MineVision ready on any Wi-Fi ==="
echo "Dashboard (same network as laptop):"
echo "  http://minevision.local:8000"
echo "  http://darshan.local:8000"
[[ -n "$IP" ]] && echo "  http://$IP:8000"
echo
echo "Change Wi-Fi later (HDMI or SSH):"
echo "  sudo bash $ROOT/raspberry_pi/scripts/join-wifi.sh \"NewNetwork\" \"password\""
echo
echo "Laptop: double-click open-dashboard.bat"
echo "ESP32 secrets.h: GATEWAY_HOST \"minevision.local\" + add each SSID with WIFI_SSID / WIFI_SSID_2"
systemctl --no-pager --full status minevision.service | head -n 20 || true
