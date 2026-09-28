"""FastAPI command-and-control backend."""

from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from minevision import config
from minevision.fusion.anomaly import RollingAnomaly
from minevision.fusion.engine import FuseInput, fuse
from minevision.ingest import RawTelemetry, ScenarioEngine
from minevision.safety import decide
from minevision.storage import Database
from minevision.thermal import ThermalAnalyzer, synthetic_frame, MlxCamera
from minevision.netinfo import LAN_NAME, LanAdvertiser, dashboard_urls, host_stem, ipv4_addrs
from minevision.vision import CameraSource, visibility_from_gray

ROOT = Path(__file__).resolve().parents[3]
DASHBOARD = ROOT / "dashboard"


class Esp32Telemetry(BaseModel):
    vehicle_id: str = "DUMPER_01"
    front_distance: float | None = None
    left_distance: float | None = None
    right_distance: float | None = None
    lidar_strength: float = 200
    temperature: float = 26.0
    humidity: float = 50.0
    pressure_hpa: float = 1013.0
    light_level: int = 50
    light_raw: int = 2000
    motion_detected: bool = False
    radar_distance_m: float | None = None
    radar_occupied: bool = False
    latitude: float | None = None
    longitude: float | None = None
    gps_valid: bool = False
    gps_sats: int = 0
    speed_kmh_gps: float = 0.0
    heading_deg: float = 0.0
    pitch_deg: float | None = None
    roll_deg: float | None = None
    accel_x_g: float | None = None
    accel_y_g: float | None = None
    accel_z_g: float | None = None
    tilt_alert: bool = False
    local_zone: str = "SAFE"
    buzzer_state: str = "off"
    firmware: str = "1.0.0"
    timestamp: str | None = None
    cab_advice: str | None = None
    model_config = {"extra": "ignore"}


class V2VBeacon(BaseModel):
    vehicle_id: str
    latitude: float
    longitude: float
    speed: float = 0.0
    direction: float = 0.0
    risk_level: str = "SAFE"
    fog_mode: bool = False
    emergency: bool = False
    timestamp: str | None = None


class ScenarioBody(BaseModel):
    scenario: int = Field(ge=0, le=5)


class ThresholdBody(BaseModel):
    safe_m: float | None = None
    warn_m: float | None = None
    buzz_m: float | None = None
    danger_front_m: float | None = None
    danger_side_m: float | None = None
    fog_enter: int | None = None
    fog_exit: int | None = None


