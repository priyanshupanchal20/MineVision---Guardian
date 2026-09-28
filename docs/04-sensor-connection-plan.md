# Exact sensor-to-controller connection plan

Board assumed: **ESP32-S3-DevKitC-1 class Dual USB-C** with **WROOM-1-N16R8** (16 MB flash, 8 MB **octal** PSRAM).  
Raspberry Pi: **3 Model B**, 40-pin header, I2C1 enabled.

## Pins you must never wire on this ESP32-S3

| GPIO | Why |
|---|---|
| 19, 20 | Native USB D− / D+ (second Type-C) |
| 35, 36, 37 | Octal PSRAM on N16R8 — **do not use** |
| 43, 44 | USB-UART bridge TX/RX (first Type-C console) |
| 26–32 | Flash on some modules; leave unused |
| 45, 46 | Strapping; leave floating unless you know the boot mode |
| 0 | BOOT button |

Debug console stays on the USB-UART port. Sensor UARTs use UART0/1/2 **re-mapped** onto free GPIOs. Native USB CDC can also print logs if you open the second Type-C.

## ESP32-S3 wiring

### TFMini-S (UART0, 115200) — silkscreen TX / RX

On **YD-ESP32-S3** (V1120 / 2022-V1.3) the pads labelled **TX** and **RX** are GPIO43 and GPIO44. They are **already used by TFMini-S**. Do not put GPS or radar on them.

| TFMini-S wire | YD-ESP32-S3 pad | GPIO | Rail |
|---|---|---|---|
| Red +5V | 5Vin | — | 5 V |
| Black GND | GND | — | GND |
| Green TX | **RX** | **44** (UART0 RX) | 3.3 V logic |
| White RX | **TX** | **43** (UART0 TX) | 3.3 V logic |

Use the **USB-OTG** Type-C for Serial Monitor. The **COM** Type-C is hard-wired to the same TX/RX pads and will collide with the LiDAR.

Benewake logic is 3.3 V. Do not put 5 V on RX.

### NEO-6M GPS (UART2, 9600)

**Not** the silkscreen TX/RX (those are the LiDAR). Use numbered **15** and **16**.

| NEO-6M | ESP32-S3 | Rail |
|---|---|---|
| VCC | 5V or 3V3 as labelled on **your** module | See module |
| GND | GND | GND |
| TX | **GPIO15** (UART2 RX) | |
| RX | **GPIO16** (UART2 TX) | |
| PPS | not connected | optional later |

Many clone boards are 5 V powered with 3.3 V TX. Confirm with a meter. Indoor GPS will not lock — that is not a firmware bug.

### Waveshare S3KM1110 / HMMD (UART0, 115200)

| Radar | ESP32-S3 | Rail |
|---|---|---|
| 3V3 (or VCC 3.3 V) | 3V3 | **3.3 V only** (Waveshare HMMD: 3.0–3.6 V) |
| GND | GND | GND |
| TX | **GPIO11** (UART0 RX) | |
| RX | **GPIO10** (UART0 TX) | |
| OUT | **GPIO12** optional digital presence | active-high |

If your breakout is labelled 5 V tolerant, still prefer 3.3 V unless the silkscreen requires 5 V.

### BME280 (I2C0)

| BME280 | ESP32-S3 | Rail |
|---|---|---|
| VIN / 3.3V | 3V3 | 3.3 V (not 5 V on Adafruit-style boards unless specified) |
| GND | GND | GND |
| SDA | **GPIO8** | shared with 1.3" OLED |
| SCL | **GPIO9** | shared with 1.3" OLED |
| SDO | GND → address `0x76`, 3V3 → `0x77` | |

### MPU-6050 (I2C1 — separate from BME280)

Pads **8 / 9** are BME280 + the 1.3" OLED. MPU-6050 uses **17 / 18**.

| MPU-6050 | YD-ESP32-S3 pad | GPIO |
|---|---|---|
| VCC | **3V3** | — |
| GND | **GND** | — |
| SDA | **17** | 17 |
| SCL | **18** | 18 |
| AD0 | **GND** → `0x68` | — |
| INT | unused | GPIO7 is left ultrasonic echo |
| XDA / XCL | nc | — |

Chip is 3.3 V. Firmware: `Wire1.begin(17, 18)`.

### LM393 LDR module

| LDR module | ESP32-S3 | Rail |
|---|---|---|
| VCC | 3V3 | 3.3 V |
| GND | GND | GND |
| A0 | **GPIO4** (ADC1_CH3) | analog darkness |
| D0 | unused | optional; GPIO5 is free |

### 1.30" IIC OLED cab alert display (SH1106 128×64)

This replaced the JHD 162A character LCD. Four wires, I2C, same bus as the BME280. Front silk left → right: **VCC GND SCK SDA**. SCK is SCL. Line 1 = zone, large metres, then speed advice (`NORMAL SPEED` / `CRAWL MODE` / `REDUCE SPEED` / `STOP VEHICLE` / `TILT ALERT`). It runs on the ESP32 even if the Pi or Wi-Fi is down.

| OLED silk | YD-ESP32-S3 | Notes |
|---|---|---|
| VCC | **3V3** | 3.3 V (module is 3.3–5 V; stay on 3V3) |
| GND | GND | |
| SCK | **GPIO9** | I2C SCL, shared with BME280 |
| SDA | **GPIO8** | I2C SDA, shared with BME280 |

