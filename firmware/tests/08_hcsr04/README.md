# HC-SR04 × 2 — YD-ESP32-S3

GPIO **14 is not on this board**. Left echo is pad **7**.

Make **two** dividers. Never connect ECHO straight to the ESP32.

```
ECHO (5V) ---- 2.2 kΩ ----+---- GPIO
                          |
                        3.3 kΩ
                          |
                         GND
```

| Sensor | Pin | Board pad |
|---|---|---|
| Left + Right | VCC | **5Vin** |
| Left + Right | GND | **GND** |
| Left | TRIG | **13** |
| Left | ECHO | **7** via divider |
| Right | TRIG | **21** |
| Right | ECHO | **47** via divider |
