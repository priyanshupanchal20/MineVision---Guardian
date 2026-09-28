# Fog Risk Index (0–100)

Inputs (all available on this hardware, plus camera when present):

| Input | Clear → foggy mapping |
|---|---|
| Relative humidity | RH 40% → 0, RH 95%+ → 100 (piecewise linear, steep after 80%) |
| Dew proximity | `T_air - T_dew`; 8 °C gap → 0, ≤ 1 °C → 100 |
| Ambient light | LDR scaled; dark pit + high RH raises fog, dark + dry is just night |
| Visible-camera clarity | `1 - visibility_confidence` |
| Optional history | rolling 5-minute RH slope (positive slope adds up to +10) |

Dew point uses Magnus over water:

```
a = 17.62, b = 243.12
γ = (a·T)/(b+T) + ln(RH/100)
T_dew = (b·γ)/(a-γ)
```

## Formula

```
humidity_term   = piecewise_rh(RH)
dew_term        = clip(100 * (8 - (T - T_dew)) / 8, 0, 100)
light_term      = darkness_score          # 0 bright, 100 dark
camera_term     = 100 * (1 - vis_conf)    # 50 if camera missing
trend_term      = clip(5 * dRH/min, 0, 10)

FogIndex = 0.35*humidity + 0.25*dew + 0.15*light + 0.20*camera + 0.05*trend
```

## Categories

| Index | Label |
|---|---|
| 0–30 | Clear |
| 31–60 | Moderate visibility reduction |
| 61–80 | Dense fog risk |
| 81–100 | Severe low visibility |

## FOG SAFETY MODE

Enters when `FogIndex >= fog_enter_threshold` (default **70**), exits below **60** (hysteresis).

While active:

- LiDAR poll already at 100 Hz internally; telemetry stays 5 Hz but danger path is unchanged
- Radar and thermal weights increase (see fusion doc)
- RGB camera weight drops
- Recommended speed at most REDUCE even if path is clear
- Obstacle warning distance **inflates** by `fog_zone_scale` (default 1.25): warning starts at 10 m equivalent, danger at 5 m
- Central dashboard banner `FOG MODE ACTIVATED`

Humidity alone is **not** fog (a wet tropical pit can be 90% RH and still see 50 m). The index therefore requires the **combination** of moisture, dew proximity, and optical/light evidence. Software demo Scenario 2 injects those together so the mode is obvious for judges.
