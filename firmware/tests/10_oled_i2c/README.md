# 1.30" IIC V2.2 OLED (SH1106 128×64)

Your module silk, left → right: **VCC GND SCK SDA**. SCK is I2C clock (SCL), not SPI.

| OLED | YD-ESP32-S3 |
|---|---|
| VCC | **3V3** |
| GND | GND |
| SCK | **GPIO9** (same SCL as BME280) |
| SDA | **GPIO8** (same SDA as BME280) |

Address **0x3C** (sometimes 0x3D). Shares I2C0 with BME280. Do **not** use pads 17/18.

Library: U8g2, constructor `U8G2_SH1106_128X64_NONAME_F_HW_I2C`. If the picture is shifted by about two pixels, the chip is SSD1306 — set `OLED_IS_SH1106` to `0` in `firmware/include/config.h`.