class Hub:
    def __init__(self) -> None:
        self.db = Database()
        self.scenario = ScenarioEngine()
        self.thermal = ThermalAnalyzer()
        self.mlx = MlxCamera()
        self.anomaly = RollingAnomaly()
        self.camera = CameraSource()
        from minevision.vision.st7735 import CameraTft

        self.tft = CameraTft(self.camera, self.mlx)
        self.lan = LanAdvertiser(config.PORT)
        self.fog_mode = False
        self.started = time.time()
        self.vehicles: dict[str, dict[str, Any]] = {}
        self.heatmaps: dict[str, list] = {}
        self.last_alerts: list[dict] = []
        self._alert_seen: dict[str, float] = {}
        self._alert_ack: set[str] = set()
        self.sockets: list[WebSocket] = []
        self.lock = asyncio.Lock()
        self.rh_prev = 50.0
        self.rh_prev_t = time.time()
        self.us_hold: dict[str, dict[str, float | None]] = {}
        self._db_t = 0.0
        self._slow_t = 0.0
        self._vis = None
        self._th = None
        self.last_gray = None
        self.last_rgb = None
        self.last_ingest_ts = 0.0

    def _darkness(self, light_level: int) -> float:
        return float(max(0, min(100, 100 - light_level)))

    def _rh_slope(self, rh: float) -> float:
        now = time.time()
        dt_min = max(1e-3, (now - self.rh_prev_t) / 60.0)
        slope = (rh - self.rh_prev) / dt_min
        self.rh_prev = rh
        self.rh_prev_t = now
        return slope

    def _hold_us(self, vid: str, left, right) -> tuple[float | None, float | None]:
        now = time.time()
        h = self.us_hold.setdefault(vid, {"left": None, "right": None, "lt": 0.0, "rt": 0.0})

        def one(val, key: str, tkey: str) -> float | None:
            parsed = None
            if val is not None:
                try:
                    parsed = float(val)
                except (TypeError, ValueError):
                    parsed = None
                if parsed is not None and config.US_MIN_M <= parsed <= config.US_MAX_M:
                    h[key] = round(parsed, 2)
                    h[tkey] = now
                    return h[key]
            if now - float(h[tkey] or 0) <= config.US_HOLD_S:
                return h[key]  # type: ignore[return-value]
            h[key] = None
            return None

        return one(left, "left", "lt"), one(right, "right", "rt")

    def _hold_front(self, vid: str, front):
        now = time.time()
        h = self.us_hold.setdefault(vid, {"left": None, "right": None, "lt": 0.0, "rt": 0.0})
        parsed = None
        if front is not None:
            try:
                parsed = float(front)
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None and config.LIDAR_MIN_M <= parsed <= config.LIDAR_MAX_M:
                h["front"] = round(parsed, 2)
                h["ft"] = now
                return h["front"]
        if now - float(h.get("ft") or 0) <= config.LIDAR_HOLD_S:
            return h.get("front")
        h["front"] = None
        return None

    def _slow_vision_thermal(self, tel: dict, extras: dict):
        now = time.time()
        if self._th is not None and now - self._slow_t < config.SLOW_SENSORS_S:
            return self._vis, self._th
        self._slow_t = now
        fog_amt = float(extras.get("fog_amount", 0.1))
        gray = self.camera.read_gray(fog_amt)
        self.last_gray = gray
        self.last_rgb = self.camera.read_rgb(fog_amt)
        vis = visibility_from_gray(gray)
        hot = bool(extras.get("thermal_hot", False))
        amb = float(extras.get("ambient_c", tel.get("temperature") or 26))
        live = self.mlx.read()
        if live is not None:
            frame = live
        else:
            frame = synthetic_frame(ambient_c=amb, hot_blob=hot)
        th = self.thermal.process(frame)
        if live is not None:
            th.note = f"{self.mlx.kind} live · " + th.note
        self._vis = vis
        self._th = th
        return vis, th

    def process_telemetry(self, tel: dict, extras: dict | None = None) -> dict:
        extras = extras or {}
        vid = tel["vehicle_id"]
        self.db.upsert_vehicle(vid)
        self.last_ingest_ts = time.time()
        now_db = self.last_ingest_ts
        if now_db - self._db_t >= 0.5:
            self.db.log_telemetry(vid, tel)

        vis, th = self._slow_vision_thermal(tel, extras)

        anom = self.anomaly.update(
            float(tel.get("humidity") or 50),
            float(tel.get("light_level") or 50),
            tel.get("front_distance"),
            bool(tel.get("motion_detected")),
            th.anomaly,
        )

        darkness = self._darkness(int(tel.get("light_level") or 50))
        left_m, right_m = self._hold_us(vid, tel.get("left_distance"), tel.get("right_distance"))
        front_m = self._hold_front(vid, tel.get("front_distance"))
        radar_hit = bool(tel.get("radar_occupied") or tel.get("motion_detected"))
        inp = FuseInput(
            front_m=front_m,
            left_m=left_m,
            right_m=right_m,
            temperature_c=float(tel.get("temperature") or 26),
            humidity_rh=float(tel.get("humidity") or 50),
            darkness_score=darkness,
            visibility_confidence=vis.confidence,
            thermal_anomaly=th.anomaly,
            thermal_risk=th.risk,
            motion_detected=radar_hit,
            lidar_strength=tel.get("lidar_strength"),
            rh_slope_per_min=self._rh_slope(float(tel.get("humidity") or 50)),
            fog_mode_prev=self.fog_mode if vid == config.VEHICLE_ID else False,
        )
        fog_was = self.fog_mode if vid == config.VEHICLE_ID else False
        fused = fuse(inp)
        if vid == config.VEHICLE_ID:
            self.fog_mode = fused.fog_mode

        decision = decide(vid, fused, front_m, left_m, right_m)
        if bool(tel.get("tilt_alert")):
            decision.alerts.insert(0, "TILT ALERT — reduce speed / check dump bed")
            if decision.speed_advice == "NORMAL SPEED":
                decision.speed_advice = "TILT ALERT"
        cab_adv = tel.get("cab_advice")
        if cab_adv == "STOP VEHICLE" and decision.speed_advice != "STOP VEHICLE":
            decision.speed_advice = "STOP VEHICLE"
            decision.hud_color = "red"
        elif cab_adv == "CRAWL MODE" and decision.speed_advice == "NORMAL SPEED":
            decision.speed_advice = "CRAWL MODE"
            decision.hud_color = "orange"
        raw_buzz = str(tel.get("buzzer_state") or "")
        if raw_buzz == "continuous":
            decision.audio = "continuous"
        elif raw_buzz in ("off", "single", "repeated"):
            decision.audio = "off"
        if vid == config.VEHICLE_ID and fused.fog_mode and not fog_was:
            decision.alerts.insert(0, "FOG MODE ACTIVATED")
        if (radar_hit):
            # Ensure control-room alert list always carries the radar presence event.
            human_msg = "HUMAN PRESENCE (24 GHz) — person within 30 cm ahead"
            if human_msg not in decision.alerts and "HIGH CONFIDENCE PRESENCE" not in " ".join(decision.alerts):
                decision.alerts.insert(0, human_msg)
        gps_status = "FIX" if tel.get("gps_valid") else "NO FIX"

        state = {
            "vehicle_id": vid,
            "risk_score": fused.risk_score,
            "risk_level": fused.risk_level,
            "speed_advice": decision.speed_advice,
            "hud_color": decision.hud_color,
            "audio": decision.audio,
            "fog_index": fused.fog.index,
            "fog_label": fused.fog.label,
            "fog_mode": fused.fog_mode,
            "front_distance": front_m,
            "left_distance": left_m,
            "right_distance": right_m,
            "front_zone": fused.front_zone.value,
            "left_zone": fused.left_zone.value,
            "right_zone": fused.right_zone.value,
            "thermal_anomaly": th.anomaly,
            "thermal_max_c": round(th.max_c, 1),
            "thermal_note": th.note,
            "presence": fused.presence,
            "presence_high_confidence": fused.presence_high_confidence,
            "motion_detected": radar_hit,
            "radar_occupied": radar_hit,
            "visibility_confidence": vis.confidence,
            "visibility_label": vis.label,
            "visibility_metrics": {
                "contrast": vis.contrast,
                "edge_density": vis.edge_density,
                "blur": vis.blur_score,
            },
            "temperature": tel.get("temperature"),
            "humidity": tel.get("humidity"),
            "pressure_hpa": tel.get("pressure_hpa"),
            "light_level": tel.get("light_level"),
            "latitude": tel.get("latitude"),
            "longitude": tel.get("longitude"),
            "heading_deg": tel.get("heading_deg"),
            "speed_kmh": tel.get("speed_kmh_gps"),
            "gps_status": gps_status,
            "gps_sats": tel.get("gps_sats"),
            "pitch_deg": tel.get("pitch_deg"),
            "roll_deg": tel.get("roll_deg"),
            "tilt_alert": bool(tel.get("tilt_alert")),
            "local_zone": tel.get("local_zone"),
            "cab_zone": tel.get("local_zone"),
            "buzzer_state": decision.audio,
            "firmware": tel.get("firmware"),
            "thermal_source": self.mlx.kind,
            "vision_source": self.camera.source,
            "vision_note": self.camera.ov_note,
            "left_sensor": "ok" if left_m is not None else "offline",
            "right_sensor": "ok" if right_m is not None else "offline",
            "lidar_sensor": "ok" if front_m is not None else "offline",
            "last_ingest_ts": self.last_ingest_ts,
            "weights": fused.weights,
            "notes": fused.notes,
            "anomaly_label": anom.label,
            "recommended_note": fused.notes[-1] if fused.notes else "",
            "mode": config.MODE,
            "timestamp": tel.get("timestamp"),
        }
        self.vehicles[vid] = state
        self.heatmaps[vid] = th.heatmap_16x12
        if now_db - self._db_t >= 0.5:
            self._db_t = now_db
            self.db.log_fused(vid, state)

        now = time.time()
        fired: set[str] = set()
        for msg in decision.alerts:
            key = re.sub(r"\d+\.\d+", "X", msg)
            fired.add(key)
            if key in self._alert_ack:
                continue
            last = self._alert_seen.get(key, 0)
            if now - last < 12:
                continue
            self._alert_seen[key] = now
            sev = "INFO"
            if "CRITICAL" in msg or "STOP" in msg:
                sev = "CRITICAL"
            elif "HIGH" in msg or "WARNING" in msg or "high-risk" in msg or "HUMAN PRESENCE" in msg:
                sev = "HIGH"
            elif "FOG" in msg:
                sev = "FOG"
            rec = self.db.log_alert(vid, sev, msg)
            self.last_alerts.insert(0, rec)
            self.last_alerts = self.last_alerts[:80]
        self._alert_ack &= fired

        if extras.get("peer"):
            self.ingest_peer(extras["peer"])
        return state

    def clear_alerts(self) -> int:
        n = len(self.last_alerts)
        for rec in self.last_alerts:
            msg = str(rec.get("message") or "")
            self._alert_ack.add(re.sub(r"\d+\.\d+", "X", msg))
        self._alert_ack |= set(self._alert_seen)
        self.last_alerts.clear()
        return n

    def ingest_peer(self, beacon: dict) -> None:
        vid = beacon["vehicle_id"]
        self.db.upsert_vehicle(vid)
        level = str(beacon.get("risk_level", "SAFE")).upper()
        if "CRITICAL" in level:
            score, advice, color = 90, "STOP VEHICLE", "red"
        elif "HIGH" in level:
            score, advice, color = 70, "CRAWL MODE", "orange"
        elif "CAUTION" in level:
            score, advice, color = 45, "REDUCE SPEED", "yellow"
        else:
            score, advice, color = 18, "NORMAL SPEED", "green"
        self.vehicles[vid] = {
            "vehicle_id": vid,
            "risk_score": score,
            "risk_level": level if level in ("SAFE", "CAUTION", "HIGH RISK", "CRITICAL") else (
                "HIGH RISK" if "HIGH" in level else "SAFE" if "SAFE" in level else "CAUTION"
            ),
            "speed_advice": advice,
            "hud_color": color,
            "fog_mode": bool(beacon.get("fog_mode")),
            "fog_index": 75 if beacon.get("fog_mode") else 20,
            "fog_label": "Dense fog risk" if beacon.get("fog_mode") else "Clear",
            "front_distance": None,
            "left_distance": None,
            "right_distance": None,
            "front_zone": "UNKNOWN",
            "thermal_anomaly": False,
            "presence": "EMERGENCY" if beacon.get("emergency") else "PEER",
            "motion_detected": False,
            "visibility_confidence": None,
            "visibility_label": "N/A",
            "temperature": None,
            "humidity": None,
            "light_level": None,
            "latitude": beacon.get("latitude"),
            "longitude": beacon.get("longitude"),
            "heading_deg": beacon.get("direction"),
            "speed_kmh": beacon.get("speed"),
            "gps_status": "FIX",
            "is_peer": True,
            "emergency": bool(beacon.get("emergency")),
            "mode": config.MODE,
            "timestamp": beacon.get("timestamp"),
        }

    async def broadcast(self) -> None:
        snap = {
            "type": "fleet_snapshot",
            "mode": config.MODE,
            "scenario": self.scenario.scenario,
            "uptime_s": int(time.time() - self.started),
            "vehicles": list(self.vehicles.values()),
            "alerts": self.last_alerts[:20],
            "heatmap": self.heatmaps.get(config.VEHICLE_ID, []),
            "last_ingest_age_s": (
                round(time.time() - self.last_ingest_ts, 2) if self.last_ingest_ts else None
            ),
            "esp_link": bool(
                self.last_ingest_ts and (time.time() - self.last_ingest_ts) < 5.0
            ),
            "vision_source": self.camera.source,
            "vision_note": self.camera.ov_note,
            "thermal_source": self.mlx.kind,
        }
        dead = []
        payload = json.dumps(snap)
        for ws in list(self.sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.sockets:
                self.sockets.remove(ws)

    def refresh_pi_sensors(self) -> None:
        """Keep camera / thermal panels alive even when the ESP32 is offline."""
        now = time.time()
        if now - self._slow_t < config.SLOW_SENSORS_S and self.heatmaps.get(config.VEHICLE_ID):
            return
        self._slow_t = now
        gray = self.camera.read_gray(0.0)
        self.last_gray = gray
        vis = visibility_from_gray(gray)
        live = self.mlx.read()
        if live is not None:
            frame = live
            source = self.mlx.kind
        else:
            frame = synthetic_frame(ambient_c=26.0, hot_blob=False)
            source = "synth"
        th = self.thermal.process(frame)
        if live is not None:
            th.note = f"{source} live · " + th.note
        self._vis = vis
        self._th = th
        self.heatmaps[config.VEHICLE_ID] = th.heatmap_16x12

        age = None if not self.last_ingest_ts else now - self.last_ingest_ts
        if age is not None and age < 5.0:
            # ESP is posting — only refresh heatmap / notes on the live vehicle.
            state = self.vehicles.get(config.VEHICLE_ID)
            if state is not None:
                state["thermal_note"] = th.note
                state["thermal_max_c"] = round(th.max_c, 1)
                state["thermal_anomaly"] = th.anomaly
                state["thermal_source"] = self.mlx.kind
                state["vision_source"] = self.camera.source
                state["vision_note"] = self.camera.ov_note
                state["visibility_confidence"] = vis.confidence
                state["visibility_label"] = vis.label
            return

        self.vehicles[config.VEHICLE_ID] = {
            "vehicle_id": config.VEHICLE_ID,
            "risk_score": 12,
            "risk_level": "SAFE",
            "speed_advice": "WAITING FOR ESP32",
            "hud_color": "yellow",
            "audio": "off",
            "fog_index": 0,
            "fog_label": "—",
            "fog_mode": False,
            "front_distance": None,
            "left_distance": None,
            "right_distance": None,
            "front_zone": "UNKNOWN",
            "left_zone": "UNKNOWN",
            "right_zone": "UNKNOWN",
            "thermal_anomaly": th.anomaly,
            "thermal_max_c": round(th.max_c, 1),
            "thermal_note": th.note,
            "presence": "CLEAR",
            "motion_detected": False,
            "radar_occupied": False,
            "visibility_confidence": vis.confidence,
            "visibility_label": vis.label,
            "temperature": None,
            "humidity": None,
            "light_level": None,
            "latitude": None,
            "longitude": None,
            "gps_status": "NO ESP",
            "gps_sats": 0,
            "pitch_deg": None,
            "roll_deg": None,
            "tilt_alert": False,
            "firmware": None,
            "thermal_source": self.mlx.kind,
            "vision_source": self.camera.source,
            "vision_note": self.camera.ov_note,
            "left_sensor": "offline",
            "right_sensor": "offline",
            "lidar_sensor": "offline",
            "notes": [
                "ESP32 not posting to /api/v1/ingest",
                "Pi camera + thermal are live — join ESP to this Wi-Fi",
                f"Gateway: {LAN_NAME}.local:{config.PORT}",
            ],
            "recommended_note": "Power ESP32 hub on the same Wi-Fi as this Pi",
            "mode": config.MODE,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "is_peer": False,
        }


hub = Hub()


async def sim_loop() -> None:
    while True:
        if config.MODE == "sim":
            tel, extras = hub.scenario.tick()
            hub.process_telemetry(tel.to_dict(), extras)
        else:
            hub.refresh_pi_sensors()
        await hub.broadcast()
        await asyncio.sleep(1.0 / config.WS_HZ)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(
        "Pi thermal:",
        hub.mlx.kind,
        "I2C1 SDA=pin3/GPIO2 SCL=pin5/GPIO3 addr 0x33",
    )
    print("Pi vision:", hub.camera.source, hub.camera.ov_note)
    print("Pi TFT:", hub.tft.note)
    print("Pi mDNS:", hub.lan.note)
    for url in dashboard_urls(config.PORT):
        print("  dashboard:", url)
    task = asyncio.create_task(sim_loop())
    yield
    hub.lan.stop()
    hub.tft.close()
    task.cancel()


app = FastAPI(
    title="MineVision Guardian API",
    version="1.0.0",
    description="NMDC / SIH 26007 command dashboard backend",
    lifespan=lifespan,
)

if DASHBOARD.exists():
    app.mount("/static", StaticFiles(directory=DASHBOARD / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(DASHBOARD / "index.html")


@app.get("/api/v1/health")
def health():
    age = None
    if hub.last_ingest_ts:
        age = round(time.time() - hub.last_ingest_ts, 2)
    primary = hub.vehicles.get(config.VEHICLE_ID) or {}
    return {
        "ok": True,
        "mode": config.MODE,
        "uptime_s": int(time.time() - hub.started),
        "vehicles": list(hub.vehicles.keys()),
        "last_ingest_age_s": age,
        "firmware": primary.get("firmware"),
        "thermal_source": hub.mlx.kind,
        "vision_source": hub.camera.source,
        "ov7670": hub.camera.ov_note or None,
        "st7735": hub.tft.note if getattr(hub, "tft", None) else None,
        "gc9a01": hub.tft.note if getattr(hub, "tft", None) else None,
        "hostname": host_stem(),
        "lan_name": f"{LAN_NAME}.local",
        "addresses": ipv4_addrs(),
        "urls": dashboard_urls(config.PORT),
        "mdns": hub.lan.note if getattr(hub, "lan", None) else None,
    }


@app.get("/api/v1/camera.jpg")
@app.get("/api/v1/camera.png")
def camera_image():
    data, mime = hub.camera.preview_image()
    return Response(
        content=data,
        media_type=mime,
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/v1/fleet")
def fleet():
    return {"vehicles": list(hub.vehicles.values()), "alerts": hub.last_alerts[:20]}


@app.get("/api/v1/vehicles/{vehicle_id}")
def vehicle(vehicle_id: str):
    return hub.vehicles.get(vehicle_id) or {"error": "unknown vehicle"}


@app.post("/api/v1/ingest")
def ingest(body: Esp32Telemetry):
    state = hub.process_telemetry(body.model_dump())
    return {"ok": True, "risk_score": state["risk_score"], "risk_level": state["risk_level"]}


@app.post("/api/v1/v2v")
def v2v(body: V2VBeacon):
    hub.ingest_peer(body.model_dump())
    return {"ok": True}


@app.get("/api/v1/alerts")
def alerts(limit: int = 50):
    return hub.db.recent_alerts(limit)


@app.post("/api/v1/alerts/clear")
def clear_alerts():
    n = hub.clear_alerts()
    return {"ok": True, "cleared": n}


@app.get("/api/v1/history/risk")
def history_risk(vehicle_id: str = "DUMPER_01", minutes: int = 30):
    return hub.db.history_risk(vehicle_id, minutes)


@app.get("/api/v1/history/fog")
def history_fog(vehicle_id: str = "DUMPER_01", minutes: int = 30):
    rows = hub.db.history_risk(vehicle_id, minutes)
    return [{"timestamp": r["timestamp"], "fog_index": r["fog_index"]} for r in rows]


@app.get("/api/v1/history/alerts_count")
def alerts_count(minutes: int = 60):
    return hub.db.alert_counts(minutes)


@app.post("/api/v1/demo/scenario")
def demo_scenario(body: ScenarioBody):
    hub.scenario.set_scenario(body.scenario)
    return {"ok": True, "scenario": body.scenario}


@app.get("/api/v1/config")
def get_config():
    return {
        "safe_m": config.SAFE_M,
        "warn_m": config.WARN_M,
        "buzz_m": config.DANGER_FRONT_M,
        "danger_front_m": config.DANGER_FRONT_M,
        "danger_side_m": config.DANGER_SIDE_M,
        "fog_enter": config.FOG_ENTER,
        "fog_exit": config.FOG_EXIT,
        "weights_clear": config.WEIGHTS_CLEAR,
        "weights_fog": config.WEIGHTS_FOG,
        "mode": config.MODE,
        "map_center": [config.MAP_CENTER_LAT, config.MAP_CENTER_LON],
        "lidar_min_m": config.LIDAR_MIN_M,
        "us_min_m": config.US_MIN_M,
    }


@app.post("/api/v1/config/thresholds")
def set_thresholds(body: ThresholdBody):
    if body.safe_m is not None:
        config.SAFE_M = float(body.safe_m)
    if body.warn_m is not None:
        config.WARN_M = float(body.warn_m)
    if body.danger_front_m is not None:
        config.DANGER_FRONT_M = float(body.danger_front_m)
        config.BUZZ_M = config.DANGER_FRONT_M
    elif body.buzz_m is not None:
        config.DANGER_FRONT_M = float(body.buzz_m)
        config.BUZZ_M = config.DANGER_FRONT_M
    if body.danger_side_m is not None:
        config.DANGER_SIDE_M = float(body.danger_side_m)
    if body.fog_enter is not None:
        config.FOG_ENTER = int(body.fog_enter)
    if body.fog_exit is not None:
        config.FOG_EXIT = int(body.fog_exit)
    return get_config()


@app.get("/api/v1/thermal/{vehicle_id}")
def thermal(vehicle_id: str):
    return {
        "heatmap": hub.heatmaps.get(vehicle_id, []),
        "state": hub.vehicles.get(vehicle_id, {}),
    }


@app.websocket("/ws/fleet")
async def ws_fleet(ws: WebSocket):
    await ws.accept()
    hub.sockets.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in hub.sockets:
            hub.sockets.remove(ws)
