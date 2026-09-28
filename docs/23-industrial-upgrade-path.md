# Real-world industrial-grade upgrade path

| Prototype | Industrial deployment |
|---|---|
| TFMini-S (~12 m ToF) | Long-range automotive / industrial LiDAR (e.g. 80–200 m, multi-echo, IP67) |
| HC-SR04 | Automotive ultrasonic park-aid class or short-range 77 GHz corner radar |
| NEO-6M | Dual-band RTK/DGPS GNSS + industrial IMU, base station on pit rim |
| ESP32-S3 Wi-Fi + ESP-NOW | Private 5G / C-V2X / industrial Wi-Fi 6 mesh; LoRaWAN for slow telemetry |
| MLX90640 32×24 | Calibrated industrial thermal camera (higher resolution, radiometric) |
| OV7670 / USB webcam | Automotive HDR camera + lens heater / washer, or skip RGB in fog and keep radar/LiDAR |
| BME280 + LDR | Forward-scatter visibility sensor + AWS weather |
| S3KM1110 24 GHz presence | 77/79 GHz automotive radar with tracked objects, or 60 GHz in-cabin occupant |
| Raspberry Pi 3 1 GB | Industrial edge AI IPC, -20–70 °C, conformal coat, watchdog PLC |
| FastAPI on one Pi | HA pair in control room, MQTT/Kafka bus, historian |
| SQLite | PostgreSQL + Timescale |
| Browser HUD | Cab-certified display, sunlight readable, CAN/J1939 interface |
| Piezo buzzer | ISO-style acoustic + seat vibration HMI, alarm management standard |
| Jumper wires | M12 connectors, shielded CAN/Ethernet, fused channels |
| Table RC dumper | OEM-supported sensor mast, vibration isolation, maintenance hatch |

## Safety process upgrade

Prototype software is **not** SIL-rated. Production needs: requirements traceability, independent E-stop, watchdogs, FMEA, cybersecurity (IEC 62443), and **never** silent actuation. First years should remain **advisory**.

## What we would keep

The **idea** of weighted fusion that *degrades RGB in fog and promotes LiDAR/radar/thermal*, Fog Safety Mode hysteresis, control-room alerting, and V2V risk beacons. Those transfer. The specific chips do not.
