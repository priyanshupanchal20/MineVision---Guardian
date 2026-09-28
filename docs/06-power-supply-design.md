# Power supply design

## Budget (typical, all sensors active)

| Load | Voltage | Current (typ / peak) | Notes |
|---|---|---|---|
| ESP32-S3 Wi-Fi TX | 5 V (onboard 3.3 V LDO) | 80 / 240 mA | peaks on beacon |
| TFMini-S | 5 V | 140 / 180 mA | |
| HC-SR04 × 2 | 5 V | 15 / 30 mA | |
| S3KM1110 | 3.3 V | 70 / 90 mA | |
| BME280 | 3.3 V | < 1 mA | |
| LDR module | 3.3 V | 5 mA | |
| NEO-6M | 5 V or 3.3 V | 45 / 67 mA | acquisition higher |
| LEDs + buzzer | 3.3 V | 40 / 80 mA | |
| Raspberry Pi 3 B | 5 V | 400 / 800 mA | HDMI + Wi-Fi + USB cam |
| MLX90640 | 3.3 V from Pi | 23 mA | |
| USB webcam | 5 V via Pi | 100 / 200 mA | |
| **Total** | **5 V** | **~0.95 A typ / ~1.8 A peak** | |

## Recommended supply

**Minimum:** regulated **5.0 V, 3 A** USB-C PD power bank or bench PSU.  
**On an RC body:** 3S LiPo → **5 V 3 A buck** (e.g. mini560) with ≥ 470 µF low-ESR on the 5 V rail.

Do **not** power the Pi from the ESP32 5 V pin. Give the Pi its official 5 V barrel / USB and share **GND only**, *or* feed both from the same 3 A buck with thick wires.

## Rails

```
[5 V 3 A]──┬── Raspberry Pi 3 (polyfuse already on board)
            ├── ESP32-S3 5V pin
            ├── TFMini-S VIN
            └── HC-SR04 VCC (both)

ESP32 3V3──┬── BME280
            ├── LDR
            └── S3KM1110 3V3   (if current allows; else a dedicated AMS1117-3.3 from 5 V)

Pi 3V3 ────── MLX90640
```

If the radar browns out when Wi-Fi transmits, move S3KM1110 to its own AMS1117 from the 5 V rail (still 3.3 V out, extra decoupling 100 µF).

## Decoupling

- 100 nF ceramic at every module VCC, close to the pin.
- 100–220 µF electrolytic on ESP32 5 V.
- 470 µF on the shared 5 V barrel.

## Inrush / safety

- Common GND first, then 5 V.
- Never hot-plug LiDAR TX into a live UART while 5 V is connected without GND.
- Add a 1 A polyfuse on the sensor 5 V spur so a shorted ultrasonic does not reset the Pi.
- Prototype is **not** IS (intrinsically safe) and **not** flameproof. Real NMDC pit electrics need certified enclosures.

## Runtime estimate (20 000 mAh 5 V bank)

At 1.2 A average: ≈ **12–14 hours** of demo. Enough for SIH day with margin.
