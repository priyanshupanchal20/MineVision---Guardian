"""Lightweight rolling z-score anomaly detector (Pi 3 friendly, no sklearn)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class AnomalyResult:
    label: str  # Normal | Caution | Dangerous
    z: float


class RollingAnomaly:
    def __init__(self, window: int = 40) -> None:
        self.window = deque(maxlen=window)

    def update(self, humidity: float, light: float, lidar_m: float | None, motion: bool, thermal: bool) -> AnomalyResult:
        x = humidity + (100 - light) + (0 if lidar_m is None else max(0, 12 - lidar_m) * 4)
        x += 25 if motion else 0
        x += 20 if thermal else 0
        self.window.append(x)
        if len(self.window) < 8:
            return AnomalyResult("Normal", 0.0)
        mu = sum(self.window) / len(self.window)
        var = sum((v - mu) ** 2 for v in self.window) / len(self.window)
        sd = var ** 0.5
        z = 0.0 if sd < 1e-6 else (x - mu) / sd
        if z > 2.5:
            label = "Dangerous"
        elif z > 1.4:
            label = "Caution"
        else:
            label = "Normal"
        return AnomalyResult(label, round(z, 2))
