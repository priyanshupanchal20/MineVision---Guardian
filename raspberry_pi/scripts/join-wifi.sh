#!/bin/bash
# Join any Wi-Fi from the Pi (HDMI/SSH). Dashboard stays at http://minevision.local:8000
# Usage:
#   sudo bash join-wifi.sh "NetworkName" "password"
#   sudo bash join-wifi.sh "OpenCafe" ""
set -euo pipefail

SSID="${1:-}"
PASS="${2:-}"

if [[ -z "$SSID" ]]; then
  echo "Usage: sudo bash $0 \"WiFi name\" \"password\""
  echo
  echo "Scan:"
  if command -v nmcli >/dev/null 2>&1; then
    nmcli -t -f SSID,SIGNAL,SECURITY device wifi list | head -n 30
  elif command -v iwlist >/dev/null 2>&1; then
    iwlist wlan0 scan 2>/dev/null | grep -E "ESSID|Quality" | head -n 40 || true
  fi
  exit 1
fi

IFACE="wlan0"
if command -v nmcli >/dev/null 2>&1; then
  IFACE="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi"{print $1; exit}')"
  IFACE="${IFACE:-wlan0}"
fi

echo "Joining Wi-Fi: $SSID  (iface $IFACE)"

if command -v nmcli >/dev/null 2>&1; then
  nmcli radio wifi on || true
  nmcli device set "$IFACE" managed yes || true
  if [[ -n "$PASS" ]]; then
    nmcli device wifi connect "$SSID" password "$PASS" ifname "$IFACE" || \
      nmcli connection up id "$SSID" || \
      nmcli connection add type wifi ifname "$IFACE" con-name "$SSID" ssid "$SSID" \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" && nmcli connection up "$SSID"
  else
    nmcli device wifi connect "$SSID" ifname "$IFACE" || \
      nmcli connection add type wifi ifname "$IFACE" con-name "$SSID" ssid "$SSID" && \
      nmcli connection up "$SSID"
  fi
elif [[ -f /etc/wpa_supplicant/wpa_supplicant.conf ]]; then
  CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
  if [[ -n "$PASS" ]]; then
    BLOCK="$(wpa_passphrase "$SSID" "$PASS")"
  else
    BLOCK=$(printf 'network={\n\tssid="%s"\n\tkey_mgmt=NONE\n}\n' "$SSID")
  fi
  # Drop an older block for the same SSID, then append.
  python3 - "$CONF" "$SSID" <<'PY' || true
import re, sys
path, ssid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="ignore").read()
pat = re.compile(r'network=\{(?:[^{}]|\{[^{}]*\})*ssid\s*=\s*"%s"(?:[^{}]|\{[^{}]*\})*\}' % re.escape(ssid), re.S)
open(path, "w", encoding="utf-8").write(pat.sub("", text))
PY
  printf '\n%s\n' "$BLOCK" | sudo tee -a "$CONF" >/dev/null
  if command -v wpa_cli >/dev/null 2>&1; then
    wpa_cli -i "$IFACE" reconfigure || true
  fi
  if systemctl list-unit-files | grep -q dhcpcd; then
    systemctl restart dhcpcd || true
  fi
  if systemctl list-unit-files | grep -q networking; then
    systemctl restart networking || true
  fi
else
  echo "No NetworkManager (nmcli) and no wpa_supplicant.conf — install NetworkManager:"
  echo "  sudo apt install -y network-manager"
  exit 1
fi

echo "Waiting for an IPv4 address..."
for _ in $(seq 1 20); do
  IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -n "$IP" && "$IP" != "127.0.0.1" ]]; then
    echo "Connected. IP: $IP"
    echo "Dashboard: http://minevision.local:8000"
    echo "           http://$IP:8000"
    exit 0
  fi
  sleep 1
done

echo "No IP yet. Check password / 2.4 GHz-only / guest AP isolation."
exit 2
