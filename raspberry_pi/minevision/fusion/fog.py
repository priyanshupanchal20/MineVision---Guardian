"""Fog Risk Index 0–100."""

from __future__ import annotations

import math
from dataclasses import dataclass

from minevision import config


def dew_point_c(temp_c: float, rh: float) -> float:
    """Magnus formula over water, °C."""
    rh = min(100.0, max(0.1, rh))
    a, b = 17.62, 243.12
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh / 100.0)
    return (b * gamma) / (a - gamma)


def humidity_term(rh: float) -> float:
    if rh <= 40:
        return 0.0
    if rh <= 80:
        return 40.0 * (rh - 40.0) / 40.0
    return 40.0 + 60.0 * min(1.0, (rh - 80.0) / 15.0)


def dew_term(temp_c: float, rh: float) -> float:
    gap = temp_c - dew_point_c(temp_c, rh)
    return float(min(100.0, max(0.0, 100.0 * (8.0 - gap) / 8.0)))


def clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(min(hi, max(lo, x)))


@dataclass(frozen=True)
class FogResult:
    index: int
    label: str
    humidity_term: float
    dew_term: float
    light_term: float
    camera_term: float
    trend_term: float
    dew_point_c: float


def fog_label(index: int) -> str:
    if index <= 30:
        return "Clear"
    if index <= 60:
        return "Moderate visibility reduction"
    if index <= 80:
        return "Dense fog risk"
    return "Severe low visibility"


def fog_risk_index(
    temperature_c: float,
    humidity_rh: float,
    darkness_score: float,
    visibility_confidence: float | None,
    rh_slope_per_min: float = 0.0,
) -> FogResult:
    """
    darkness_score: 0 = bright, 100 = dark (from LDR).
    visibility_confidence: 0–1, or None if no camera.
    """
    h = humidity_term(humidity_rh)
    d = dew_term(temperature_c, humidity_rh)
    light = clip(darkness_score)
    if visibility_confidence is None:
        cam = 50.0
    else:
        cam = clip(100.0 * (1.0 - visibility_confidence))
    trend = clip(5.0 * max(0.0, rh_slope_per_min), 0.0, 10.0)
    raw = 0.35 * h + 0.25 * d + 0.15 * light + 0.20 * cam + 0.05 * trend
    idx = int(round(clip(raw)))
    return FogResult(
        index=idx,
        label=fog_label(idx),
        humidity_term=h,
        dew_term=d,
        light_term=light,
        camera_term=cam,
        trend_term=trend,
        dew_point_c=dew_point_c(temperature_c, humidity_rh),
    )


def fog_mode_next(index: int, currently_on: bool) -> bool:
    if currently_on:
        return index >= config.FOG_EXIT
    return index >= config.FOG_ENTER
