"""Weighted Mine Safety Risk Score + presence logic."""

from __future__ import annotations

from dataclasses import dataclass

from minevision import config
from minevision.fusion.distance import Zone, distance_risk, effective_thresholds
from minevision.fusion.fog import FogResult, fog_mode_next, fog_risk_index


def clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(min(hi, max(lo, x)))


def risk_label(score: int) -> str:
    if score <= 30:
        return "SAFE"
    if score <= 60:
        return "CAUTION"
    if score <= 80:
        return "HIGH RISK"
    return "CRITICAL"


def speed_advice(label: str, fog_mode: bool) -> str:
    mapping = {
        "SAFE": "NORMAL SPEED",
        "CAUTION": "REDUCE SPEED",
        "HIGH RISK": "CRAWL MODE",
        "CRITICAL": "STOP VEHICLE",
    }
    advice = mapping[label]
    if fog_mode and advice == "NORMAL SPEED":
        return "REDUCE SPEED"
    return advice


@dataclass
class FuseInput:
    front_m: float | None
    left_m: float | None
    right_m: float | None
    temperature_c: float
    humidity_rh: float
    darkness_score: float
    visibility_confidence: float | None
    thermal_anomaly: bool
    thermal_risk: float
    motion_detected: bool
    lidar_strength: float | None = None
    rh_slope_per_min: float = 0.0
    fog_mode_prev: bool = False
    lidar_confirms_obstacle: bool | None = None


@dataclass
class FuseResult:
    risk_score: int
    risk_level: str
    speed_advice: str
    fog: FogResult
    fog_mode: bool
    front_zone: Zone
    left_zone: Zone
    right_zone: Zone
    distance_risk: float
    thermal_risk: float
    motion_risk: float
    visibility_risk: float
    agreement_bonus: int
    presence: str
    presence_high_confidence: bool
    weights: dict
    notes: list[str]


def _lidar_obstacle(front_m: float | None, fog_mode: bool, strength: float | None) -> bool:
    if front_m is None:
        return False
    if strength is not None and strength < config.LIDAR_MIN_STRENGTH:
        return False
    _safe, warn = effective_thresholds(fog_mode)
    return front_m <= warn * 2  # warning or closer counts as "object"


def fuse(inp: FuseInput) -> FuseResult:
    vis = inp.visibility_confidence
    fog = fog_risk_index(
        inp.temperature_c,
        inp.humidity_rh,
        inp.darkness_score,
        vis,
        inp.rh_slope_per_min,
    )
    fog_mode = fog_mode_next(fog.index, inp.fog_mode_prev)
    weights = dict(config.WEIGHTS_FOG if fog_mode else config.WEIGHTS_CLEAR)

    d_risk, fz, lz, rz = distance_risk(inp.front_m, inp.left_m, inp.right_m, fog_mode)
    thermal_risk = clip(inp.thermal_risk)
    motion_risk = 80.0 if inp.motion_detected else 10.0
    vis_conf = 0.5 if vis is None else vis
    visibility_risk = clip(100.0 * (1.0 - vis_conf))

    notes: list[str] = []
    if inp.left_m is None:
        notes.append("Left ultrasonic offline — replace HC-SR04 / check GPIO7 echo")
    if inp.right_m is None:
        notes.append("Right ultrasonic has no echo")
    if inp.front_m is None:
        notes.append("Front LiDAR has no valid return")
    if inp.lidar_strength is not None and inp.lidar_strength < config.LIDAR_MIN_STRENGTH:
        notes.append("LiDAR strength weak — distance confidence reduced")
        d_risk = 0.4 * d_risk + 0.6 * 40.0

    base = (
        weights["distance"] * d_risk
        + weights["environment"] * fog.index
        + weights["thermal"] * thermal_risk
        + weights["motion"] * motion_risk
        + weights["visibility"] * visibility_risk
    )

    lidar_hit = _lidar_obstacle(inp.front_m, fog_mode, inp.lidar_strength)
    if inp.lidar_confirms_obstacle is not None:
        lidar_hit = inp.lidar_confirms_obstacle
    votes = int(lidar_hit) + int(inp.thermal_anomaly) + int(inp.motion_detected)
    bonus = 0
    if votes >= 3:
        bonus = config.AGREEMENT_BONUS_FULL
        notes.append("LiDAR + thermal + mmWave agreement")
    elif votes == 2:
        bonus = config.AGREEMENT_BONUS_PARTIAL
        notes.append("Two-sensor agreement")

    score = clip(base + bonus)

    # Rule overrides (PDF Phase 6)
    if fz == Zone.DANGER or lz == Zone.DANGER or rz == Zone.DANGER:
        score = max(score, 81.0)
        notes.append("Rule: ranging DANGER → CRITICAL floor")
    if fog.index > 70 and fz in (Zone.WARNING, Zone.DANGER):
        score = max(score, 61.0)
        notes.append("Rule: dense fog + obstacle → HIGH RISK floor")

    high_presence = bool(inp.motion_detected and inp.thermal_anomaly)
    if high_presence:
        score = max(score, 61.0)
        notes.append("Rule: mmWave + thermal → HIGH CONFIDENCE PRESENCE")
        presence = "HIGH CONFIDENCE PRESENCE"
    elif inp.motion_detected or inp.thermal_anomaly:
        presence = "PRESENCE DETECTED"
    else:
        presence = "CLEAR"

    score_i = int(round(clip(score)))
    label = risk_label(score_i)
    if fog_mode:
        notes.append("FOG SAFETY MODE — LiDAR/radar/thermal prioritized")

    return FuseResult(
        risk_score=score_i,
        risk_level=label,
        speed_advice=speed_advice(label, fog_mode),
        fog=fog,
        fog_mode=fog_mode,
        front_zone=fz,
        left_zone=lz,
        right_zone=rz,
        distance_risk=d_risk,
        thermal_risk=thermal_risk,
        motion_risk=motion_risk,
        visibility_risk=visibility_risk,
        agreement_bonus=bonus,
        presence=presence,
        presence_high_confidence=high_presence,
        weights=weights,
        notes=notes,
    )
