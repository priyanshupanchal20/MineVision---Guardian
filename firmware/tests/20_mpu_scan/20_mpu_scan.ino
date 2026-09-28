/*
  NEW MPU test (not the old Adafruit-only sketch).
  OLED on 8/9. MPU on 17/18. Raw I2C — clones with WHO_AM_I != 0x68 still run.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <math.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
static bool oled_ok = false;
static bool mpu_ok = false;
static uint8_t mpu_addr = 0, mpu_who = 0;
static float pitch = 0, roll = 0;
static char scan_line[22] = "17/18: none";

static bool wr(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  Wire1.write(val);
  return Wire1.endTransmission() == 0;
}

static bool rd(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  if (Wire1.endTransmission(false) != 0) return false;
  if (Wire1.requestFrom((int)addr, (int)n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire1.read();
  return true;
}

static void scanBus() {
  char tmp[22] = "17/18:";
  int found = 0;
  for (uint8_t a = 0x08; a <= 0x77; a++) {
    Wire1.beginTransmission(a);
    if (Wire1.endTransmission() == 0) {
      char hex[8];
      snprintf(hex, sizeof(hex), " %02X", a);
      if (strlen(tmp) + strlen(hex) < sizeof(tmp) - 1) strcat(tmp, hex);
      found++;
    }
  }
  if (!found) snprintf(tmp, sizeof(tmp), "17/18: none");
  strncpy(scan_line, tmp, sizeof(scan_line) - 1);
  scan_line[sizeof(scan_line) - 1] = 0;
}

static bool tryMpu(uint8_t addr) {
  uint8_t who = 0;
  if (!rd(addr, 0x75, &who, 1)) return false;
  if (!wr(addr, 0x6B, 0x00)) return false;
  delay(50);
  uint8_t raw[6];
  if (!rd(addr, 0x3B, raw, 6)) return false;
  mpu_addr = addr;
  mpu_who = who;
  mpu_ok = true;
  return true;
}

static void sampleMpu() {
  if (!mpu_ok) return;
  uint8_t raw[6];
  if (!rd(mpu_addr, 0x3B, raw, 6)) return;
  const int16_t ax = (int16_t)((raw[0] << 8) | raw[1]);
  const int16_t ay = (int16_t)((raw[2] << 8) | raw[3]);
  const int16_t az = (int16_t)((raw[4] << 8) | raw[5]);
  const float x = ax / 4096.0f, y = ay / 4096.0f, z = az / 4096.0f;
  roll = atan2f(y, z) * 180.0f / PI;
  pitch = atan2f(-x, sqrtf(y * y + z * z)) * 180.0f / PI;
}

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW MPU SCAN");
  oled.drawStr(0, 22, scan_line);
  if (mpu_ok) {
    snprintf(line, sizeof(line), "WHO %02X @%02X", mpu_who, mpu_addr);
    oled.drawStr(0, 34, line);
    snprintf(line, sizeof(line), "P%5.0f  R%5.0f", pitch, roll);
    oled.drawStr(0, 48, line);
    oled.drawStr(0, 62, "tilt the board");
  } else {
    oled.drawStr(0, 36, "no ACK on 17/18");
    oled.drawStr(0, 50, "swap SDA/SCL");
    oled.drawStr(0, 62, "ADO->GND  3V3");
  }
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW MPU SCAN  SDA17 SCL18");

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

  Wire1.begin(17, 18);
  Wire1.setClock(50000);
  Wire1.setTimeOut(80);
}

void loop() {
  scanBus();
  if (!mpu_ok) {
    tryMpu(0x68) || tryMpu(0x69);
  } else {
    sampleMpu();
  }
  Serial.printf("scan=%s mpu=%d who=0x%02X pitch=%.1f\n", scan_line, mpu_ok, mpu_who, pitch);
  draw();
  delay(200);
}
