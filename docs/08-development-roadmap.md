# Phase-by-phase development roadmap

Durations assume one builder with the listed hardware, evenings + one weekend.

| Phase | Goal | Exit criterion | Est. |
|---|---|---|---|
| **1 Planning** | Architecture, pins, power, protocols | This `docs/` pack reviewed | 1 day — **done in repo** |
| **2 Sensor tests** | Each device prints valid data | Serial output matches each test README | 3–4 days |
| **3 ESP32 hub** | Combined JSON + local alarms | JSON matches schema; danger trip works with Pi unplugged | 2 days |
| **4 Pi edge** | Ingest + thermal + camera + logs | Dashboard live with hardware or sim | 2 days |
| **5 AI/ML** | Visibility, thermal clusters, optional IsolationForest | Unit tests pass; Pi CPU < 60% | 1 day |
| **6 Safety engine** | Rules + weights + speed advice | Scenarios 1–5 reproducible | 1 day |
| **7 Dashboard** | Map, cards, charts, alerts | Judge can operate from a browser | 1 day |
| **8 Integration** | Full stack on RC body | Demo script timed < 8 minutes | 2 days |

## Phase 2 detail (do not skip)

1. LDR analog sweep (cover / lamp).
2. One ultrasonic against a wall at 30, 50, 100 cm.
3. BME280 plausible T/RH (breath test raises RH).
4. TFMini-S on a tape measure 0.3–8 m (strength > 100).
5. GPS outdoors, `fix_valid: true`.
6. mmWave: walk into FOV, `occupied` flips.
7. MLX90640: palm raises a cluster.
8. Camera: fog cloth drops contrast / visibility_confidence.

## Phase 8 demo hardware path

Miniature dumper or RC truck → sensor mast → ESP32 in hull → 5 V bank → Pi on table with HDMI or laptop on same Wi-Fi → projector on `http://<pi>:8000`.

## Parallel software track (can finish before wiring)

Windows simulation already implements Phases 4–8. Use it to rehearse the judge script the same day you clone this repo.
