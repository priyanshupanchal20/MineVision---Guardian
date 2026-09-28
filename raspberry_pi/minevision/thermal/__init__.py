"""Thermal cluster analysis for MLX90640 32x24 matrices."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from minevision import config
from minevision.thermal.mlx import MlxCamera


@dataclass
class ThermalResult:
    anomaly: bool
    risk: float
    max_c: float
    cluster_count: int
    largest_blob: int
    heat_moving: bool
    heatmap_16x12: list[list[float]]
    note: str


def _connected_components(mask: np.ndarray) -> list[int]:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    sizes: list[int] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            n = 0
            while stack:
                cy, cx = stack.pop()
                n += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            sizes.append(n)
    return sizes


class ThermalAnalyzer:
    def __init__(self) -> None:
        self.background: np.ndarray | None = None
        self.prev: np.ndarray | None = None
        self.warmup = 0

    def reset(self) -> None:
        self.background = None
        self.prev = None
        self.warmup = 0

    def process(self, frame_c: np.ndarray) -> ThermalResult:
        frame = np.asarray(frame_c, dtype=np.float32)
        if frame.shape != (config.THERMAL_ROWS, config.THERMAL_COLS):
            frame = frame.reshape(config.THERMAL_ROWS, config.THERMAL_COLS)

        if self.background is None:
            self.background = frame.copy()
        else:
            self.background = 0.98 * self.background + 0.02 * frame
        self.warmup += 1

        residual = frame - self.background
        roi = residual[8:24, 8:24]
        abs_roi = frame[8:24, 8:24]
        sigma = float(np.std(roi)) if roi.size else 0.0
        thr = max(config.THERMAL_RESIDUAL_C, 1.8 * sigma)
        mask = (roi > thr) & (abs_roi > config.THERMAL_ABS_MIN_C)
        sizes = [s for s in _connected_components(mask) if s >= config.THERMAL_MIN_BLOB]
        n = len(sizes)
        largest = max(sizes) if sizes else 0
        tmax = float(np.max(frame))
        risk = float(
            np.clip(20 * n + 2 * largest + 1.5 * (tmax - 28.0), 0, 100)
        )
        moving = False
        if self.prev is not None:
            moving = float(np.mean(np.abs(frame - self.prev))) > 0.4
        self.prev = frame.copy()

        small = frame.reshape(24, 32)[::2, ::2]  # 12x16
        heatmap = np.round(small, 1).tolist()
        anomaly = n >= 1 and self.warmup >= 3
        if anomaly:
            note = f"Heat cluster ({n} region(s), max {tmax:.1f} °C) — not a person ID"
        else:
            note = "No thermal anomaly"

        return ThermalResult(
            anomaly=bool(anomaly),
            risk=risk if anomaly else min(risk, 15.0),
            max_c=tmax,
            cluster_count=n if anomaly else 0,
            largest_blob=largest if anomaly else 0,
            heat_moving=moving,
            heatmap_16x12=heatmap,
            note=note,
        )


def synthetic_frame(
    ambient_c: float = 26.0,
    hot_blob: bool = False,
    blob_c: float = 34.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    frame = ambient_c + rng.normal(0, 0.25, (24, 32))
    if hot_blob:
        frame[10:16, 13:19] = blob_c + rng.normal(0, 0.4, (6, 6))
    return frame.astype(np.float32)
