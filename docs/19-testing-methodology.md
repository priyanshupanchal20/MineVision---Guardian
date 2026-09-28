# Prototype testing methodology

Test in this order. Record pass/fail in a lab notebook; SIH judges may ask.

## 1. Unit tests (no hardware)

```text
pytest raspberry_pi/tests -q
```

Must pass: fog index bands, risk categories, hysteresis, agreement bonus, collision zones, visibility formula.

## 2. Sensor benches (Phase 2)

Each `firmware/tests/*` README lists wiring, expected serial lines, and troubleshooting.

Acceptance: 20 consecutive valid frames or a documented environmental reason (e.g. GPS indoor).

## 3. ESP32 hub without Pi

Cardboard: LiDAR ~3 m must **not** be DANGER and **no beep**. LiDAR ~1.2 m or left/right US ~0.8 m: DANGER + continuous buzzer **with Wi-Fi off**.

## 4. Ingest integration

`curl` POST sample JSON from `docs/16-sample-json-messages.md` to a running Pi/Windows API. Dashboard card must update < 1 s.

## 5. Scenario tests (physical)

Follow PDF scenarios:

| ID | Setup | Pass |
|---|---|---|
| 1 Normal | open space, lights on | Green, fog low, NORMAL |
| 2 Fog | humidifier + cloth over camera + optional RH inject | Fog Mode banner, REDUCE |
| 3 Obstacle | box in front of LiDAR | distance matches tape ±10 cm, warning/stop |
| 4 Presence | person or warm mug + stand in radar FOV | PRESENCE / high confidence if thermal also |
| 5 Critical | object < 1.5 m | cab buzzer continuous, STOP, alert text with metres |

## 6. Negative tests

- Cover LiDAR: strength drops, system must **not** claim SAFE solely from camera.
- Unplug Pi: ESP32 alarm still works.
- Unplug GPS: map stale, collision logic unchanged.
- Dual ultrasonic crosstalk: enable stagger; distances should not jump together.

## 7. Endurance

30-minute sim or live run. Memory on Pi: `free -h` should stay with ≥ 80 MB free. SQLite file growth sane.

## 8. Judge dry-run

Time `docs/20-demo-script.md`. Target **≤ 8 minutes** talking, 2 minutes backup video.
