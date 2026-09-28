# Start here — build order

This file is the only sequence you should follow. The PDF forbids jumping into a fully integrated stack before sensors are proven.

## Phase 0 — Read (today)

1. `docs/01-system-architecture.md`
2. `docs/02-hardware-responsibility.md`
3. `docs/04-sensor-connection-plan.md`
4. `docs/05-esp32-pin-mapping.md`
5. `docs/08-development-roadmap.md`

Then run the **software simulation** (`python raspberry_pi/run.py`) so you understand the dashboard judges will see, *before* any soldering.

## Phase 1 — Planning artefacts (done in this repo)

- Block diagram, pin map, power budget, data flow, protocols.

## Phase 2 — One sensor at a time

Flash **only** the matching sketch in `firmware/tests/`. Do not proceed to the next sensor until Serial Monitor shows the expected output in that folder’s README.

Order:

1. LDR (simplest analog)
2. HC-SR04 left, then right
3. BME280
4. TFMini-S LiDAR
5. NEO-6M GPS (outdoors)
6. S3KM1110 mmWave
7. MLX90640 on the Pi
8. OV7670 / USB camera on the Pi

## Phase 3 — ESP32 sensor hub

Flash `firmware/vehicle_hub/` (or PlatformIO `firmware/src/main.cpp`). Confirm JSON on Serial, then HTTP POST to the Pi.

## Phase 4 — Raspberry Pi edge

Point `MINEVISION_MODE=live` at the ESP32. Thermal + camera + fusion + SQLite.

## Phase 5 — Algorithms (already implemented, tune thresholds)

Fog index, risk score, thermal clusters, visibility, collision zones.

## Phase 6 — Safety decision engine

Rule engine + weighted fusion. LEDs/buzzer/OLED on ESP32, HUD on dashboard.

## Phase 7 — Dashboard

FastAPI + WebSocket UI. Judge demo buttons.

## Phase 8 — Integration

ESP32 → Wi-Fi/HTTP → Pi → fusion → dashboard → operator alert. Run `docs/19-testing-methodology.md` then `docs/20-demo-script.md`.

## Config that must stay tunable

Safety distances, fog-mode threshold, fusion weights, vehicle ID, Wi-Fi, and gateway IP live in:

- `firmware/include/config.h`
- `raspberry_pi/minevision/config.py`
