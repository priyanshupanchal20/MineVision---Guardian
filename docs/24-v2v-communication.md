# Vehicle-to-vehicle (V2V) prototype

## Current hardware

One ESP32-S3. A second physical ESP32 is optional. This repo always runs a **software DUMPER_02** so judges see two icons without extra silicon.

## Packet (≤ 250 bytes for ESP-NOW)

```json
{
  "vehicle_id": "DUMPER_01",
  "latitude": 18.72012,
  "longitude": 81.23045,
  "speed": 12.0,
  "direction": 120,
  "risk_level": "HIGH",
  "fog_mode": true,
  "emergency": false,
  "timestamp": "2026-09-08T16:30:00Z"
}
```

Broadcast period: 1 Hz. On CRITICAL, 5 Hz and `emergency: true`.

ESP-NOW is connectionless, same Wi-Fi channel as the STA interface. Firmware `lib/V2V` sends; Pi ingests via `POST /api/v1/v2v` if a companion node forwards, or the sim loop injects DUMPER_02.

## How to add a second ESP32 later

Flash the same firmware with `VEHICLE_ID DUMPER_02`. Peer MAC can be `ff:ff:ff:ff:ff:ff` broadcast. No router required for the beacon; ingest to Pi still needs IP if you want the dashboard.

## Production radios (not this PCB)

- **LoRa/LoRaWAN** — long range, low rate, good for heartbeat / emergency bit, bad for 10 Hz tracks.
- **Private 5G** — haul-road QoS, cameras, high-rate tracks.
- **Wi-Fi mesh** — cheaper, worse mobility and interference.
- **Industrial V2X (C-V2X / DSRC)** — standardised CAM/DENM-like messages, the correct long-term HEMM choice.

GPS error means V2V **must not** close collision from positions alone. Use ranging sensors for close-in; use V2X for “I am in fog / I stopped / I am on this chainage”.
