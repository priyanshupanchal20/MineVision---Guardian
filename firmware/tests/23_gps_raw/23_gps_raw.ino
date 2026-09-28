/*
  NEW GPS test (not the old combined bench).
  OLED 8/9. NEO-6M on UART2: GPS TX -> GPIO15, GPS RX -> GPIO16.
  Not the silk TX/RX pads (those are LiDAR).
  Indoor pass = chars climbing. Fix needs outdoor sky.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <TinyGPSPlus.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
HardwareSerial GpsUart(2);
TinyGPSPlus gps;

static bool oled_ok = false;
static uint32_t baud = 9600;
static uint32_t chars_mark = 0;
static bool tried_38400 = false;

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW GPS RAW");
  snprintf(line, sizeof(line), "chars %lu  %lu", (unsigned long)gps.charsProcessed(), (unsigned long)baud);
  oled.drawStr(0, 24, line);
  if (gps.location.isValid()) {
    snprintf(line, sizeof(line), "FIX sats %d", gps.satellites.value());
    oled.drawStr(0, 38, line);
    snprintf(line, sizeof(line), "%.5f %.5f", gps.location.lat(), gps.location.lng());
    oled.drawStr(0, 50, line);
  } else if (gps.charsProcessed() > 20) {
    oled.drawStr(0, 38, "NMEA ok  nofix");
    oled.drawStr(0, 50, "needs outdoor sky");
  } else {
    oled.drawStr(0, 38, "0 chars: swap TX");
    oled.drawStr(0, 50, "GPS TX -> GPIO15");
  }
  oled.drawStr(0, 62, "TX15 RX16  5V/GND");
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW GPS RAW  GPS-TX->15  GPS-RX->16");

  GpsUart.setRxBufferSize(512);
  GpsUart.begin(baud, SERIAL_8N1, 15, 16);
  chars_mark = 0;

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
}

void loop() {
  uint8_t n = 0;
  while (GpsUart.available() && n < 64) {
    gps.encode(GpsUart.read());
    n++;
  }

  if (!tried_38400 && millis() > 4000 && gps.charsProcessed() <= chars_mark) {
    tried_38400 = true;
    baud = 38400;
    GpsUart.end();
    delay(20);
    GpsUart.begin(baud, SERIAL_8N1, 15, 16);
    Serial.println("GPS retry 38400");
  }

  Serial.printf("chars=%lu baud=%lu valid=%d sats=%d\n",
                (unsigned long)gps.charsProcessed(), (unsigned long)baud,
                gps.location.isValid(), gps.satellites.value());
  draw();
  delay(80);
}
