# Sample JSON messages

## ESP32 → Pi ingest (`POST /api/v1/ingest`)

```json
{
  "vehicle_id": "DUMPER_01",
  "front_distance": 8.2,
  "left_distance": 5.1,
  "right_distance": 6.3,
  "lidar_strength": 312,
  "temperature": 24.5,
  "humidity": 91.0,
  "pressure_hpa": 1008.2,
  "light_level": 35,
  "light_raw": 1420,
  "motion_detected": true,
  "radar_distance_m": 3.4,
  "radar_occupied": true,
  "latitude": 18.72012,
  "longitude": 81.23045,
  "gps_valid": true,
  "gps_sats": 8,
  "speed_kmh_gps": 12.0,
  "heading_deg": 120,
  "local_zone": "SAFE",
  "buzzer_state": "off",
  "firmware": "1.4.0",
  "timestamp": "2026-09-08T16:30:00Z"
}
```

## V2V beacon

```json
{
  "vehicle_id": "DUMPER_02",
  "latitude": 18.72080,
  "longitude": 81.23110,
  "speed": 18.0,
  "direction": 300,
  "risk_level": "HIGH",
  "fog_mode": true,
  "emergency": false,
  "timestamp": "2026-09-08T16:30:01Z"
}
```

## Fused vehicle_state (dashboard / GET vehicle)

```json
{
  "vehicle_id": "DUMPER_01",
  "risk_score": 74,
  "risk_level": "HIGH RISK",
  "speed_advice": "CRAWL MODE",
  "fog_index": 78,
  "fog_label": "Dense fog risk",
  "fog_mode": true,
  "front_distance": 5.4,
  "left_distance": 4.8,
  "right_distance": 6.1,
  "front_zone": "WARNING",
  "thermal_anomaly": true,
  "thermal_max_c": 34.2,
  "presence": "HIGH CONFIDENCE PRESENCE",
  "motion_detected": true,
  "visibility_confidence": 0.22,
  "visibility_label": "POOR",
  "temperature": 24.5,
  "humidity": 94.0,
  "light_level": 18,
  "latitude": 18.72012,
  "longitude": 81.23045,
  "gps_status": "FIX",
  "recommended_note": "FOG SAFETY MODE — LiDAR/radar/thermal prioritized"
}
```

## Alert

```json
{
  "id": 184,
  "severity": "CRITICAL",
  "vehicle_id": "DUMPER_01",
  "message": "CRITICAL: Obstacle detected 2.5 meters ahead of DUMPER_01",
  "timestamp": "2026-09-08T16:31:04Z"
}
```
