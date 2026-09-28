/*
  NEW combined bench — only sensors already proven.
  LEDs not required (pins reserved, held LOW). Add 5mm + 330R later.
  MPU: raw I2C on 17/18 (WHO 0x70 clones OK).
  LDR: inverted (module high in dark).
  Buzzer GPIO6: beeps if closest range < 50 cm.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <Adafruit_BME280.h>
#include <TinyGPSPlus.h>
#include <math.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
HardwareSerial Lidar(0);
HardwareSerial GpsUart(2);
Adafruit_BME280 bme;
TinyGPSPlus gps;

static bool oled_ok = false, bme_ok = false, mpu_ok = false;
static uint8_t mpu_addr = 0, mpu_who = 0, bme_addr = 0;
static float pitch = 0, roll = 0, t_c = 0, rh = 0;
static float left_m = NAN, right_m = NAN, lidar_m = NAN;
static uint16_t lidar_st = 0;
static uint32_t lidar_sec = 0, lidar_hz = 0, lidar_t = 0;
static uint32_t gps_baud = 9600;
static bool gps_38400 = false;
static int light_pct = 0;
static int page = 0;

static bool wr1(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  Wire1.write(val);
  return Wire1.endTransmission() == 0;
}
static bool rd1(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  if (Wire1.endTransmission(false) != 0) return false;
  if (Wire1.requestFrom((int)addr, (int)n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire1.read();
  return true;
}

static bool tryMpu(uint8_t addr) {
  uint8_t who = 0, raw[6];
  if (!rd1(addr, 0x75, &who, 1)) return false;
  if (!wr1(addr, 0x6B, 0x00)) return false;
  delay(40);
  if (!rd1(addr, 0x3B, raw, 6)) return false;
  mpu_addr = addr;
  mpu_who = who;
  mpu_ok = true;
  return true;
}

static void sampleMpu() {
  if (!mpu_ok) return;
  uint8_t raw[6];
  if (!rd1(mpu_addr, 0x3B, raw, 6)) return;
  const int16_t ax = (int16_t)((raw[0] << 8) | raw[1]);
  const int16_t ay = (int16_t)((raw[2] << 8) | raw[3]);
  const int16_t az = (int16_t)((raw[4] << 8) | raw[5]);
  const float x = ax / 4096.0f, y = ay / 4096.0f, z = az / 4096.0f;
  roll = atan2f(y, z) * 180.0f / PI;
  pitch = atan2f(-x, sqrtf(y * y + z * z)) * 180.0f / PI;
}

static float pingUs(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 25000);
  if (!us) return NAN;
  return (us * 0.0343f) / 2.0f;
}

static void readLidar() {
  while (Lidar.available() >= 9) {
    if (Lidar.peek() != 0x59) { Lidar.read(); continue; }
    uint8_t b[9];
    if (Lidar.readBytes(b, 9) != 9) break;
    if (b[0] != 0x59 || b[1] != 0x59) continue;
    uint8_t sum = 0;
    for (int i = 0; i < 8; i++) sum += b[i];
    if (sum != b[8]) continue;
    uint16_t cm = b[2] | (uint16_t)(b[3] << 8);
    lidar_st = b[4] | (uint16_t)(b[5] << 8);
    lidar_m = cm * 0.01f;
    lidar_sec++;
  }
}

static float closestM() {
  float d = NAN;
  auto take = [&](float v) {
    if (isnan(v) || v < 0.02f) return;
    if (isnan(d) || v < d) d = v;
  };
  take(lidar_m);
  take(left_m);
  take(right_m);
  return d;
}

static void draw() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW ALL RAW");

  if (page == 0) {
    if (isnan(left_m) && isnan(right_m)) snprintf(line, sizeof(line), "US -- --");
    else snprintf(line, sizeof(line), "US L%3.0f R%3.0f cm",
                 isnan(left_m) ? -1 : left_m * 100.0f,
                 isnan(right_m) ? -1 : right_m * 100.0f);
    oled.drawStr(0, 24, line);
    if (lidar_hz == 0) snprintf(line, sizeof(line), "LID 0Hz");
    else snprintf(line, sizeof(line), "LID %3.0fcm %uHz", lidar_m * 100.0f, (unsigned)lidar_hz);
    oled.drawStr(0, 38, line);
    if (bme_ok) snprintf(line, sizeof(line), "BME %.1fC %.0f%%", t_c, rh);
    else snprintf(line, sizeof(line), "BME --");
    oled.drawStr(0, 52, line);
    oled.drawStr(0, 62, "page1 MPU GPS LDR");
  } else {
    if (mpu_ok) snprintf(line, sizeof(line), "MPU P%.0f R%.0f", pitch, roll);
    else snprintf(line, sizeof(line), "MPU --");
    oled.drawStr(0, 24, line);
    if (gps.location.isValid())
      snprintf(line, sizeof(line), "GPS FIX %d", gps.satellites.value());
    else if (gps.charsProcessed() > 20)
      snprintf(line, sizeof(line), "GPS NMEA nofix");
    else
      snprintf(line, sizeof(line), "GPS --");
    oled.drawStr(0, 38, line);
    snprintf(line, sizeof(line), "LDR %d%%", light_pct);
    oled.drawStr(0, 52, line);
    const float d = closestM();
    if (!isnan(d) && d < 0.50f) oled.drawStr(0, 62, "BUZZ close <50cm");
    else oled.drawStr(0, 62, "LEDs later G1 Y2");
  }
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW ALL RAW  LEDs optional");

  pinMode(13, OUTPUT);
  pinMode(21, OUTPUT);
  pinMode(7, INPUT);
  pinMode(47, INPUT);
  pinMode(4, INPUT);
  pinMode(6, OUTPUT);
  digitalWrite(6, LOW);
  pinMode(1, OUTPUT);
  pinMode(2, OUTPUT);
  pinMode(42, OUTPUT);
  pinMode(41, OUTPUT);
  digitalWrite(1, LOW);
  digitalWrite(2, LOW);
  digitalWrite(42, LOW);
  digitalWrite(41, LOW);

  analogReadResolution(12);
  analogSetPinAttenuation(4, ADC_11db);

  Lidar.setRxBufferSize(512);
  Lidar.begin(115200, SERIAL_8N1, 44, 43);
  GpsUart.setRxBufferSize(512);
  GpsUart.begin(gps_baud, SERIAL_8N1, 15, 16);

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
  if (bme.begin(0x76, &Wire)) { bme_ok = true; bme_addr = 0x76; }
  else if (bme.begin(0x77, &Wire)) { bme_ok = true; bme_addr = 0x77; }

  Wire1.begin(17, 18);
  Wire1.setClock(50000);
  Wire1.setTimeOut(80);
  tryMpu(0x68) || tryMpu(0x69);

  lidar_t = millis();
}

void loop() {
  readLidar();
  uint8_t n = 0;
  while (GpsUart.available() && n < 48) {
    gps.encode(GpsUart.read());
    n++;
  }
  if (!gps_38400 && millis() > 4000 && gps.charsProcessed() < 20) {
    gps_38400 = true;
    gps_baud = 38400;
    GpsUart.end();
    delay(20);
    GpsUart.begin(gps_baud, SERIAL_8N1, 15, 16);
  }

  static uint32_t us_t;
  static bool left = true;
  if (millis() - us_t >= 80) {
    us_t = millis();
    if (left) left_m = pingUs(13, 7);
    else right_m = pingUs(21, 47);
    left = !left;
  }

  if (bme_ok) {
    t_c = bme.readTemperature();
    rh = bme.readHumidity();
  }
  sampleMpu();
  light_pct = constrain(map(analogRead(4), 0, 4095, 100, 0), 0, 100);

  const uint32_t now = millis();
  if (now - lidar_t >= 1000) {
    lidar_hz = lidar_sec;
    lidar_sec = 0;
    lidar_t = now;
  }
  static uint32_t page_t;
  if (now - page_t >= 2000) {
    page_t = now;
    page = 1 - page;
  }

  const float d = closestM();
  const bool close = !isnan(d) && d < 0.50f;
  digitalWrite(6, close && ((now / 200) % 2));

  Serial.printf("L=%.2f R=%.2f LID=%.2f hz=%u T=%.1f MPU=%d GPS=%lu LDR=%d\n",
                left_m, right_m, lidar_m, (unsigned)lidar_hz, t_c, mpu_ok,
                (unsigned long)gps.charsProcessed(), light_pct);
  draw();
  delay(40);
}
