# OV7670 — Raspberry Pi 3 B+ (not ESP32)

The ESP32-S3 has no free DVP pins (LiDAR, GPS, BME280, MPU, ultrasonics, radar already occupy them).  
MLX9064X already owns Pi I2C1 (pins 1 / 3 / 5 / 6). This map **avoids those**.

**3.3 V only. Never Pi pins 2 or 4 (5 V).**

Count GPIO J8 from the **left** (DISPLAY / SD-card end), USB ports on the right.

- **Inner row** (towards the chips) = 1, 3, 5, 7, 9…  
- **Outer row** (board edge) = 2, 4, 6, 8, 10…

| OV7670 pin | Pi physical pin | Row / count from left | BCM |
|---|---|---|---|
| 3.3V / VCC | **17** | Inner, 9th | 3V3 (leave pin 1 for MLX) |
| GND | **9** | Inner, 5th | GND |
| SIOD (SDA) | **19** | Inner, 10th | GPIO10 |
| SIOC (SCL) | **23** | Inner, 12th | GPIO11 |
| XCLK | **7** | Inner, 4th | GPIO4 |
| PCLK | **15** | Inner, 8th | GPIO22 |
| VSYNC | **13** | Inner, 7th | GPIO27 |
| HREF / **HS** | **11** | Inner, 6th | GPIO17 |
| RESET / **RET** | **18** | Outer, 9th | GPIO24 |
| PWDN | **16** | Outer, 8th | GPIO23 |
| D0 | **29** | Inner, 15th | GPIO5 |
| D1 | **31** | Inner, 16th | GPIO6 |
| D2 | **33** | Inner, 17th | GPIO13 |
| D3 | **35** | Inner, 18th | GPIO19 |
| D4 | **37** | Inner, 19th | GPIO26 |
| D5 | **36** | Outer, 18th | GPIO16 |
| D6 | **38** | Outer, 19th | GPIO20 |
| D7 | **40** | Outer, 20th | GPIO21 |

If your module is labelled **HS** instead of HREF: that **is** HREF (horizontal sync). Wire **HS → pin 11**.  
If it is labelled **VS** instead of VSYNC: that **is** VSYNC. Wire **VS → pin 13**.  
If it is labelled **RET** or **RST** instead of RESET: that **is** RESET. Wire **RET → pin 18**.  
If it is labelled **D2–D9** instead of D0–D7: treat D2 as D0 … D9 as D7 (same eight wires as above).

SCCB address `0x21`. XCLK must be ~8–24 MHz (GPIO4 GPCLK). Pi 3 bit-banged DVP is slow and fragile.

Live visibility uses this OV7670 map (no USB camera). On the Pi: `sudo pigpiod`, SPI off, then `python raspberry_pi/scripts/probe_pi_cameras.py`.

```powershell
cd raspberry_pi
python -c "from minevision.vision import synthetic_scene, visibility_from_gray; print(visibility_from_gray(synthetic_scene(0.1))); print(visibility_from_gray(synthetic_scene(0.9)))"
```
