# Mine Safety Risk Score

Output: integer **0–100** plus label and speed recommendation.

## Distance risk

Front distance `d` (metres), zones `safe_m=8`, `warn_m=4` (or fog-inflated):

```
if d is None: front_risk = 40          # unknown is not safe
elif d >= safe_m: front_risk = 5
elif d >= warn_m: front_risk = 35 + 45*(safe_m-d)/(safe_m-warn_m)
else: front_risk = 80 + 20*clip((warn_m-d)/warn_m, 0, 1)
```

Left/right ultrasonics the same. Combine:

```
distance_risk = 0.70*front + 0.15*left + 0.15*right
```

## Other terms

- `environmental_risk = FogIndex`
- `thermal_risk` from cluster algorithm (0 if camera missing and no anomaly)
- `motion_risk = 80 if occupied else 10` (10 is sensor heartbeat, not “human”)
- `visibility_risk = 100*(1-vis_conf)`

Weighted sum + agreement bonus + rule overrides: `docs/09-sensor-fusion.md`.

## Speed recommendation mapping

| Label | Advice |
|---|---|
| SAFE | NORMAL SPEED |
| CAUTION | REDUCE SPEED |
| HIGH RISK | CRAWL MODE |
| CRITICAL | STOP VEHICLE |

Fog mode clamps NORMAL → REDUCE even when score is SAFE.

## What this score is not

It is **not** a probability of fatality, **not** an ISO 13849 PL rating, and **not** a substitute for mine traffic procedures. It is a **prototype operator cue** that is fully inspectable in `fusion/engine.py`.
