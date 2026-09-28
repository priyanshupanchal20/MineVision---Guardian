# Sensor fusion engine

The stack never treats one sensor as ground truth. It computes a **Mine Safety Risk Score (0–100)** from weighted, environment-dependent confidences.

## Why weights move

| Condition | RGB camera | LiDAR | mmWave | Thermal | Ultrasonic |
|---|---|---|---|---|---|
| Clear daylight | high | high | medium | medium | medium |
| Dense fog (Fog Index ≥ 70) | **low** | **higher** | **higher** | **higher** | medium (wet dirt / rain still hurts) |
| Darkness, no fog | **low** | high | high | **higher** | medium |
| Heavy rain / mud on transducers | medium | medium | high | medium | **low** |
| Multi-sensor agreement | confidence **bonus**, not a new sensor | | | | |

## Agreement bonus

If LiDAR reports an object in WARNING/DANGER **and** thermal has a hot cluster in the forward ROI **and** mmWave `occupied`:

```
HIGH CONFIDENCE OBSTACLE / PRESENCE EVENT
confidence = min(1.0, 0.45 + 0.25*lidar + 0.15*thermal + 0.15*radar)
risk_score += 12  (capped at 100)
```

Two of three sensors: +6. One sensor: no bonus.

## Formula (implemented in `fusion/engine.py`)

```
distance_risk      ∈ [0,100]   from front/left/right (worst side wins 0.25, front 0.75)
environmental_risk ∈ [0,100]   = Fog Risk Index
thermal_risk       ∈ [0,100]   cluster score (not “human class”)
motion_risk        ∈ [0,100]   mmWave occupied + energy
visibility_risk    ∈ [0,100]   100 * (1 - visibility_confidence)

base = Σ (w_i * component_i)   with Σ w = 1
score = clip(base + agreement_bonus + rule_overrides, 0, 100)
```

Default clear-weather weights:

```
w_distance = 0.40
w_environment = 0.15
w_thermal = 0.15
w_motion = 0.15
w_visibility = 0.15
```

Fog Safety Mode weights:

```
w_distance = 0.38
w_environment = 0.12
w_thermal = 0.22
w_motion = 0.22
w_visibility = 0.06
```

Rule overrides (always applied after weights):

- `front < danger_m` → score ≥ 81 (CRITICAL)
- Fog Index > 70 **and** any obstacle in warning zone → score ≥ 61 (HIGH RISK)
- mmWave occupied **and** thermal anomaly → `presence_confidence = high`, score ≥ 61 if not already critical

## Categories

| Score | Label | HUD | Speed advice |
|---|---|---|---|
| 0–30 | SAFE | 🟢 | NORMAL SPEED |
| 31–60 | CAUTION | 🟡 | REDUCE SPEED |
| 61–80 | HIGH RISK | 🟠 | CRAWL MODE |
| 81–100 | CRITICAL | 🔴 | STOP VEHICLE |

## Sensor confidence scalars

Each raw reading is multiplied by `c ∈ [0,1]` before it can dominate the score. Examples:

- LiDAR strength < 100 → `c_lidar = 0.4` (sun, dust, no target)
- GPS HDOP > 5 or no fix → location used for map only, **zero** collision weight
- Ultrasonic timeout → that side `c = 0`, score does not assume a phantom wall

This is **not** Kalman tracking of a dumper-sized object. A production stack would add an Extended Kalman / particle filter on industrial LiDAR + radar tracks. Here the fusion is a **transparent weighted risk**, which judges can audit on a whiteboard.

## Optional anomaly layer (Pi 3)

`fusion/anomaly.py` is a rolling z-score over humidity, light, LiDAR gap, radar, and thermal flags. Labels: Normal / Caution / Dangerous. IsolationForest + sklearn is intentionally **not** used — it is heavier than a 1 GB Pi 3 should carry for this demo.

