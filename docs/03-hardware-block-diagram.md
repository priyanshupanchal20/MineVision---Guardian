# Hardware block diagram

```mermaid
flowchart LR
  subgraph PWR["Power"]
    PB[5 V 3 A supply]
    BUCK[Optional 12 V → 5 V 3 A buck<br/>from RC battery]
    PB --> RAIL5[5 V rail]
    BUCK --> RAIL5
    RAIL5 --> LDO3[3.3 V from ESP32 / Pi]
  end

  subgraph VEH["On-vehicle sensor head"]
    TF[TFMini-S 5 V UART]
    US[HC-SR04 x2 5 V GPIO<br/>ECHO via divider]
    RAD[S3KM1110 3.3 V UART]
    BME[BME280 3.3 V I2C]
    LDR[LM393 3.3 V ADC]
    GPS[NEO-6M 3.3–5 V UART]
    LCD[1.3in I2C OLED cab HUD]
    BZ[Buzzer + 4 LEDs]
  end

  subgraph MCU["ESP32-S3-WROOM-N16R8"]
    U0[UART0 LiDAR silk TX/RX]
    U2[UART2 GPS GPIO15/16]
    U1[UART1 mmWave]
    I2C[I2C0 BME280 + OLED]
    ADC[ADC1 LDR]
    GPIO[TRIG/ECHO + alerts]
    WIFI[Wi-Fi STA]
    NOW[ESP-NOW]
  end

  subgraph PI["Raspberry Pi 3 B"]
    I2C1[I2C1 MLX90640]
    CAM[OV7670 GPIO or USB cam]
    PY[Python fusion + FastAPI]
    AP[Wi-Fi / Ethernet]
  end

  RAIL5 --> TF
  RAIL5 --> US
  RAIL5 --> MCU
  RAIL5 --> PI
  LDO3 --> RAD
  LDO3 --> BME
  LDO3 --> LDR
  LDO3 --> LCD

  TF --> U1
  GPS --> U2
  RAD --> U0
  BME --> I2C
  LCD --> I2C
  LDR --> ADC
  US --> GPIO
  MCU --> BZ
  WIFI --> PY
  NOW -.-> PY
  I2C1 --> PY
  CAM --> PY
```

## Physical mounting (miniature dumper / RC)

| Sensor | Mount | Notes |
|---|---|---|
| TFMini-S | Front bumper, slightly above chassis, lens clear of bumper lip | Do not look into sun; keep glass dry |
| HC-SR04 left / right | Side skirts, 10–20 cm above ground | Soft targets absorb 40 kHz poorly |
| mmWave | Front or cabin-equivalent, facing expected pedestrian path | 24 GHz sees through light cloth, not thick metal |
| MLX90640 | Forward-facing, 55° FOV centred on haul path | Keep 10 cm from ESP32 Wi-Fi antenna |
| OV7670 / USB cam | Forward, parallel to LiDAR | Fog demo: compare RGB vs thermal |
| BME280 | Shaded, not on motor heat | Rain splash will ruin it — under a hood |
| LDR | Upward / sky-facing, not in LED glare | |
| GPS | Top of cab mock-up, sky view | Indoor fix will be invalid |
| 1.3" OLED | Cab mock-up, operator eye line | I2C with BME280 on pads 8/9 |
| ESP32 | Inside cab mock-up | USB-C debug accessible |
| Pi 3 | Rear / offboard table for demo if vibration is high | HDMI optional; judges use laptop browser |

## Communication protocols

| Device | Protocol | Rate | Address / baud |
|---|---|---|---|
| TFMini-S | UART 8N1 | 100 Hz default | 115200, header `0x59 0x59` |
| NEO-6M | UART NMEA | 1 Hz | 9600 |
| S3KM1110 | UART 8N1 | ~10 Hz reports | 115200, report header `F4 F3 F2 F1` |
| BME280 | I2C | 2 Hz | `0x76` (or `0x77`) |
| MLX90640 | I2C | 2 Hz prototype | `0x33` |
| OV7670 | SCCB + DVP | low | SCCB `0x21` |
| LDR | Analog | 10 Hz | ADC 12-bit |
| HC-SR04 | GPIO pulse | 10 Hz each, staggered | TRIG 10 µs |
| 1.3" OLED | I2C SH1106 128×64 | on zone change | SDA 8, SCL 9, addr 0x3C |
| ESP32 → Pi | HTTP JSON | 5 Hz | `POST /api/v1/ingest` |
| V2V | ESP-NOW | 1 Hz | 250-byte payload |
