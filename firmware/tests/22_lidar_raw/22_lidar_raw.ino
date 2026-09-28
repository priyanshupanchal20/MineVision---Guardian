/*
  NEW LiDAR test (not the old combined bench).
  OLED 8/9. TFMini-S on UART0 silk RX=GPIO44 TX=GPIO43.
  Unplug CH343/COM from those pins — they share UART0.
  TFMini needs EXTERNAL 5 V + GND common with ESP32.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
HardwareSerial Lidar(0);

static bool oled_ok = false;
static uint16_t dist_cm = 0, strength = 0;
static uint32_t frames_sec = 0, total = 0, hz = 0, hz_t = 0, last_frame_ms = 0;

static void readLidar() {
  while (Lidar.available() >= 9) {
    if (Lidar.peek() != 0x59) {
      Lidar.read();
      continue;
    }
    uint8_t b[9];
    if (Lidar.readBytes(b, 9) != 9) break;
    if (b[0] != 0x59 || b[1] != 0x59) continue;
    uint8_t sum = 0;
    for (int i = 0; i < 8; i++) sum += b[i];
    if (sum != b[8]) continue;
    dist_cm = b[2] | (uint16_t)(b[3] << 8);
    strength = b[4] | (uint16_t)(b[5] << 8);
    frames_sec++;
    total++;
    last_frame_ms = millis();
  }
}

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW LIDAR RAW");
  snprintf(line, sizeof(line), "hz %u  n %lu", (unsigned)hz, (unsigned long)total);
  oled.drawStr(0, 24, line);
  if (hz == 0) {
    oled.drawStr(0, 38, "0Hz unplug CH343");
    oled.drawStr(0, 50, "GRN->RX44 WHT->TX43");
  } else {
    snprintf(line, sizeof(line), "%u cm  st %u", (unsigned)dist_cm, (unsigned)strength);
    oled.drawStr(0, 38, line);
    oled.drawStr(0, 50, "cover lens: cm jumps");
  }
  oled.drawStr(0, 62, "5V ext + GND share");
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW LIDAR RAW  RX44 TX43  USB-OTG only");

  Lidar.setRxBufferSize(512);
  Lidar.begin(115200, SERIAL_8N1, 44, 43);

  Wire.begin(8, 9);
  Wire.setClock(100000);
  uint8_t oa = 0x3C;
  Wire.beginTransmission(oa);
  if (Wire.endTransmission() != 0) {
    oa = 0x3D;
    Wire.beginTransmission(oa);
    oled_ok = Wire.endTransmission() == 0;
  } else oled_ok = true;
  if (oled_ok) {
    oled.setI2CAddress(oa << 1);
    oled.setBusClock(100000);
    oled.begin();
  }
  hz_t = millis();
}

void loop() {
  readLidar();
  const uint32_t now = millis();
  if (now - hz_t >= 1000) {
    hz = frames_sec;
    frames_sec = 0;
    hz_t = now;
  }
  Serial.printf("hz=%u cm=%u st=%u age_ms=%lu\n",
                (unsigned)hz, (unsigned)dist_cm, (unsigned)strength,
                (unsigned long)(now - last_frame_ms));
  draw();
  delay(80);
}
