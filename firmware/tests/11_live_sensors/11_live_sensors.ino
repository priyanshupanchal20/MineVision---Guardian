/*
  Live bench — every wired sensor except 24 GHz radar.
  GPS = UART2 GPIO15/16. LiDAR = UART0 silk RX/TX. Serial = USB-OTG CDC.
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

static bool oled_ok = false, bme_ok = false, mpu_ok = false, lidar_ok = false;
static const char *mpu_bus_name = "nf";
static float lidar_m = NAN, lidar_raw_m = NAN;
static uint16_t lidar_st = 0;
static uint32_t lidar_hz = 0, lidar_frames = 0, lidar_hz_t = 0;
static float left_m = NAN, right_m = NAN;
static float t_c = NAN, rh = NAN, p_hpa = NAN;
static float pitch = NAN, roll = NAN;
static uint32_t gps_baud = 9600;
static uint32_t gps_chars_at_switch = 0;

static uint16_t med3(uint16_t a, uint16_t b, uint16_t c) {
  if (a > b) { uint16_t t = a; a = b; b = t; }
  if (b > c) { uint16_t t = b; b = c; c = t; }
  if (a > b) { uint16_t t = a; a = b; b = t; }
  return b;
}

static bool readTfminiLatest() {
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

  lidar_raw_m = cm * 0.01f;
  lidar_st = st;
  lidar_frames++;
  /* No median — extra frames = lag. Show the newest valid sample. */
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
  unsigned long us = pulseIn(echo, HIGH, 12000);  // ~2 m, must not stall LiDAR
  if (us == 0) return NAN;
  const float m = (us * 0.0343f) / 2.0f;
  if (m < 0.02f || m > 4.00f) return NAN;
  return m;
}

static float median3f(float a, float b, float c) {
  if (isnan(a) || isnan(b) || isnan(c)) return NAN;
  if (a > b) { float t = a; a = b; b = t; }
  if (b > c) { float t = b; b = c; c = t; }
  if (a > b) { float t = a; a = b; b = t; }
  return b;
}

static void sampleUs(float *out, int trig, int echo) {
  const float d = pingUs(trig, echo);
  static float lh0 = NAN, lh1 = NAN, lh2 = NAN;
  static float rh0 = NAN, rh1 = NAN, rh2 = NAN;
  float *h0, *h1, *h2;
  if (out == &left_m) { h0 = &lh0; h1 = &lh1; h2 = &lh2; }
  else { h0 = &rh0; h1 = &rh1; h2 = &rh2; }
  *h0 = *h1; *h1 = *h2; *h2 = d;
  const float med = median3f(*h0, *h1, *h2);
  *out = isnan(med) ? d : med;
}

static void feedGps() {
  while (GpsUart.available()) gps.encode(GpsUart.read());
}

static void maybeSwitchGpsBaud() {
  if (gps_baud != 9600) return;
  if (millis() < 4000) return;
  if (gps.charsProcessed() > gps_chars_at_switch) return;
  gps_baud = 38400;
  GpsUart.end();
  delay(20);
  GpsUart.begin(38400, SERIAL_8N1, 15, 16);
  Serial.println("GPS: no NMEA at 9600 — retry 38400");
}

static void drawOled() {
  if (!oled_ok) return;
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);

  if (bme_ok) snprintf(line, sizeof(line), "BME OK %4.1fC %2.0f%%", t_c, rh);
  else snprintf(line, sizeof(line), "BME --  I2C 8/9");
  oled.drawStr(0, 10, line);

  if (lidar_ok) snprintf(line, sizeof(line), "LID %4dcm %uHz", (int)lroundf(lidar_m * 100.0f), (unsigned)lidar_hz);
  else snprintf(line, sizeof(line), "LID -- cm %uHz", (unsigned)lidar_hz);
  oled.drawStr(0, 22, line);

  char lbuf[8], rbuf[8];
  if (isnan(left_m)) strcpy(lbuf, "--");
  else snprintf(lbuf, sizeof(lbuf), "%d", (int)lroundf(left_m * 100.0f));
  if (isnan(right_m)) strcpy(rbuf, "--");
  else snprintf(rbuf, sizeof(rbuf), "%d", (int)lroundf(right_m * 100.0f));
  snprintf(line, sizeof(line), "US L%s R%s cm", lbuf, rbuf);
  oled.drawStr(0, 34, line);

  if (mpu_ok) snprintf(line, sizeof(line), "MPU OK %s P%.0f", mpu_bus_name, pitch);
  else snprintf(line, sizeof(line), "MPU --  SDA17 SCL18");
  oled.drawStr(0, 46, line);

  const bool gps_talk = gps.charsProcessed() > 20;
  if (gps.location.isValid()) {
    snprintf(line, sizeof(line), "GPS FIX %d sats", gps.satellites.value());
  } else if (gps_talk) {
    snprintf(line, sizeof(line), "GPS NMEA nofix");
  } else {
    snprintf(line, sizeof(line), "GPS --  TX15 RX16");
  }
  oled.drawStr(0, 58, line);
  oled.sendBuffer();
}

static bool mpuStart(TwoWire &bus, const char *name) {
  bus.setClock(100000);
  bus.setTimeOut(50);
  if (!(mpu.begin(0x68, &bus) || mpu.begin(0x69, &bus))) return false;
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  mpu_ok = true;
  mpu_bus_name = name;
  Serial.printf("MPU-6050 OK on %s\n", name);
  return true;
}

