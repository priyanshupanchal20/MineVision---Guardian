"""ESP-NOW / JSON V2V helpers (software path)."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def beacon(
    vehicle_id: str,
    latitude: float,
    longitude: float,
    speed: float,
    direction: float,
    risk_level: str,
    fog_mode: bool,
    emergency: bool = False,
) -> dict:
    return {
        "vehicle_id": vehicle_id,
        "latitude": latitude,
        "longitude": longitude,
        "speed": speed,
        "direction": direction,
        "risk_level": risk_level,
        "fog_mode": fog_mode,
        "emergency": emergency,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def encode(packet: dict) -> bytes:
    return json.dumps(packet, separators=(",", ":")).encode("utf-8")
