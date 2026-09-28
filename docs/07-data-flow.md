# Data flow diagram

```mermaid
flowchart TD
  subgraph ESP["ESP32-S3 10 ms tick"]
    R1[Read LiDAR frame]
    R2[Ping ultrasonics staggered]
    R3[Poll BME280 2 Hz]
    R4[ADC LDR]
    R5[Parse NMEA]
    R6[Parse mmWave report]
    Z[Local zone + buzzer/LED]
    J[Build telemetry JSON]
    R1 --> Z --> J
    R2 --> Z
    R3 --> J
    R4 --> J
    R5 --> J
    R6 --> Z
  end

  J -->|HTTP POST 5 Hz| ING[/api/v1/ingest/]
  J -->|ESP-NOW 1 Hz| V2V[Peer vehicles]

  subgraph PI["Raspberry Pi / Windows sim"]
    ING --> VAL[Validate + stamp]
    TH[MLX90640 matrix]
    CAM[Camera frame]
    TH --> TA[Thermal clusters]
    CAM --> VI[Contrast / blur / edges]
    VAL --> FUSE
    TA --> FUSE[Weighted fusion]
    VI --> FUSE
    V2V --> FUSE
    FUSE --> FOG[Fog Risk Index]
    FUSE --> RS[Mine Safety Risk Score]
    FOG --> DE[Decision engine]
    RS --> DE
    DE --> DB[(SQLite)]
    DE --> WS[WebSocket broadcast]
  end

  WS --> UI[Command dashboard]
```

## JSON cadence

| Message | Hz | Path |
|---|---|---|
| ESP32 telemetry | 5 | `POST /api/v1/ingest` |
| Thermal snapshot | 2 | internal, then folded into state |
| Visibility metrics | 1 | internal |
| Fused `vehicle_state` | 5 | WebSocket `/ws/fleet` |
| V2V beacon | 1 | ESP-NOW / sim |
| Alert events | on edge | REST + WS `alert` |

## Backpressure

If Wi-Fi drops, ESP32 keeps a ring buffer of the last 20 danger events and retries. The Pi marks `link: degraded` after 2 s without ingest and raises CAUTION (not CRITICAL) for comms loss — comms loss is not an obstacle.
