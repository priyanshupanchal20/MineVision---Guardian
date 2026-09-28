# Thermal detection algorithm (MLX90640)

Sensor: 32×24 IR array, 55° FOV, I2C `0x33`. Output is a **temperature matrix in °C**, not a classified person.

## Honest claim

We detect **warm clusters** that *may* be humans, engines, or tyres. We never display “identified human ID”. UI copy is:

- `THERMAL: no anomaly`
- `THERMAL: heat cluster` + max °C + pixel count
- Combined with mmWave: `HIGH CONFIDENCE PRESENCE`

## Pipeline (Pi 3, 2 Hz)

1. Read 768 floats via Adafruit MLX90640 (refresh 2 Hz to save I2C).
2. Subtract a slow EMA background `B ← 0.98 B + 0.02 T` after 20 frames of warmup.
3. Residual `R = T - B`.
4. Forward ROI: columns 8–23, rows 8–23 (central ~50% of FOV, haul path).
5. Threshold: `R > max(2.5 °C, 1.8*σ_R)` **and** absolute `T > 28 °C` (tune for Chhattisgarh ambient).
6. Connected components (4-neighbour). Keep blobs with **≥ 4 pixels**.
7. Score:

```
thermal_risk = clip(20 * n_clusters + 2 * largest_blob_px + 1.5 * (Tmax - 28), 0, 100)
anomaly = n_clusters >= 1
```

8. Downsample 32×24 → 16×12 for WebSocket heatmap (bandwidth).

## Motion of heat

`ΔT` frame-to-frame in the ROI, mean abs > 0.4 °C → `heat_moving = true` (helps Scenario 4).

## Failure modes

- Sun-heated rocks look like engines.
- Glass and rain on the lens flatten contrast.
- 55° FOV will miss a person beside the dumper — that is why mmWave + ultrasonics exist.
