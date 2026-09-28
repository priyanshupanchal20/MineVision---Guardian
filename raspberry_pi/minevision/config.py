"""MineVision Guardian — tunable prototype configuration."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

MODE = os.getenv("MINEVISION_MODE", "sim").lower()  # sim | live
HOST = os.getenv("MINEVISION_HOST", "0.0.0.0")
PORT = int(os.getenv("MINEVISION_PORT", "8000"))
DB_PATH = Path(os.getenv("MINEVISION_DB", DATA_DIR / "minevision.db"))

VEHICLE_ID = os.getenv("MINEVISION_VEHICLE_ID", "DUMPER_01")
PEER_ID = "DUMPER_02"

# Bailadila / Kirandul approximate haul corridor
MAP_CENTER_LAT = 18.7200
MAP_CENTER_LON = 81.2300

# Collision zones (metres) — prototype scale, configurable
SAFE_M = 8.0
WARN_M = 4.0
DANGER_FRONT_M = 1.5  # LiDAR: DANGER + cab buzzer only below this
DANGER_SIDE_M = 1.0   # left/right ultrasonic: DANGER + buzzer only below this
BUZZ_M = DANGER_FRONT_M  # alias kept for older API clients
ZONE_HYSTERESIS_M = 0.3
FOG_ZONE_SCALE = 1.25

# Fog Safety Mode
FOG_ENTER = 70
FOG_EXIT = 60

# LiDAR — match ESP32 TFMini close hand (~3 cm), not 30 cm
LIDAR_MIN_M = 0.03
LIDAR_MAX_M = 12.0
LIDAR_MIN_STRENGTH = 80
LIDAR_HOLD_S = 0.05

# Ultrasonic
US_MIN_M = 0.06
US_MAX_M = 4.5
US_HOLD_S = 0.04

# Heavy camera/thermal work is throttled so /ingest stays under the ESP HTTP timeout
SLOW_SENSORS_S = 0.18
WS_HEATMAP_HZ = 2.0

# Fusion weights
WEIGHTS_CLEAR = {
    "distance": 0.40,
    "environment": 0.15,
    "thermal": 0.15,
    "motion": 0.15,
    "visibility": 0.15,
}
WEIGHTS_FOG = {
    "distance": 0.38,
    "environment": 0.12,
    "thermal": 0.22,
    "motion": 0.22,
    "visibility": 0.06,
}

AGREEMENT_BONUS_FULL = 12
AGREEMENT_BONUS_PARTIAL = 6

# Thermal
THERMAL_ROWS = 24
THERMAL_COLS = 32
THERMAL_ABS_MIN_C = 28.0
THERMAL_RESIDUAL_C = 2.5
THERMAL_MIN_BLOB = 4

# Tick rates
INGEST_HZ = 10.0
WS_HZ = 15.0

FIRMWARE_SCHEMA_VERSION = "1.5.5"

# --- Raspberry Pi 3 J8 (USB on the right, pin 1 = 3V3 by the SD card) ---
# Inner row = odd pins 1,3,5…  Outer row = even pins 2,4,6…
# MLX9064X uses I2C1. Never 5 V (pins 2 / 4).
PI_MLX_VIN_PHYS = 1
PI_MLX_GND_PHYS = 6
PI_MLX_SDA_PHYS = 3  # BCM GPIO2
PI_MLX_SCL_PHYS = 5  # BCM GPIO3
PI_MLX_SDA_BCM = 2
PI_MLX_SCL_BCM = 3
PI_MLX_I2C_BUS = 1
PI_MLX_ADDR = 0x33

# OV7670 DVP — does not share MLX pins 1/3/5/6
PI_OV_VCC_PHYS = 17  # inner 9th, 3V3
PI_OV_GND_PHYS = 9   # inner 5th
PI_OV_SIOD_BCM = 10  # phys 19 inner 10th
PI_OV_SIOC_BCM = 11  # phys 23 inner 12th
PI_OV_XCLK_BCM = 4   # phys 7  inner 4th
PI_OV_PCLK_BCM = 22  # phys 15 inner 8th
PI_OV_VSYNC_BCM = 27 # phys 13 inner 7th
PI_OV_HREF_BCM = 17  # phys 11 inner 6th
PI_OV_RESET_BCM = 24 # phys 18 outer 9th
PI_OV_PWDN_BCM = 23  # phys 16 outer 8th
PI_OV_D_BCM = (5, 6, 13, 19, 26, 16, 20, 21)  # D0..D7 phys 29,31,33,35,37,36,38,40
PI_OV_WIDTH = 320
PI_OV_HEIGHT = 240
# OV7670 on the Pi header is the vehicle camera. USB Canon is optional.
USB_CAM = os.getenv("MINEVISION_USB_CAM", "0").lower() in ("1", "true", "yes")
OV7670_CAM = os.getenv("MINEVISION_OV7670", "1").lower() in ("1", "true", "yes")

# 1.28" 240×240 GC9A01 round TFT — NOT on SPI0. GPIO10/11 are OV7670 SCCB.
# Bit-bang SPI on free header pins. VCC is display-only (onboard LDO).
# Silk left→right: RST CS DC SDA SCL GND VCC.
ST7735 = os.getenv("MINEVISION_TFT", os.getenv("MINEVISION_ST7735", "1")).lower() in (
    "1",
    "true",
    "yes",
)
PI_ST_WIDTH = 240
PI_ST_HEIGHT = 240
PI_ST_SCK_BCM = 18   # phys 12  module SCL
PI_ST_MOSI_BCM = 12  # phys 32  module SDA
PI_ST_CS_BCM = 8     # phys 24  module CS
PI_ST_DC_BCM = 25    # phys 22  module DC
PI_ST_RST_BCM = 7    # phys 26  module RST
PI_ST_MISO_BCM = 9   # phys 21 dummy, leave unconnected
PI_ST_VCC_PHYS = 2   # 5V — display only
PI_ST_GND_PHYS = 14
PI_ST_LED_PHYS = 17  # unused on this 7-pin board (backlight from VCC)
PI_ST_COLSTART = int(os.getenv("MINEVISION_ST7735_COL", "0"))
PI_ST_ROWSTART = int(os.getenv("MINEVISION_ST7735_ROW", "0"))
PI_ST_MADCTL = int(os.getenv("MINEVISION_ST7735_MADCTL", "0x08"), 0)
# pigpio bb_spi_open only accepts 50–500000. Fast path uses mmap GPIO instead.
PI_ST_BAUD = int(os.getenv("MINEVISION_ST7735_BAUD", "500000"))
