/*
  NEW LDR test (not the old combined bench).
  OLED 8/9. LM393 LDR A0 -> GPIO4. D0 unused. 3V3 + GND.
  Cover/uncover the sensor — raw and % should move.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
static bool oled_ok = false;
static int raw = 0, pct = 0;

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW LDR RAW");
  snprintf(line, sizeof(line), "raw %d", raw);
  oled.drawStr(0, 26, line);
  snprintf(line, sizeof(line), "light %d%%", pct);
  oled.drawStr(0, 40, line);
  oled.drawStr(0, 52, "cover=dark flash=hi");
  oled.drawStr(0, 62, "A0 GPIO4  3V3 GND");
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW LDR RAW  A0 GPIO4");
  analogReadResolution(12);
  analogSetPinAttenuation(4, ADC_11db);

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
  raw = analogRead(4);
  /* LM393 A0 goes high in dark, low in light */
  pct = constrain(map(raw, 0, 4095, 100, 0), 0, 100);
  Serial.printf("raw=%d light=%d\n", raw, pct);
  draw();
  delay(150);
}