static void i2cDump(TwoWire &bus, const char *tag) {
  Serial.printf("I2C %s:", tag);
  int n = 0;
  for (uint8_t a = 0x08; a <= 0x77; a++) {
    bus.beginTransmission(a);
    if (bus.endTransmission() == 0) {
      Serial.printf(" 0x%02X", a);
      n++;
    }
  }
  if (!n) Serial.print(" (none)");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(500);
  Serial.println();
  Serial.println("=== SENSOR BENCH  no radar  ===");
  Serial.println("BME OLED US-L US-R LIDAR GPS  (MPU optional)");
  Serial.flush();

  pinMode(7, OUTPUT);   // left TRIG (wires swapped)
  pinMode(47, OUTPUT);  // right TRIG
  pinMode(13, INPUT);   // left ECHO
  pinMode(21, INPUT);   // right ECHO

  Lidar.setRxBufferSize(1024);
  Lidar.setTimeout(5);
  Lidar.begin(115200, SERIAL_8N1, 44, 43);
  delay(50);
  const uint8_t tf_on[] = {0x5A, 0x05, 0x07, 0x01, 0x67};
  const uint8_t hz100[] = {0x5A, 0x06, 0x03, 0x64, 0x00, 0xC7};
  const uint8_t tf_save[] = {0x5A, 0x04, 0x11, 0x6F};
  Lidar.write(tf_on, sizeof(tf_on));
  delay(20);
  Lidar.write(hz100, sizeof(hz100));
  delay(20);
  Lidar.write(tf_save, sizeof(tf_save));
  while (Lidar.available()) Lidar.read();

  GpsUart.setRxBufferSize(512);
  GpsUart.begin(9600, SERIAL_8N1, 15, 16);

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
    oled.setBusClock(400000);
    oled.begin();
    oled.clearBuffer();
    oled.setFont(u8g2_font_6x12_tf);
    oled.drawStr(0, 12, "SENSOR CHECK");
    oled.drawStr(0, 26, "BME  LIDAR  US");
    oled.drawStr(0, 40, "MPU  GPS  OLED");
    oled.drawStr(0, 56, "watch 5 lines...");
    oled.sendBuffer();
    Serial.printf("OLED OK 0x%02X\n", oled_addr);
    delay(1200);
  } else {
    Serial.println("OLED not found");
  }

  bme_ok = bme.begin(0x76, &Wire) || bme.begin(0x77, &Wire);
  Serial.println(bme_ok ? "BME280 OK" : "BME280 not found");

  Wire1.begin(17, 18);
  Wire1.setClock(100000);
  Wire1.setTimeOut(50);
  i2cDump(Wire, "8/9");
  i2cDump(Wire1, "17/18");

  if (!mpuStart(Wire1, "17/18")) {
    if (!mpuStart(Wire, "8/9")) {
      Serial.println("MPU-6050 not found on 17/18 or 8/9");
    }
  }

  lidar_hz_t = millis();
}

void loop() {
  readTfminiLatest();
  uint8_t gps_n = 0;
  while (GpsUart.available() && gps_n < 48) {
    gps.encode(GpsUart.read());
    gps_n++;
  }
  maybeSwitchGpsBaud();

  const uint32_t now = millis();
  if (now - lidar_hz_t >= 1000) {
    lidar_hz = lidar_frames;
    lidar_frames = 0;
    lidar_hz_t = now;
  }

  static uint32_t us_t = 0;
  static bool ping_left = true;
  if (now - us_t >= 100) {
    us_t = now;
    if (ping_left) sampleUs(&left_m, 7, 13);
    else sampleUs(&right_m, 47, 21);
    ping_left = !ping_left;
    readTfminiLatest();
  }

  static uint32_t oled_t = 0;
  if (now - oled_t >= 70) {
    oled_t = now;
    drawOled();
  }

  static uint32_t env_t = 0;
  if (now - env_t >= 800) {
    env_t = now;
    if (bme_ok) {
      t_c = bme.readTemperature();
      rh = bme.readHumidity();
      p_hpa = bme.readPressure() / 100.0f;
    }
    if (mpu_ok) {
      sensors_event_t a, g, temp;
      mpu.getEvent(&a, &g, &temp);
      roll = atan2f(a.acceleration.y, a.acceleration.z) * 180.0f / PI;
      pitch = atan2f(-a.acceleration.x,
                     sqrtf(a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z)) *
              180.0f / PI;
    }
    Serial.printf(
        "STATUS oled=%d bme=%d lidar=%d usL=%.2f usR=%.2f "
        "T=%.2f RH=%.1f P=%.1f lidar_m=%.2f lidar_hz=%u str=%u "
        "gps_chars=%lu gps_valid=%d mpu=%d\n",
        oled_ok ? 1 : 0, bme_ok ? 1 : 0, lidar_ok ? 1 : 0,
        isnan(left_m) ? -1.0f : left_m, isnan(right_m) ? -1.0f : right_m,
        bme_ok ? t_c : NAN, bme_ok ? rh : NAN, bme_ok ? p_hpa : NAN,
        lidar_ok ? lidar_m : -1.0f, (unsigned)lidar_hz, lidar_st,
        (unsigned long)gps.charsProcessed(), gps.location.isValid() ? 1 : 0,
        mpu_ok ? 1 : 0);
  }
}
