# Wiring — YD-ESP32-S3 (your board)

Silk **TX / RX** = GPIO43 / GPIO44 = **TFMini-S only**. GPS uses **15 / 16**.

```
YD-ESP32-S3  N16R8  V1120 2022-V1.3

TFMini-S  5Vin/GND
  green TX  ->  board RX   (GPIO44)
  white RX  ->  board TX   (GPIO43)
  Serial logs: USB-OTG  (not COM)

GPS  (do NOT use TX/RX)
  TX -> GPIO15
  RX -> GPIO16

BME280  (do NOT use TX/RX)
  VIN -> 3V3
  GND -> GND
  SDA -> pad 8
  SCL -> pad 9

MPU-6050  (NOT pads 8/9 — those are BME280)
  VCC -> 3V3
  GND -> GND
  SDA -> pad 17
  SCL -> pad 18
  AD0 -> GND   (address 0x68)


HLK-LD2420 radar (3V3 only): OT1->12  OT2->14  RX unused
  Human presence (walk OR stand): firmware uses the stable OUT pin (OT2 on new FW, OT1 on old), ignores UART TX chatter.
  Radar does not stop motors by itself — LiDAR/US DANGER still owns the brake.
LDR    3V3 A0 4
US L   5Vin  TRIG 13  ECHO 7  *divider*
US R   5Vin  TRIG 21  ECHO 47 *divider*
LED G1 Y2 R42 FOG41   BUZZ 6
DRIVE STOP  GPIO5 → Arduino Uno D3   (HIGH = DANGER, Uno cuts L298N)
            common GND with Uno

1.30" IIC OLED  (front silk VCC GND SCK SDA)
  VCC -> 3V3
  GND -> GND
  SCK -> pad 9   (same SCL as BME280)
  SDA -> pad 8   (same SDA as BME280)
  NOT pads 17/18 (MPU)
  address 0x3C (or 0x3D)

NEVER: 19 20 35 36 37 0 45 46
```

Raspberry Pi 3 — MLX9064X (NOT on the ESP32)
```
VIN -> Pi pin 1  (3V3)     never pin 2/4 (5V)
GND -> Pi pin 6
SDA -> Pi pin 3  (GPIO2)
SCL -> Pi pin 5  (GPIO3)
Address 0x33     sudo i2cdetect -y 1
```

Raspberry Pi 3 — OV7670 (NOT on the ESP32, do not steal MLX pins 1/3/5/6)
```
3V3  -> Pi pin 17
GND  -> Pi pin 9
SIOD -> Pi pin 19  (GPIO10)
SIOC -> Pi pin 23  (GPIO11)
XCLK -> Pi pin 7   (GPIO4)
PCLK -> Pi pin 15  (GPIO22)
VSYNC-> Pi pin 13  (GPIO27)
HREF/HS -> Pi pin 11  (GPIO17)   HS = HREF on this module
RESET/RET -> Pi pin 18  (GPIO24)   RET = RESET on this module
PWDN -> Pi pin 16  (GPIO23)
D0..D7 -> pins 29,31,33,35,37,36,38,40
```

Raspberry Pi 3 — 1.28" GC9A01 round TFT (silk RST CS DC SDA SCL GND VCC)
Do NOT use hardware SPI0 (pins 19/23) — those are OV7670 SIOD/SIOC.
Do NOT steal MLX pins 1/3/5/6. Common GND with the Pi is required.
```
VCC -> Pi pin 2   (5V, display only — onboard LDO)
GND -> Pi pin 14
SCL -> Pi pin 12  (GPIO18)   clock
SDA -> Pi pin 32  (GPIO12)   MOSI / data (not I2C)
DC  -> Pi pin 22  (GPIO25)
CS  -> Pi pin 24  (GPIO8)
RST -> Pi pin 26  (GPIO7)
```
Leave BLK/LED unconnected if the board has no extra backlight pin.
Hub shows OV7670 on the top half and MLX90640 ironbow on the bottom half.

Judge demo: USB webcam on any Pi USB port is the reliable path.

Full atlas: `hardware/wiring-diagrams.html`
