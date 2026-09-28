/*
  Phase 2 — TFMini-S on YD-ESP32-S3 silkscreen TX / RX
  Board RX (GPIO44) <- TFMini green TX
  Board TX (GPIO43) -> TFMini white RX
  Serial Monitor: use the USB-OTG Type-C, not COM (COM shares TX/RX).
*/
#include <Arduino.h>
HardwareSerial Lidar(0);
void setup() {
  Serial.begin(115200);
  Lidar.begin(115200, SERIAL_8N1, 44, 43);
  Serial.println("TFMini-S on silk RX=GPIO44  TX=GPIO43  (USB-OTG for logs)");
}
void loop() {
  if (Lidar.available() < 9) return;
  if (Lidar.peek() != 0x59) { Lidar.read(); return; }
  uint8_t b[9];
  if (Lidar.readBytes(b, 9) != 9) return;
  if (b[0] != 0x59 || b[1] != 0x59) return;
  uint8_t sum = 0; for (int i = 0; i < 8; i++) sum += b[i];
  if (sum != b[8]) { Serial.println("checksum"); return; }
  uint16_t cm = b[2] | (b[3] << 8);
  uint16_t st = b[4] | (b[5] << 8);
  Serial.printf("dist_m=%.2f strength=%u temp_code=%u\n", cm * 0.01f, st, b[6]);
}
