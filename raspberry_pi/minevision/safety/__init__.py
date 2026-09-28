"""Safety decision engine: maps fused score to operator outputs and alerts."""

from __future__ import annotations

from dataclasses import dataclass

from minevision import config
from minevision.fusion.distance import Zone
from minevision.fusion.engine import FuseResult


def closest_m(*vals: float | None) -> float | None:
    good = [float(v) for v in vals if v is not None and v > 0]
    return min(good) if good else None


def obstacle_too_close(
    front_m: float | None,
    left_m: float | None = None,
    right_m: float | None = None,
) -> bool:
    if front_m is not None and front_m > 0 and front_m < config.DANGER_FRONT_M:
        return True
    if left_m is not None and left_m > 0 and left_m < config.DANGER_SIDE_M:
        return True
    if right_m is not None and right_m > 0 and right_m < config.DANGER_SIDE_M:
        return True
    return False


@dataclass
class Decision:
    hud_color: str
    audio: str  # off | single | repeated | continuous
    speed_advice: str
    alerts: list[str]


def decide(
    vehicle_id: str,
    fused: FuseResult,
    front_m: float | None,
    left_m: float | None = None,
    right_m: float | None = None,
) -> Decision:
    level = fused.risk_level
    color = {
        "SAFE": "green",
        "CAUTION": "yellow",
        "HIGH RISK": "orange",
        "CRITICAL": "red",
    }[level]
    # Buzzer / DANGER: LiDAR < 1.5 m or left/right US < 1.0 m.
    close = closest_m(front_m, left_m, right_m)
    too_close = obstacle_too_close(front_m, left_m, right_m)
    audio = "continuous" if too_close else "off"

    alerts: list[str] = []
    if too_close and close is not None:
        alerts.append(
            f"CRITICAL: Obstacle {close:.1f} m from {vehicle_id} — cab buzzer ON"
        )
    elif fused.front_zone == Zone.DANGER and front_m is not None:
        alerts.append(
            f"CRITICAL: Obstacle detected {front_m:.1f} meters ahead of {vehicle_id}"
        )
    elif fused.front_zone == Zone.WARNING and front_m is not None:
        alerts.append(
            f"WARNING: Obstacle {front_m:.1f} m ahead of {vehicle_id}"
        )
    if fused.presence_high_confidence:
        alerts.append("HIGH CONFIDENCE PRESENCE — mmWave + thermal agree (person ahead)")
    elif fused.presence == "PRESENCE DETECTED":
        alerts.append("HUMAN PRESENCE (24 GHz) — person within 30 cm ahead")
    if fused.risk_level in ("HIGH RISK", "CRITICAL"):
        alerts.append("Vehicle entered high-risk zone")
    if fused.speed_advice == "STOP VEHICLE":
        alerts.append(f"{vehicle_id}: Recommend STOP VEHICLE")

    # de-dup preserve order
    seen: set[str] = set()
    uniq = []
    for a in alerts:
        if a not in seen:
            seen.add(a)
            uniq.append(a)

    return Decision(
        hud_color=color if not too_close else "red",
        audio=audio,
        speed_advice="STOP VEHICLE" if too_close else fused.speed_advice,
        alerts=uniq,
    )
