# API documentation

Base URL: `http://<host>:8000`

Interactive OpenAPI: `http://<host>:8000/docs`

All timestamps are UTC ISO-8601. Vehicle IDs are strings such as `DUMPER_01`.

## REST

### `GET /api/v1/health`

Returns process status, mode (`sim`|`live`), uptime.

### `GET /api/v1/fleet`

Current fused state of every known vehicle.

### `GET /api/v1/vehicles/{vehicle_id}`

Single vehicle fused document (see sample JSON).

### `POST /api/v1/ingest`

ESP32 telemetry. Body: `Esp32Telemetry` schema. Returns `{ "ok": true, "risk_score": ... }`.

### `POST /api/v1/v2v`

Peer beacon (hardware ESP-NOW bridge or simulator).

### `GET /api/v1/alerts?limit=50`

Newest safety events first.

### `GET /api/v1/history/risk?vehicle_id=DUMPER_01&minutes=30`

Time series for charts.

### `GET /api/v1/history/fog?minutes=30`

Fog index history.

### `GET /api/v1/history/alerts_count?minutes=60`

Counts by severity.

### `POST /api/v1/demo/scenario`

```json
{ "scenario": 1 }
```

`scenario` ∈ `1..5` or `0` to return to free-running sim. `idle` stops injects.

### `POST /api/v1/config/thresholds`

Update `safe_m`, `warn_m`, `fog_enter`, `fog_exit` at runtime (prototype only).

### `GET /api/v1/thermal/{vehicle_id}`

16×12 heatmap + cluster summary.

### `GET /api/v1/config`

Current thresholds and weights.

## WebSocket `GET /ws/fleet`

Server pushes JSON every ~200 ms:

```json
{
  "type": "fleet_snapshot",
  "vehicles": [ ],
  "alerts": [ ]
}
```

Event messages:

```json
{ "type": "alert", "alert": { } }
```

## Authentication

Prototype: none (private Wi-Fi). Production: mTLS + operator SSO. Do not expose `:8000` to the public internet.
