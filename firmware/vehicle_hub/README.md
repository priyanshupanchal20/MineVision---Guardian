# ESP32-S3 integrated vehicle hub

**Preferred:** PlatformIO project in `firmware/` (`src/main.cpp`).

Arduino IDE: install ESP32 3.x, board ESP32S3 Dev Module, 16 MB flash, OPI PSRAM, libraries listed in `docs/18-installation.md`. Copy `include/config.h` into a sketch folder named `vehicle_hub` together with the contents of `src/main.cpp` renamed to `vehicle_hub.ino` (remove the `.cpp` include wrapper).

Local safety (LED + buzzer) runs **without Wi-Fi**. Buzzer is **continuous only when LiDAR < 1.5 m or left/right ultrasonic < 1.0 m**. Above those, that channel is not DANGER. JSON prints on Serial at 115200. HTTP POST to `http://GATEWAY_HOST:8000/api/v1/ingest` when associated.

Copy `include/secrets.h.example` → `include/secrets.h` before field use.