Address `0x3C` (fallback `0x3D`). Do **not** wire this to pads 17/18. If the image is shifted by ~2 pixels, set `OLED_IS_SH1106` to `0` in `config.h` (SSD1306).

### HC-SR04 left (YD-ESP32-S3)

GPIO14 is **not** on this board. Left echo is **GPIO7**.

| HC-SR04 | YD-ESP32-S3 pad | Rail |
|---|---|---|
| VCC | **5Vin** | 5 V |
| GND | **GND** | GND |
| TRIG | **13** | 3.3 V high is OK |
| ECHO | **7 via divider** | **mandatory 5 V → 3.3 V** |

Divider: ECHO — 2.2 kΩ — GPIO7 — 3.3 kΩ — GND (≈ 3.0 V high).

### HC-SR04 right

| HC-SR04 | YD-ESP32-S3 pad | Rail |
|---|---|---|
| VCC | **5Vin** | 5 V |
| GND | **GND** | GND |
| TRIG | **21** | |
| ECHO | **47 via same divider** | |

Stagger pings by ≥ 60 ms so the left echo is not heard by the right transducer.

### Operator outputs

| Output | GPIO | Notes |
|---|---|---|
| Green LED (SAFE) | **GPIO1** | 330 Ω to LED anode, cathode to GND |
| Yellow LED (CAUTION) | **GPIO2** | |
| Red LED (CRITICAL) | **GPIO42** | |
| Fog LED (FOG MODE) | **GPIO41** | |
| Buzzer (active) | **GPIO6** | If passive piezo, use PWM; firmware uses digital patterns |
| 1.3" OLED | **GPIO8 / GPIO9** I2C0 | cab alerts; address 0x3C with BME280 |

## Raspberry Pi 3 wiring

Enable: `sudo raspi-config` → Interface → I2C on. Optionally Camera if using a CSI module (OV7670 is **not** CSI).

### MLX9064X (MLX90640 / MLX90641) — Raspberry Pi 3 only

Do not wire this to the ESP32. Pads 8/9 are BME280 + OLED, 17/18 are MPU-6050, silk TX/RX are TFMini-S.

| MLX9064X | Pi 3 physical pin | BCM |
|---|---|---|
| VIN / 3.3V | **1** | 3V3 |
| GND | **6** | GND |
| SDA | **3** | GPIO2 |
| SCL | **5** | GPIO3 |

Address `0x33`. Confirm: `sudo i2cdetect -y 1`. Keep wires short (&lt; 30 cm) or drop to 100 kHz if CRC errors appear. Never use Pi pins 2 or 4 (5 V).

### OV7670 (Raspberry Pi 3 GPIO DVP)

Count J8 from the **left** (SD-card / pin-1 end). **Inner** = odd pins (1, 3, 5…). **Outer** = even pins (2, 4, 6…).  
**3.3 V only.** Never Pi pins 2 or 4 (5 V). Do **not** steal MLX pins 1 / 3 / 5 / 6.

| OV7670 | Pi pin | Where to count | BCM |
|---|---|---|---|
| 3.3V / VCC | **17** | Inner, 9th from the left | 3V3 |
| GND | **9** | Inner, 5th | GND |
| SIOD (SDA) | **19** | Inner, 10th | GPIO10 |
| SIOC (SCL) | **23** | Inner, 12th | GPIO11 |
| XCLK | **7** | Inner, 4th | GPIO4 |
| PCLK | **15** | Inner, 8th | GPIO22 |
| VSYNC | **13** | Inner, 7th | GPIO27 |
| HREF | **11** | Inner, 6th | GPIO17 |
| RESET | **18** | Outer, 9th | GPIO24 |
| PWDN | **16** | Outer, 8th | GPIO23 |
| D0 | **29** | Inner, 15th | GPIO5 |
| D1 | **31** | Inner, 16th | GPIO6 |
| D2 | **33** | Inner, 17th | GPIO13 |
| D3 | **35** | Inner, 18th | GPIO19 |
| D4 | **37** | Inner, 19th | GPIO26 |
| D5 | **36** | Outer, 18th | GPIO16 |
| D6 | **38** | Outer, 19th | GPIO20 |
| D7 | **40** | Outer, 20th (last pin, USB end) | GPIO21 |

HS on the module is HREF. RET/RST is RESET. VS is VSYNC.  
SCCB is **GPIO10 / GPIO11**, not the MLX I2C1 pins. Enable I2C for the thermal camera: `sudo raspi-config` → Interface → I2C. For OV7670 XCLK (~8 MHz on GPIO4) run `pigpiod` so the hub can call `hardware_clock(4, 8000000)`.

No USB camera is required. The hub grabs 160×120 grayscale from the OV7670 DVP pins in a background thread (`ov7670_grab.c`). Enable I2C for MLX only; for the camera run `sudo pigpiod` and keep SPI off so GPIO10/11 stay SCCB. Optional USB: `MINEVISION_USB_CAM=1`.

## Common ground

Star all GNDs to the 5 V supply negative. Do not daisy-chain sensor grounds through jumper-wire spaghetti if ranging looks noisy.

## Cable discipline

- UART pairs: TX→RX crossed, never TX→TX.
- I2C: SDA–SDA, SCL–SCL, common 3.3 V.
- LiDAR and radar cables < 50 cm.
- Keep GPS antenna away from ESP32 antenna by ≥ 5 cm.
