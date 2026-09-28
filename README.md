# MineVision Guardian

**Intelligent Fog Navigation and Collision Prevention System**  
Smart India Hackathon / NMDC Problem Statement **26007**  
*Safe and Efficient Operation of Mine Vehicles in Fog and Low-Visibility Conditions in Open Cast Iron Ore Mines*

MineVision Guardian is a multi-sensor operator-assistance prototype for Heavy Earth Moving Machinery (HEMM), especially dumpers in the Bailadila open-cast iron ore region where monsoon fog can drop visibility to **3–5 metres**.

This repository contains the complete prototype: architecture, hardware plans, sensor test firmware, ESP32-S3 vehicle hub, Raspberry Pi 3 fusion engine, FastAPI command dashboard, simulation (so the demo runs without hardware), judge script, and the industrial upgrade path.

> This system **assists** the operator. It does not replace a human driver and does not claim full autonomy.

---

## What you can run right now (no hardware)

On this Windows PC:

```powershell
cd "C:\Users\panch\Desktop\MineTruck Project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r raspberry_pi/requirements.txt
python raspberry_pi/run.py
```

Then open **http://127.0.0.1:8000**

The dashboard starts in **simulation mode** with DUMPER_01 (live fused sensors) and DUMPER_02 (V2V peer). Use the **Judge Demo** panel to play Scenarios 1–5 from the prototype plan.

---

## Problem this prototype addresses

| Mine risk | Prototype response |
|---|---|
| Vehicle-to-vehicle and dumper collisions in fog | LiDAR + ultrasonic + radar + thermal fusion, distance zones, stop recommendation |
| Obstacle identification in 3–5 m visibility | TFMini-S forward ranging, side ultrasonics, thermal heat clusters |
| Lost situational awareness | Operator HUD + audio patterns + speed advice |
| Control-room blindness | Central fleet dashboard, GPS track, alerts, history |
| Halted operations / haul-cycle loss | Fog Safety Mode: slower recommended speed, higher sensor priority, not a full stop unless critical |

---

## Hardware used (exactly what you have)

| Component | Role |
|---|---|
| ESP32-S3-WROOM-N16R8 Dual USB-C | Vehicle sensor hub, real-time safety I/O, Wi-Fi + ESP-NOW |
| TFMini-S LiDAR (~12 m) | Primary forward obstacle distance |
| HC-SR04 × 2 | Left / right side collision ranging |
| MLX90640 55° thermal | Heat-signature / presence support (not identity) |
| Waveshare 24 GHz S3KM1110 mmWave | Human presence / micro-motion confirmation |
| OV7670 | Visible-light monitoring + visibility confidence |
| BME280 | Temperature, humidity, pressure → fog index |
| LM393 LDR | Ambient light / day-night / darkness risk |
| NEO-6M GPS | Coarse vehicle tracking (not collision-grade) |
| Raspberry Pi 3 Model B (1 GB) | Edge gateway, fusion, thermal/vision, dashboard |

---

## Architecture in one paragraph

Sensors feed the **ESP32-S3**, which runs low-latency zone logic (safe / warning, **DANGER + buzzer only if LiDAR < 1.5 m or left/right US < 1.0 m**), drives the 1.3" cab OLED plus buzzer and LEDs, and publishes JSON over Wi-Fi. The **Raspberry Pi 3** receives that stream, reads the thermal camera and visible camera, computes Fog Risk Index + Mine Safety Risk Score, runs the safety decision engine, logs SQLite, and serves the command dashboard. A second dumper is simulated for V2V. Full diagrams: [`docs/01-system-architecture.md`](docs/01-system-architecture.md).

---

## Repository map

```
MineTruck Project/
├── docs/                      Architecture, algorithms, API, demo, upgrades
├── hardware/                  Pin map, wiring, BOM, power
├── firmware/                  Sensor tests + integrated ESP32-S3 hub
├── raspberry_pi/              Fusion engine, API, simulation
├── dashboard/                 Command-and-control UI
├── scripts/                   Windows / Pi launchers
└── data/                      SQLite + logs at runtime
```

## Deliverable index (PDF checklist)

| # | Deliverable | Location |
|---|---|---|
| 1 | System architecture | `docs/01-system-architecture.md` |
| 2 | Hardware block diagram | `docs/03-hardware-block-diagram.md` |
| 3 | Sensor connection plan | `docs/04-sensor-connection-plan.md` |
| 4 | ESP32 pin mapping | `docs/05-esp32-pin-mapping.md` |
| 5 | Power supply design | `docs/06-power-supply-design.md` |
| 6 | Individual sensor tests | `firmware/tests/` |
| 7 | ESP32 integrated firmware | `firmware/src/` + `firmware/vehicle_hub/` |
| 8 | Raspberry Pi backend | `raspberry_pi/minevision/` |
| 9 | Sensor fusion | `docs/09-sensor-fusion.md` + `fusion/` |
| 10 | Fog Risk Index | `docs/10-fog-risk-index.md` |
| 11 | Mine Safety Risk Score | `docs/11-mine-safety-risk-score.md` |
| 12 | Thermal detection | `docs/12-thermal-detection.md` |
| 13 | Camera visibility | `docs/13-camera-visibility.md` |
| 14 | Collision detection | `docs/14-collision-detection.md` |
| 15–16 | FastAPI + dashboard | `raspberry_pi/minevision/api/` + `dashboard/` |
| 17 | Database schema | `docs/17-database-schema.md` |
| 18 | API documentation | `docs/15-api-documentation.md` |
| 19 | Sample JSON | `docs/16-sample-json-messages.md` |
| 20 | Folder structure | this README |
| 21 | Installation | `docs/18-installation.md` |
| 22 | Testing methodology | `docs/19-testing-methodology.md` |
| 23 | Judge demo script | `docs/20-demo-script.md` |
| 24 | NMDC scalability | `docs/21-scalability-plan.md` |
| 25 | Limitations | `docs/22-limitations.md` |
| 26 | Industrial upgrade path | `docs/23-industrial-upgrade-path.md` |

Start reading: [`docs/00-START-HERE.md`](docs/00-START-HERE.md)

---

## Honest engineering limits (stated up front)

- NEO-6M GPS is **not** centimetre-accurate. Production needs RTK/DGPS.
- HC-SR04 is **not** industrial-weather reliable.
- MLX90640 **cannot** identify a specific person.
- 12 m LiDAR is **not** enough for a real dumper at operational speed.
- Wi-Fi / ESP-NOW is **not** mine-wide V2X.
- Raspberry Pi 3 (1 GB) **cannot** run heavy YOLO models.

Each of those has a documented production upgrade in `docs/23-industrial-upgrade-path.md`.

---

## Development rule from the prototype plan

Build **incrementally**. Validate each sensor test sketch before flashing the integrated hub. The Pi fusion engine can be validated today in simulation, then pointed at a live ESP32 JSON stream.
