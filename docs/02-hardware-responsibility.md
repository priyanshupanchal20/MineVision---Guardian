# Hardware responsibility allocation

## Design principle

Give the microcontroller everything that must stay alive in a radio outage. Give the Pi everything that needs RAM, Python, or a display.

## ESP32-S3-WROOM-N16R8 (vehicle sensor controller)

**Resources used:** 240 MHz dual-core LX7, 16 MB flash, 8 MB octal PSRAM, Wi-Fi 4, BLE, 3 hardware UARTs, native USB CDC on the second Type-C port.

**Owns:**

- TFMini-S UART LiDAR
- HC-SR04 left and right
- BME280 I2C
- LM393 LDR analog
- NEO-6M UART GPS
- S3KM1110 UART mmWave
- Green / yellow / red / fog LEDs
- 1.3" I2C OLED cab HUD (zone + speed advice)
- Piezo buzzer (continuous only when closest obstacle < 1.5 m)
- Wi-Fi station → Pi ingest API
- ESP-NOW V2V beacon
- Local copies of danger / warning / safe thresholds

**Does not own:** full thermal matrix, camera frames, SQLite, Chart.js, Leaflet.

**On-device decision (must exist in firmware, not only on Pi):**

```
IF LiDAR < 1.5 m OR left US < 1.0 m OR right US < 1.0 m:
    buzzer ON
    OLED line 2 = STOP VEHICLE
    send buzzer_state=continuous (best-effort)
Above those ranges that channel is not DANGER on the dashboard.
```

## Raspberry Pi 3 Model B, 1 GB RAM

**Owns:**

- MLX90640 on I2C1 (`0x33`)
- OV7670 (GPIO DVP, optional) **or** USB webcam (recommended for demo)
- HTTP ingest + WebSocket fan-out
- Weighted fusion, Fog Risk Index, Mine Safety Risk Score
- Thermal segmentation (hot clusters, not person-ID)
- Visibility: contrast, Laplacian blur, edge density
- Optional IsolationForest anomaly model (tiny, sklearn)
- SQLite logging
- Command dashboard
- Simulated DUMPER_02
- Speed recommendation string (NORMAL / REDUCE / CRAWL / STOP)

**Memory rules (non-negotiable on 1 GB):**

- No full YOLOv5/v8/v11 weights.
- Thermal at 2–8 Hz, not 64 Hz.
- Camera frames downscaled to ≤ 320×240 before metrics.
- Single uvicorn worker.
- SQLite WAL, periodic purge of raw frames.

## Shared / human

| Item | Owner |
|---|---|
| 5 V 3 A power rail | Common buck / power bank |
| Mechanical mount on RC / miniature dumper | Builder |
| Fog simulation (humidifier / cloth / software inject) | Demo operator |
| Threshold tuning after first outdoor test | Builder, via `config.h` / `config.py` |

## If the Pi is unplugged

The dumper still has:

- Distance zones
- Side ultrasonics
- Radar presence bit
- Environment raw values
- Local acoustic/visual alarm
- 1.3" OLED cab text (STOP / CRAWL / TILT)

The control room goes dark. That is acceptable for a prototype and **not** acceptable in production (needs redundant edge nodes).
