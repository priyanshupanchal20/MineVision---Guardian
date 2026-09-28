# Wiring diagrams index

All visual sheets live in one print-ready file:

**[hardware/wiring-diagrams.html](../hardware/wiring-diagrams.html)**

Open that file in Chrome/Edge (double-click). Use Print → Save as PDF if you need paper copies for the bench.

| Sheet | What it shows |
|---|---|
| 1 System | ESP32 vs Pi vs every sensor |
| 2 Power | 5 V 3 A tree and 3.3 V rails |
| 3 Forbidden pins | N16R8 pins you must not use |
| 4 ESP32 map | Every project GPIO |
| 5 LiDAR | TFMini-S colour wires, UART1 |
| 6 Ultrasonics | Left GPIO13/14, right GPIO21/47 |
| 7 Echo divider | 2.2 kΩ / 3.3 kΩ (mandatory ×2) |
| 8 mmWave | S3KM1110 3.3 V UART0 |
| 9 GPS | NEO-6M UART2 |
| 10 BME280 | I2C GPIO8/9 |
| 11 LDR | A0 GPIO4 |
| 12 LEDs / buzzer | GPIO1/2/42/41/6 + 330 Ω |
| 13 Raspberry Pi | 40-pin pins 1, 3, 5, 6 |
| 14 Thermal | MLX90640 0x33 |
| 15 Camera | USB webcam (OV7670 not for demo) |
| 16 Order | Ground-first assembly |

Cheat-sheet: `hardware/WIRING.md`  
Pin rationale: `docs/04-sensor-connection-plan.md` · `docs/05-esp32-pin-mapping.md`
