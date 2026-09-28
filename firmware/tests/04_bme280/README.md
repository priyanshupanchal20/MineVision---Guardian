# BME280 test — YD-ESP32-S3

I2C is **not** crossed. Do not use silk TX/RX (LiDAR).

| BME280 | Board pad | GPIO |
|---|---|---|
| VCC / VIN | **3V3** | — |
| GND | **GND** | — |
| SDA | **8** | 8 |
| SCL | **9** | 9 |
| SDO | GND → `0x76`, 3V3 → `0x77` | firmware tries both |
| CSB if present | 3V3 (I2C mode) | — |

Library: Adafruit BME280 + Unified Sensor.

Expected: room temperature, RH 30–70 %, P ~1013 hPa. Breath on the sensor → RH rises.

Fail: 5 V on a 3.3 V-only board; SDA/SCL swapped; CSB left floating in SPI mode.
