/*
  Fresh sensor bench — YD-ESP32-S3. Radar and motors not used.
  5 V sensors (TFMini, HC-SR04, GPS if silk says 5 V) need an EXTERNAL 5 V
  rail + common GND. Board 5Vin is ~0.5 V unless IN-OUT is soldered.

  OLED+BME  3V3  SDA8 SCL9
  MPU       3V3  SDA17 SCL18  AD0=GND
  LiDAR     5 V  green->silk RX(44)  white->silk TX(43)
  US left   5 V  TRIG13  ECHO7 via divider
  US right  5 V  TRIG21  ECHO47 via divider
  GPS       5 V or 3V3   TX->15  RX->16
  Serial    USB-OTG only (not COM / CH343)
*/
#include <Arduino.h>
#include <Wire.h>
#include <HardwareSerial.h>
#include <Adafruit_BME280.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <U8g2lib.h>
#include <TinyGPSPlus.h>
#include <math.h>
#include <string.h>

HardwareSerial Lidar(0);
HardwareSerial GpsUart(2);
TinyGPSPlus gps;
Adafruit_BME280 bme;
Adafruit_MPU6050 mpu;
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

static bool oled_ok, bme_ok, mpu_ok, lidar_ok;
static const char *mpu_bus = "nf";
static uint8_t mpu_who = 0, mpu_addr = 0;
static TwoWire *mpu_wire = nullptr;
static uint8_t i2c_bus1_n = 0;  // devices on 17/18 besides none expected
static float lidar_m = NAN;
static uint16_t lidar_st;
static uint32_t lidar_hz, lidar_frames, lidar_hz_t;
static float left_m = NAN, right_m = NAN;
static float t_c = NAN, rh = NAN, p_hpa = NAN, pitch = NAN;
static uint32_t gps_baud = 9600;
static uint32_t gps_chars_mark;

static bool readLidarLatest() {
  bool got = false;
  uint16_t cm = 0, st = 0;
  while (Lidar.available() >= 9) {
    if (Lidar.peek() != 0x59) { Lidar.read(); continue; }
    uint8_t b[9];
    if (Lidar.readBytes(b, 9) != 9) break;
    if (b[0] != 0x59 || b[1] != 0x59) continue;
    uint8_t sum = 0;
    for (int i = 0; i < 8; i++) sum += b[i];
    if (sum != b[8]) continue;
    cm = b[2] | (uint16_t)(b[3] << 8);
    st = b[4] | (uint16_t)(b[5] << 8);
    got = true;
  }
  if (!got) return false;
  lidar_st = st;
  lidar_frames++;
  if (cm < 2 || cm > 1200 || st < 20) {
    lidar_ok = false;
    return true;
  }
  lidar_m = cm * 0.01f;
  lidar_ok = true;
  return true;
}

static float pingUs(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 12000);
  if (!us) return NAN;
  const float m = (us * 0.0343f) / 2.0f;
  if (m < 0.02f || m > 4.00f) return NAN;
  return m;
}

static void drawOled() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);

  if (bme_ok) snprintf(line, sizeof(line), "BME OK %4.1fC %2.0f%%", t_c, rh);
  else snprintf(line, sizeof(line), "BME --  3V3 SDA8");
  oled.drawStr(0, 10, line);

  if (lidar_ok) snprintf(line, sizeof(line), "LID %4dcm %uHz", (int)lroundf(lidar_m * 100.0f), (unsigned)lidar_hz);
  else snprintf(line, sizeof(line), "LID --  5V TXRX");
  oled.drawStr(0, 22, line);

  char lbuf[8], rbuf[8];
  if (isnan(left_m)) strcpy(lbuf, "--");
  else snprintf(lbuf, sizeof(lbuf), "%d", (int)lroundf(left_m * 100.0f));
  if (isnan(right_m)) strcpy(rbuf, "--");
  else snprintf(rbuf, sizeof(rbuf), "%d", (int)lroundf(right_m * 100.0f));
  snprintf(line, sizeof(line), "US L%s R%s cm", lbuf, rbuf);
  oled.drawStr(0, 34, line);

  if (mpu_ok) snprintf(line, sizeof(line), "MPU OK %s P%.0f", mpu_bus, pitch);
  else if (i2c_bus1_n) snprintf(line, sizeof(line), "MPU ACK n=%u tryRST", i2c_bus1_n);
  else snprintf(line, sizeof(line), "MPU nf  SDA17 SCL18");
  oled.drawStr(0, 46, line);

  if (gps.location.isValid())
    snprintf(line, sizeof(line), "GPS FIX %d sats", gps.satellites.value());
  else if (gps.charsProcessed() > 20)
    snprintf(line, sizeof(line), "GPS NMEA nofix");
  else
    snprintf(line, sizeof(line), "GPS --  TX15 RX16");
  oled.drawStr(0, 58, line);
  oled.sendBuffer();
}

