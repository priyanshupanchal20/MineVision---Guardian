# MPU-6050 test — YD-ESP32-S3 (own pins, not BME280)

Pads **8** and **9** stay on the BME280. MPU-6050 uses a second I2C bus.

| MPU-6050 | Board pad | GPIO |
|---|---|---|
| VCC | **3V3** | — |
| GND | **GND** | — |
| SDA | **17** | 17 |
| SCL | **18** | 18 |
| AD0 | **GND** → `0x68` | — |
| INT | unused | optional 7 |
| XDA / XCL | not connected | — |

Library: Adafruit MPU6050. Expected: `az` ≈ 1 g when flat.
