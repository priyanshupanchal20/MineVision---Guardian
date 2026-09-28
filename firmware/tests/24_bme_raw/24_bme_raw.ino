/*
  NEW BME280 test (not the old combined bench).
  OLED + BME on I2C0 SDA8 SCL9.
  BME: CSB->3V3, SDO->GND for 0x76. 3V3 + GND.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <Adafruit_BME280.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
Adafruit_BME280 bme;

static bool oled_ok = false, bme_ok = false;
static uint8_t bme_addr = 0;
static char scan_line[22] = "8/9: --";
static float t_c = 0, rh = 0, p_hpa = 0;

static void scanBus() {
  char tmp[22] = "8/9:";
  int found = 0;
  for (uint8_t a = 0x08; a <= 0x77; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      char hex[8];
      snprintf(hex, sizeof(hex), " %02X", a);
      if (strlen(tmp) + strlen(hex) < sizeof(tmp) - 1) strcat(tmp, hex);
      found++;
    }
  }
  if (!found) snprintf(tmp, sizeof(tmp), "8/9: none");
  strncpy(scan_line, tmp, sizeof(scan_line) - 1);
  scan_line[sizeof(scan_line) - 1] = 0;
}

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW BME RAW");
  oled.drawStr(0, 22, scan_line);
  if (bme_ok) {
    snprintf(line, sizeof(line), "OK @%02X", bme_addr);
    oled.drawStr(0, 34, line);
    snprintf(line, sizeof(line), "%.1fC  %.0f%%", t_c, rh);
    oled.drawStr(0, 48, line);
    snprintf(line, sizeof(line), "%.0f hPa", p_hpa);
    oled.drawStr(0, 62, line);
  } else {
    oled.drawStr(0, 36, "no 76/77 on 8/9");
    oled.drawStr(0, 50, "CSB->3V3 SDO->GND");
    oled.drawStr(0, 62, "VCC 3V3 not 5V");
  }
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW BME RAW  SDA8 SCL9");

  Wire.begin(8, 9);
  Wire.setClock(100000);
  Wire.setTimeOut(80);

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

  if (bme.begin(0x76, &Wire)) {
    bme_ok = true;
    bme_addr = 0x76;
  } else if (bme.begin(0x77, &Wire)) {
    bme_ok = true;
    bme_addr = 0x77;
  }
}

void loop() {
  scanBus();
  if (bme_ok) {
    t_c = bme.readTemperature();
    rh = bme.readHumidity();
    p_hpa = bme.readPressure() / 100.0f;
  }
  Serial.printf("scan=%s bme=%d T=%.1f RH=%.0f P=%.0f\n",
                scan_line, bme_ok, t_c, rh, p_hpa);
  draw();
  delay(250);
}
