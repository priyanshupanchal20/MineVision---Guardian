# ESP32-S3 pin mapping table

Board: ESP32-S3-WROOM-1-**N16R8**, Dual Type-C DevKitC-1 layout.

| GPIO | Function | Direction | Peripheral | Notes |
|---|---|---|---|---|
| **43 (silk TX)** | LIDAR_RX (ESP TX) | OUT | UART0 TX | TFMini-S white RX — **occupied** |
| **44 (silk RX)** | LIDAR_TX (ESP RX) | IN | UART0 RX | TFMini-S green TX — **occupied** |
| 1 | LED_GREEN | OUT | GPIO | SAFE |
| 2 | LED_YELLOW | OUT | GPIO | CAUTION |
| 4 | LDR_AO | IN analog | ADC1_CH3 | 0–4095 |
| 6 | BUZZER | OUT | GPIO | alert patterns |
| 8 | I2C_SDA | I/O | I2C0 | BME280 + 1.3" OLED |
| 9 | I2C_SCL | OUT | I2C0 | BME280 + 1.3" OLED |
| 17 | MPU_SDA | I/O | I2C1 | MPU-6050 only |
| 18 | MPU_SCL | OUT | I2C1 | MPU-6050 only |
| 7 | US_LEFT_ECHO | IN | GPIO | after 5→3.3 V divider |
| 10 | RADAR_RX (ESP TX) | OUT | UART1 TX | to S3KM1110 RX |
| 11 | RADAR_TX (ESP RX) | IN | UART1 RX | from S3KM1110 TX |
| 12 | RADAR_OUT | IN | GPIO | optional presence |
| 13 | US_LEFT_TRIG | OUT | GPIO | |
| 15 | GPS_TX (ESP RX) | IN | UART2 RX | from NEO-6M TX |
| 16 | GPS_RX (ESP TX) | OUT | UART2 TX | to NEO-6M RX |
| 21 | US_RIGHT_TRIG | OUT | GPIO | |
| 41 | LED_FOG | OUT | GPIO | FOG SAFETY MODE |
| 42 | LED_RED | OUT | GPIO | HIGH / CRITICAL |
| 47 | US_RIGHT_ECHO | IN | GPIO | after divider |
| 3V3 | sensors | PWR | | BME, OLED, LDR, radar |
| 5Vin | sensors | PWR | | LiDAR, ultrasonics, ESP |
| GND | common | PWR | | |

## UART map

| UART | RX GPIO | TX GPIO | Baud | Device |
|---|---|---|---|---|
| USB CDC (USB-OTG) | — | — | 115200 | PC Serial Monitor |
| UART0 | **44 (silk RX)** | **43 (silk TX)** | 115200 | **TFMini-S (occupied)** |
| UART1 | 11 | 10 | 115200 | S3KM1110 |
| UART2 | 15 | 16 | 9600 | NEO-6M |

Arduino `HardwareSerial` constructor: `Serial1.begin(baud, SERIAL_8N1, rxPin, txPin)`.

## Cab OLED (1.30" IIC V2.2, SH1106)

SDA=8, SCL=9 (SCK on the module silk), address `0x3C`. Shares I2C0 with the BME280 (`0x76`). Do not steal silk TX/RX from the LiDAR or 17/18 from the MPU-6050. Spare GPIOs: 3, 5, 38, 39, 40, 48. Do not use 19/20/35/36/37.

## Raspberry Pi 3 mapping (summary)

| BCM | Function |
|---|---|
| 2 | I2C1 SDA — MLX90640 |
| 3 | I2C1 SCL — MLX90640 |
| USB | Webcam index 0 |
| Ethernet / wlan0 | Dashboard + ESP32 ingest |
