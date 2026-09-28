# Installation instructions

## A. Windows laptop (simulation + dashboard) — do this first

Requires Python 3.10+.

```powershell
cd "C:\Users\panch\Desktop\MineTruck Project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r raspberry_pi\requirements.txt
python raspberry_pi\run.py
```

Browser: http://127.0.0.1:8000

If PowerShell blocks venv: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Unit tests:

```powershell
pytest raspberry_pi/tests -q
```

## B. Raspberry Pi 3 (live edge)

Raspberry Pi OS Lite 32-bit is lighter on 1 GB RAM; Desktop is OK if you close Chromium on the Pi and view the dashboard from a laptop.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip i2c-tools libatlas-base-dev libopenjp2-7 libcamera-dev
cd ~/MineTruck\ Project   # or copy this repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r raspberry_pi/requirements.txt
sudo raspi-config   # enable I2C
sudo i2cdetect -y 1 # expect 0x33 for MLX90640
export MINEVISION_MODE=live
python raspberry_pi/run.py
```

Create a systemd unit from `scripts/minevision.service` for boot start.

USB webcam: plug in, `ls /dev/video0`.

## C. ESP32-S3 firmware (Arduino IDE)

1. Boards Manager: `esp32` by Espressif, **3.x**.
2. Board: **ESP32S3 Dev Module**.
3. Flash Size: **16 MB**. PSRAM: **OPI PSRAM**. USB CDC on Boot: Enabled if you use native USB.
4. Libraries: `ArduinoJson`, `Adafruit BME280 Library`, `Adafruit Unified Sensor`, `Adafruit MPU6050`, `TinyGPSPlus`, `U8g2`.
5. Copy `firmware/include/secrets.h.example` → `firmware/include/secrets.h`.
6. Open `firmware/tests/01_tfmini_lidar/` first, then later `firmware/vehicle_hub/vehicle_hub.ino`.

## D. ESP32-S3 firmware (PlatformIO)

```bash
cd firmware
pio run -t upload
pio device monitor
```

`platformio.ini` is already set for N16R8 octal PSRAM.

## E. Network (any Wi‑Fi — no fixed Pi IP)

Laptop, Pi, and ESP32 must share **one** Wi‑Fi (home, college, or phone hotspot). Guest networks with client isolation block the dashboard.

**One-time on the Pi**

```bash
cd ~/MineTruck/MineTruck\ Project
sudo bash raspberry_pi/scripts/setup-dashboard-autostart.sh
```

That enables Avahi (`minevision.local`), `pigpiod`, and boots the dashboard on every power-up.

**Change Wi‑Fi later** (HDMI keyboard or SSH over Ethernet):

```bash
sudo bash raspberry_pi/scripts/join-wifi.sh "NetworkName" "password"
```

**Laptop:** double-click `open-dashboard.bat` — it finds `http://minevision.local:8000` on the current network.

**ESP32 `secrets.h`:** keep `GATEWAY_HOST "minevision.local"` and list each venue SSID as `WIFI_SSID` / `WIFI_SSID_2` / `WIFI_SSID_3`.

## F. Common install failures

| Symptom | Fix |
|---|---|
| `pip` numpy fails on Pi | `sudo apt install python3-numpy` then pip with `--no-deps` for opencv-headless if needed |
| OpenCV too heavy | `opencv-python-headless` is already pinned; do not install full `opencv-python` |
| I2C empty | `dtparam=i2c_arm=on` in `/boot/config.txt`, reboot |
| ESP32 not found | USB-UART cable data-capable; hold BOOT, tap RST for download |
| GPS no fix | Outdoor sky, wait 15 min cold start |
