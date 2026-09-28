# Camera visibility estimation

Used to **lower RGB trust in fog/darkness**, not to drive the vehicle.

## Metrics on a ≤ 320×240 grayscale frame

| Metric | Method | Fog/dark effect |
|---|---|---|
| Contrast | σ of pixels / 128, clipped 0–1 | fog lowers σ |
| Edge density | fraction of Canny pixels | fog/blur lowers edges |
| Blur | variance of Laplacian; `< 60` is soft | fog and motion blur |

```
visibility_confidence = clip(0.45*contrast_n + 0.35*edge_n + 0.20*blur_n, 0, 1)
```

`blur_n = clip(lap_var / 200, 0, 1)`.

## Categories (UI)

| Confidence | Label |
|---|---|
| ≥ 0.65 | GOOD |
| 0.35–0.65 | DEGRADED |
| < 0.35 | POOR |

POOR automatically feeds the Fog Index camera term and drops RGB fusion weight.

## Capture sources (in order)

1. OV7670 on the Pi 3 header (160×120 grayscale, live mode)
2. USB webcam only if `MINEVISION_USB_CAM=1`
3. Simulation generator when `MINEVISION_MODE=sim`

Pi 3 cannot run YOLO here. If a future industrial PC is fitted, a **quantized** obstacle detector can be added **beside** this metric, never instead of LiDAR.
