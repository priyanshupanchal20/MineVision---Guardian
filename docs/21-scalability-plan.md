# Scalability plan for NMDC open-cast mines

## What the prototype proves

Multi-sensor operator cues, fog-aware weighting, control-room telemetry, and a V2V *concept* on a table-scale dumper.

## What a pit-scale deployment needs

| Layer | Prototype | NMDC-scale |
|---|---|---|
| Ranging | 12 m TFMini-S + HC-SR04 | Automotive LiDAR 80–200 m + 77 GHz radar + OEM ultrasonic |
| Positioning | NEO-6M | RTK GNSS + IMU + mine map matching |
| Compute | Pi 3 + ESP32 | IP67 edge IPC (NVIDIA Jetson Orin / Intel industrial) per vehicle + PLC interlock |
| Radio | Wi-Fi / ESP-NOW | Private 5G or LTE in pit + LoRaWAN for low-rate heartbeat |
| Cloud | SQLite on Pi | Redundant control-room cluster, historian, dispatch integration |
| Safety integrity | Best-effort MCU | SIL-oriented process: independent E-stop, no drive-by-wire from this stack until certified |
| Fleet | 2 IDs | 50–200 HEMM, geofencing, haul-road occupancy |
| Environment | BME280 + LDR | Visibility meters (forward-scatter), weather stations on ridgelines |
| Human factors | Browser HUD | Cab-rated display, CAN/J1939 speed limit request to OEM |

## Rollout

1. **Pilot (1–2 dumpers, one haul road)** — data only, no actuator. Compare alerts vs. incident logs for 60 days.
2. **Advisory** — cab display + control room, still no brake command.
3. **Interlock study** with OEM — crawl/stop as *request* on CAN, always overridable, independent watchdog.
4. **Fleet** — standard fitment, training, maintenance spares.

## Cost consciousness

Do not put a 200 m LiDAR on every light vehicle. Fit long-range perception on dumpers and shovels; give light vehicles RTK + V2X receive + beacon. Reuse NMDC existing dispatch radios where possible.

## Operations

- Fog mode should also notify dispatch to **reduce authorised speed** on that bench, not only the one cab.
- Alerts must be rate-limited or operators will ignore them (alarm fatigue).
- Night shift calibration of thermal thresholds vs. ambient.
