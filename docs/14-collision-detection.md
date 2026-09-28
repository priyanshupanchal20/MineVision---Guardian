# Collision detection algorithm

## Forward (primary): TFMini-S

Valid range used: **0.3–12.0 m**. Strength must be ≥ 100 or the sample is marked `lidar_weak`.

Zones (defaults, fog-inflated when Fog Mode on):

- SAFE: `d > safe_m`
- WARNING: `warn_m < d ≤ safe_m`
- DANGER: `d ≤ warn_m`

Hysteresis 0.3 m to stop LED flicker.

## Sides: HC-SR04

Timeout 25 ms ≈ 4 m useful (sensor claims 4 m in still air; treat > 3.5 m as “clear / max”).  
If left << right by > 1.5 m and left < warn_m → `side_bias = LEFT`. Symmetric for right. UI can say “obstacle closer on left”.

## Combined collision flag

```
obstacle_front = zone in {WARNING, DANGER}
collision_imminent = zone == DANGER
side_risk = left_zone == DANGER or right_zone == DANGER
```

CRITICAL if `collision_imminent` **or** (`side_risk` and speed_sim > crawl). Simulated speed comes from the decision engine, not a real tachometer.

## Audio (ESP32 + dashboard)

| Level | Pattern |
|---|---|
| CAUTION | single beep / 1.2 s |
| HIGH RISK | repeated 4 Hz |
| CRITICAL | continuous |

## What 12 m LiDAR cannot do

A loaded dumper at 30 km/h travels **8.3 m/s**. 12 m of range is **< 1.5 s** to impact even with instant brakes, which HEMM does not have. Production requires **long-range industrial LiDAR / radar** (80–200 m class) and speed-interlocks from the OEM. This prototype demonstrates the **logic**, not the stopping distance.
