# Database schema (SQLite prototype → PostgreSQL production)

File: `data/minevision.db` (created at runtime).

```sql
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
```

Production: PostgreSQL 16, Timescale hypertables on `fused_state` and `telemetry`, retention 90 days raw / 2 years rollup. Connection string via env, never in git.
