"""Live + simulated ESP32 telemetry and V2V peer."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from minevision import config


@dataclass
class RawTelemetry:
    vehicle_id: str
    front_distance: float | None
    left_distance: float | None
    right_distance: float | None
    lidar_strength: float
    temperature: float
    humidity: float
    pressure_hpa: float
    light_level: int
    light_raw: int
    motion_detected: bool
    radar_distance_m: float | None
    radar_occupied: bool
    latitude: float
    longitude: float
    gps_valid: bool
    gps_sats: int
    speed_kmh_gps: float
    heading_deg: float
    local_zone: str
    buzzer_state: str
    firmware: str = "1.0.0"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "front_distance": self.front_distance,
            "left_distance": self.left_distance,
            "right_distance": self.right_distance,
            "lidar_strength": self.lidar_strength,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "pressure_hpa": self.pressure_hpa,
            "light_level": self.light_level,
            "light_raw": self.light_raw,
            "motion_detected": self.motion_detected,
            "radar_distance_m": self.radar_distance_m,
            "radar_occupied": self.radar_occupied,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gps_valid": self.gps_valid,
            "gps_sats": self.gps_sats,
            "speed_kmh_gps": self.speed_kmh_gps,
            "heading_deg": self.heading_deg,
            "local_zone": self.local_zone,
            "buzzer_state": self.buzzer_state,
            "firmware": self.firmware,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
        }


class ScenarioEngine:
    """Judge demo scenarios 0 (free) and 1–5 from the prototype plan."""

    def __init__(self) -> None:
        self.scenario = 1
        self.t0 = time.time()
        self.phase = 0.0

    def set_scenario(self, n: int) -> None:
        self.scenario = int(n)
        self.t0 = time.time()
        self.phase = 0.0

    def tick(self) -> tuple[RawTelemetry, dict]:
        """Returns telemetry for DUMPER_01 plus sim extras (thermal/vis/fog inject)."""
        t = time.time() - self.t0
        self.phase += 0.05
        extras = {
            "thermal_hot": False,
            "fog_amount": 0.05,
            "ambient_c": 26.0,
        }
        # Haul-road micro path around Bailadila centre
        lat = config.MAP_CENTER_LAT + 0.0012 * math.sin(self.phase / 8)
        lon = config.MAP_CENTER_LON + 0.0015 * math.cos(self.phase / 8)
        heading = (math.degrees(self.phase / 8) + 90) % 360

        sc = self.scenario
        if sc == 0:
            front = 11.0 + 0.4 * math.sin(t)
            left, right = 9.4, 9.6
            temp, rh, light = 28.0, 55.0, 72
            motion = False
            speed = 22.0
        elif sc == 1:
            front, left, right = 11.4, 9.5, 9.8
            temp, rh, light = 29.0, 48.0, 80
            motion = False
            speed = 25.0
            extras["fog_amount"] = 0.05
        elif sc == 2:
            # Fog simulation: humidity + darkness + poor camera
            k = min(1.0, t / 8.0)
            front, left, right = 10.5, 9.0, 9.1
            temp = 22.0 - 1.5 * k
            rh = 55.0 + 40.0 * k
            light = int(80 - 60 * k)
            motion = False
            speed = 18.0
            extras["fog_amount"] = 0.15 + 0.7 * k
            extras["ambient_c"] = temp
        elif sc == 3:
            # Obstacle approaches
            front = max(3.8, 11.0 - t * 0.55)
            left, right = 9.2, 9.0
            temp, rh, light = 28.0, 52.0, 70
            motion = False
            speed = 16.0
        elif sc == 4:
            front, left, right = 9.2, 4.4, 6.5
            temp, rh, light = 27.0, 60.0, 50
            motion = True
            speed = 12.0
            extras["thermal_hot"] = True
            extras["fog_amount"] = 0.2
        elif sc == 5:
            front = max(0.9, 4.5 - t * 0.25)
            left, right = 3.2, 5.5
            temp, rh, light = 26.0, 70.0, 40
            motion = True
            speed = 8.0
            extras["thermal_hot"] = True
            extras["fog_amount"] = 0.35
        else:
            front, left, right = 10.0, 6.0, 6.0
            temp, rh, light = 27.0, 50.0, 70
            motion = False
            speed = 20.0

        too_close = (
            front < config.DANGER_FRONT_M
            or left < config.DANGER_SIDE_M
            or right < config.DANGER_SIDE_M
        )
        if front < config.DANGER_FRONT_M:
            zone = "DANGER"
        elif front < config.SAFE_M:
            zone = "WARNING"
        else:
            zone = "SAFE"
        buzz = "continuous" if too_close else "off"

        tel = RawTelemetry(
            vehicle_id=config.VEHICLE_ID,
            front_distance=round(front, 2),
            left_distance=round(left, 2),
            right_distance=round(right, 2),
            lidar_strength=280 if front < 12 else 90,
            temperature=round(temp, 1),
            humidity=round(rh, 1),
            pressure_hpa=1008.0,
            light_level=int(light),
            light_raw=int(light * 40),
            motion_detected=motion,
            radar_distance_m=round(min(front, 8.0), 2) if motion else None,
            radar_occupied=motion,
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            gps_valid=True,
            gps_sats=9,
            speed_kmh_gps=speed,
            heading_deg=round(heading, 1),
            local_zone=zone,
            buzzer_state=buzz,
            firmware="1.5.3",
        )
        extras["peer"] = self._peer(t, sc)
        return tel, extras

    def _peer(self, t: float, sc: int) -> dict:
        lat = config.MAP_CENTER_LAT + 0.0018 * math.cos(t / 10)
        lon = config.MAP_CENTER_LON + 0.0022 * math.sin(t / 10)
        risk = "SAFE"
        fog = False
        emergency = False
        speed = 18.0
        if sc == 2:
            risk, fog, speed = "CAUTION", True, 10.0
        if sc >= 4:
            risk, speed = "HIGH", 8.0
        if sc == 5:
            risk, emergency, speed = "CRITICAL", True, 0.0
        return {
            "vehicle_id": config.PEER_ID,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "speed": speed,
            "direction": int((t * 12) % 360),
            "risk_level": risk,
            "fog_mode": fog,
            "emergency": emergency,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
