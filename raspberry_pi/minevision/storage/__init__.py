"""SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from minevision import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id   TEXT PRIMARY KEY,
    display_name TEXT,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telemetry (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id   TEXT NOT NULL,
    ts           TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fused_state (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id   TEXT NOT NULL,
    ts           TEXT NOT NULL,
    risk_score   INTEGER NOT NULL,
    fog_index    INTEGER NOT NULL,
    fog_mode     INTEGER NOT NULL,
    front_m      REAL,
    left_m       REAL,
    right_m      REAL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id TEXT NOT NULL,
    ts         TEXT NOT NULL,
    severity   TEXT NOT NULL,
    message    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vehicle_path (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id TEXT NOT NULL,
    ts         TEXT NOT NULL,
    latitude   REAL NOT NULL,
    longitude  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fused_ts ON fused_state(vehicle_id, ts);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
CREATE INDEX IF NOT EXISTS idx_path_ts ON vehicle_path(vehicle_id, ts);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = str(path or config.DB_PATH)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()

    def upsert_vehicle(self, vehicle_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO vehicles(vehicle_id, display_name, created_at) VALUES (?,?,?)",
                (vehicle_id, vehicle_id, _now()),
            )
            self._conn.commit()

    def log_telemetry(self, vehicle_id: str, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO telemetry(vehicle_id, ts, payload_json) VALUES (?,?,?)",
                (vehicle_id, _now(), json.dumps(payload)),
            )
            self._conn.commit()

    def log_fused(self, vehicle_id: str, fused: dict) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO fused_state(
                    vehicle_id, ts, risk_score, fog_index, fog_mode, front_m, left_m, right_m, payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    vehicle_id,
                    _now(),
                    fused.get("risk_score", 0),
                    fused.get("fog_index", 0),
                    1 if fused.get("fog_mode") else 0,
                    fused.get("front_distance"),
                    fused.get("left_distance"),
                    fused.get("right_distance"),
                    json.dumps(fused),
                ),
            )
            lat, lon = fused.get("latitude"), fused.get("longitude")
            if lat is not None and lon is not None:
                self._conn.execute(
                    "INSERT INTO vehicle_path(vehicle_id, ts, latitude, longitude) VALUES (?,?,?,?)",
                    (vehicle_id, _now(), lat, lon),
                )
            self._conn.commit()

    def log_alert(self, vehicle_id: str, severity: str, message: str) -> dict:
        ts = _now()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alerts(vehicle_id, ts, severity, message) VALUES (?,?,?,?)",
                (vehicle_id, ts, severity, message),
            )
            self._conn.commit()
            aid = cur.lastrowid
        return {
            "id": aid,
            "vehicle_id": vehicle_id,
            "timestamp": ts,
            "severity": severity,
            "message": message,
        }

    def recent_alerts(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, vehicle_id, ts, severity, message FROM alerts ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "vehicle_id": r["vehicle_id"],
                "timestamp": r["ts"],
                "severity": r["severity"],
                "message": r["message"],
            }
            for r in rows
        ]

    def history_risk(self, vehicle_id: str, minutes: int = 30) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT ts, risk_score, fog_index, front_m FROM fused_state
                   WHERE vehicle_id=? ORDER BY id DESC LIMIT ?""",
                (vehicle_id, minutes * 60),
            ).fetchall()
        rows = list(reversed(rows))
        return [
            {"timestamp": r["ts"], "risk_score": r["risk_score"], "fog_index": r["fog_index"], "front_m": r["front_m"]}
            for r in rows
        ]

    def alert_counts(self, minutes: int = 60) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT severity, COUNT(*) c FROM alerts GROUP BY severity"
            ).fetchall()
        return {r["severity"]: r["c"] for r in rows}