static bool i2cWrite8(TwoWire &w, uint8_t addr, uint8_t reg, uint8_t val) {
  w.beginTransmission(addr);
  w.write(reg);
  w.write(val);
  return w.endTransmission() == 0;
}

static bool i2cReadN(TwoWire &w, uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t n) {
  w.beginTransmission(addr);
  w.write(reg);
  if (w.endTransmission(false) != 0) return false;
  if (w.requestFrom((int)addr, (int)n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = w.read();
  return true;
}

static uint8_t i2cScanCount(TwoWire &w, bool skip_bme_oled) {
  uint8_t n = 0;
  Serial.print(" scan");
  for (uint8_t a = 0x08; a <= 0x77; a++) {
    if (skip_bme_oled && (a == 0x3C || a == 0x3D || a == 0x76 || a == 0x77)) continue;
    w.beginTransmission(a);
    if (w.endTransmission() == 0) {
      Serial.printf(" 0x%02X", a);
      n++;
    }
  }
  if (!n) Serial.print(" (none)");
  Serial.println();
  return n;
}

/* Adafruit begin() rejects clones whose WHO_AM_I is not 0x68 (often 0x70/0x72). */
static bool mpuWakeRaw(TwoWire &w, uint8_t addr, const char *name) {
  uint8_t who = 0;
  if (!i2cReadN(w, addr, 0x75, &who, 1)) return false;
  if (!i2cWrite8(w, addr, 0x6B, 0x00)) return false;  // wake
  delay(40);
  uint8_t raw[6];
  if (!i2cReadN(w, addr, 0x3B, raw, 6)) return false;
  mpu_ok = true;
  mpu_wire = &w;
  mpu_addr = addr;
  mpu_who = who;
  mpu_bus = name;
  Serial.printf("MPU raw OK bus=%s addr=0x%02X WHO=0x%02X\n", name, addr, who);
  return true;
}

static bool mpuStart(TwoWire &bus, const char *name) {
  bus.setClock(50000);
  bus.setTimeOut(80);
  if (mpu.begin(0x68, &bus) || mpu.begin(0x69, &bus)) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    mpu_ok = true;
    mpu_wire = &bus;
    mpu_addr = 0x68;
    mpu_who = 0x68;
    mpu_bus = name;
    Serial.printf("MPU Adafruit OK %s\n", name);
    return true;
  }
  if (mpuWakeRaw(bus, 0x68, name) || mpuWakeRaw(bus, 0x69, name)) return true;
  return false;
}

static void mpuReadPitch() {
  if (!mpu_ok) return;
  if (mpu_who == 0x68 && mpu_wire) {
    sensors_event_t a, g, tmp;
    mpu.getEvent(&a, &g, &tmp);
    pitch = atan2f(-a.acceleration.x,
                   sqrtf(a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z)) *
            180.0f / PI;
    return;
  }
  uint8_t raw[6];
  if (!mpu_wire || !i2cReadN(*mpu_wire, mpu_addr, 0x3B, raw, 6)) return;
  const int16_t ax = (int16_t)((raw[0] << 8) | raw[1]);
  const int16_t ay = (int16_t)((raw[2] << 8) | raw[3]);
  const int16_t az = (int16_t)((raw[4] << 8) | raw[5]);
  const float fax = ax / 4096.0f, fay = ay / 4096.0f, faz = az / 4096.0f;
  pitch = atan2f(-fax, sqrtf(fay * fay + faz * faz)) * 180.0f / PI;
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("=== FRESH SENSOR BENCH ===");
  Serial.println("5V sensors: EXTERNAL 5V + common GND (5Vin is 0.5V)");

  pinMode(13, OUTPUT);
  pinMode(21, OUTPUT);
  pinMode(7, INPUT);
  pinMode(47, INPUT);

  Lidar.setRxBufferSize(1024);
  Lidar.setTimeout(5);
  Lidar.begin(115200, SERIAL_8N1, 44, 43);
  delay(40);
  const uint8_t tf_on[] = {0x5A, 0x05, 0x07, 0x01, 0x67};
  const uint8_t hz100[] = {0x5A, 0x06, 0x03, 0x64, 0x00, 0xC7};
  Lidar.write(tf_on, sizeof(tf_on));
  delay(15);
  Lidar.write(hz100, sizeof(hz100));
  while (Lidar.available()) Lidar.read();

  GpsUart.setRxBufferSize(512);
  GpsUart.begin(9600, SERIAL_8N1, 15, 16);
  gps_chars_mark = 0;

  Wire.begin(8, 9);
  Wire.setClock(100000);
  Wire.setTimeOut(50);

  uint8_t oled_addr = 0x3C;
  Wire.beginTransmission(oled_addr);
  if (Wire.endTransmission() != 0) {
    oled_addr = 0x3D;
    Wire.beginTransmission(oled_addr);
    oled_ok = Wire.endTransmission() == 0;
  } else {
    oled_ok = true;
  }
  if (oled_ok) {
    oled.setI2CAddress(oled_addr << 1);
    oled.setBusClock(100000);
    oled.begin();
    oled.clearBuffer();
    oled.setFont(u8g2_font_6x12_tf);
    oled.drawStr(0, 14, "FRESH BENCH");
    oled.drawStr(0, 30, "OLED BME LIDAR");
    oled.drawStr(0, 44, "US MPU GPS");
    oled.drawStr(0, 58, "use EXTERNAL 5V");
    oled.sendBuffer();
    Serial.printf("OLED OK 0x%02X\n", oled_addr);
    delay(900);
  } else {
    Serial.println("OLED -- plug VCC 3V3 SDA8 SCL9");
  }

  bme_ok = bme.begin(0x76, &Wire) || bme.begin(0x77, &Wire);
  Serial.println(bme_ok ? "BME OK" : "BME --");

  Wire1.begin(17, 18);
  Wire1.setClock(50000);
  Wire1.setTimeOut(80);
  Serial.print("I2C 17/18");
  i2c_bus1_n = i2cScanCount(Wire1, false);
  Serial.print("I2C 8/9 extra");
  i2cScanCount(Wire, true);

  if (!mpuStart(Wire1, "17/18")) mpuStart(Wire, "8/9");

  lidar_hz_t = millis();
}

void loop() {
  readLidarLatest();

  uint8_t n = 0;
  while (GpsUart.available() && n < 48) {
    gps.encode(GpsUart.read());
    n++;
  }
  if (gps_baud == 9600 && millis() > 4000 && gps.charsProcessed() <= gps_chars_mark) {
    gps_baud = 38400;
    GpsUart.end();
    delay(10);
    GpsUart.begin(38400, SERIAL_8N1, 15, 16);
    Serial.println("GPS retry 38400");
  }

  const uint32_t now = millis();
  if (now - lidar_hz_t >= 1000) {
    lidar_hz = lidar_frames;
    lidar_frames = 0;
    lidar_hz_t = now;
  }

  static uint32_t us_t;
  static bool left = true;
  if (now - us_t >= 100) {
    us_t = now;
    if (left) left_m = pingUs(13, 7);
    else right_m = pingUs(21, 47);
    left = !left;
    readLidarLatest();
  }

  static uint32_t oled_t;
  if (now - oled_t >= 80) {
    oled_t = now;
    drawOled();
  }

  static uint32_t env_t;
  if (now - env_t >= 800) {
    env_t = now;
    if (bme_ok) {
      t_c = bme.readTemperature();
      rh = bme.readHumidity();
      p_hpa = bme.readPressure() / 100.0f;
    }
    if (!mpu_ok) {
      Serial.print("I2C 17/18");
      i2c_bus1_n = i2cScanCount(Wire1, false);
      if (!mpuStart(Wire1, "17/18")) mpuStart(Wire, "8/9");
    }
    if (mpu_ok) mpuReadPitch();
    Serial.printf("STATUS oled=%d bme=%d lidar=%d hz=%u usL=%.2f usR=%.2f T=%.1f gps=%lu mpu=%d\n",
                  oled_ok, bme_ok, lidar_ok, (unsigned)lidar_hz,
                  isnan(left_m) ? -1 : left_m, isnan(right_m) ? -1 : right_m,
                  bme_ok ? t_c : NAN, (unsigned long)gps.charsProcessed(), mpu_ok);
  }
}
