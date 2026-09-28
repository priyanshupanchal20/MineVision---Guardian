/*
  NEW ultrasonic test (not the old combined bench).
  OLED 8/9. Left TRIG13 ECHO7. Right TRIG21 ECHO47.
  Shows echo microseconds so timeout (0) vs a real pulse is obvious.
  Modules need EXTERNAL 5 V + GND common with ESP32. Board 5Vin is ~0.5 V.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
static bool oled_ok = false;
static unsigned long usL = 0, usR = 0;

static unsigned long echoUs(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  return pulseIn(echo, HIGH, 25000);
}

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW SONAR RAW");
  if (usL == 0) snprintf(line, sizeof(line), "L 0us  no echo");
  else snprintf(line, sizeof(line), "L %luus %dcm", usL, (int)((usL * 0.0343f) / 2.0f + 0.5f));
  oled.drawStr(0, 26, line);
  if (usR == 0) snprintf(line, sizeof(line), "R 0us  no echo");
  else snprintf(line, sizeof(line), "R %luus %dcm", usR, (int)((usR * 0.0343f) / 2.0f + 0.5f));
  oled.drawStr(0, 40, line);
  oled.drawStr(0, 52, "5V ext + GND share");
  oled.drawStr(0, 62, "L13/7  R21/47");
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW SONAR  L TRIG13 ECHO7  R TRIG21 ECHO47");

  pinMode(13, OUTPUT);
  pinMode(21, OUTPUT);
  pinMode(7, INPUT);
  pinMode(47, INPUT);

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
  usL = echoUs(13, 7);
  delay(60);
  usR = echoUs(21, 47);
  Serial.printf("L_us=%lu R_us=%lu\n", usL, usR);
  draw();
  delay(60);
}
