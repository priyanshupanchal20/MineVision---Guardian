"""Forward / side ranging zones and distance risk."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from minevision import config


class Zone(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    DANGER = "DANGER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ZoneResult:
    zone: Zone
    risk: float
    distance_m: float | None


def clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(min(hi, max(lo, x)))


def effective_thresholds(fog_mode: bool) -> tuple[float, float]:
    safe_m = config.SAFE_M
    warn_m = config.WARN_M
    if fog_mode:
        safe_m *= config.FOG_ZONE_SCALE
        warn_m *= config.FOG_ZONE_SCALE
    return safe_m, warn_m


def _scaled_danger(danger_m: float, fog_mode: bool) -> float:
    return danger_m * config.FOG_ZONE_SCALE if fog_mode else danger_m


def classify_zone(
    distance_m: float | None,
    fog_mode: bool = False,
    previous: Zone | None = None,
    danger_m: float | None = None,
) -> Zone:
    if distance_m is None:
        return Zone.UNKNOWN
    safe_m, _warn_m = effective_thresholds(fog_mode)
    limit = _scaled_danger(
        config.DANGER_FRONT_M if danger_m is None else danger_m,
        fog_mode,
    )
    hyst = config.ZONE_HYSTERESIS_M
    if previous == Zone.DANGER:
        if distance_m > limit + hyst:
            previous = None
        else:
            return Zone.DANGER
    if previous == Zone.WARNING:
        if distance_m > safe_m + hyst:
            return Zone.SAFE
        if distance_m <= limit:
            return Zone.DANGER
        return Zone.WARNING
    if distance_m > safe_m:
        return Zone.SAFE
    if distance_m > limit:
        return Zone.WARNING
    return Zone.DANGER


def component_risk(
    distance_m: float | None,
    fog_mode: bool,
    danger_m: float | None = None,
) -> float:
    if distance_m is None:
        # Missing sensor (left US unplugged) is not an obstacle.
        return 5.0
    safe_m, warn_m = effective_thresholds(fog_mode)
    limit = _scaled_danger(
        config.DANGER_FRONT_M if danger_m is None else danger_m,
        fog_mode,
    )
    d = distance_m
    if d >= safe_m:
        return 5.0
    if d >= warn_m:
        return 35.0 + 20.0 * (safe_m - d) / max(0.1, safe_m - warn_m)
    if d >= limit:
        return 55.0 + 24.0 * (warn_m - d) / max(0.1, warn_m - limit)
    return 80.0 + 20.0 * clip((limit - d) / max(0.1, limit), 0.0, 1.0)


def distance_risk(
    front_m: float | None,
    left_m: float | None,
    right_m: float | None,
    fog_mode: bool = False,
) -> tuple[float, Zone, Zone, Zone]:
    front_z = classify_zone(front_m, fog_mode, danger_m=config.DANGER_FRONT_M)
    left_z = classify_zone(left_m, fog_mode, danger_m=config.DANGER_SIDE_M)
    right_z = classify_zone(right_m, fog_mode, danger_m=config.DANGER_SIDE_M)
    risk = (
        0.70 * component_risk(front_m, fog_mode, config.DANGER_FRONT_M)
        + 0.15 * component_risk(left_m, fog_mode, config.DANGER_SIDE_M)
        + 0.15 * component_risk(right_m, fog_mode, config.DANGER_SIDE_M)
    )
    return clip(risk), front_z, left_z, right_z
