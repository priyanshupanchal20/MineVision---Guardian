#include <Arduino.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <HardwareSerial.h>
#include <ArduinoJson.h>
#include <Adafruit_BME280.h>
#include <TinyGPSPlus.h>
#include <U8g2lib.h>
#include <esp_now.h>
#include <math.h>
#include <string.h>
#include <stdio.h>
#include <stddef.h>
#include "driver/gpio.h"
#include "config.h"

HardwareSerial Lidar(0);
HardwareSerial GpsUart(2);
HardwareSerial DriveUart(1);
Adafruit_BME280 bme;
TinyGPSPlus gps;
#if OLED_IS_SH1106
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
#else
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
#endif

static bool oled_ok = false, bme_ok = false, mpu_ok = false;
static uint8_t mpu_addr = 0, mpu_who = 0;
static char oled_zone[12] = "";

static volatile float front_m = NAN, left_m = NAN, right_m = NAN;
static volatile uint16_t lidar_strength = 0;
static float temperature = NAN, humidity = NAN, pressure = NAN;
static float pitch_deg = NAN, roll_deg = NAN, accel_x = NAN, accel_y = NAN, accel_z = NAN;
static int light_level = 0, light_raw = 0;
static volatile bool radar_ot1 = false, radar_ot2 = false, radar_occupied = false;

// LD2420: reject UART TX chatter; keep only a steady presence output (human).
static bool radarPinIsPresence(int pin, bool &stable_high) {
  static struct {
    int pin;
    bool last;
    uint8_t edges;
    uint32_t win_ms;
    uint32_t high_since;
    uint32_t low_since;
    bool high_ok;
  } st[2] = {{PIN_RADAR_OT1}, {PIN_RADAR_OT2}};

  int idx = (pin == PIN_RADAR_OT1) ? 0 : 1;
  auto &s = st[idx];
  const bool now = digitalRead(pin) == HIGH;
  const uint32_t t = millis();

  if (t - s.win_ms >= 200) {
    s.edges = 0;
    s.win_ms = t;
  }
  if (now != s.last) {
    if (s.edges < 250) s.edges++;
    s.last = now;
  }
  // UART TX chatters; a real presence pin stays steady for hundreds of ms.
  const bool chatter = s.edges >= 8;
  if (chatter) {
    s.high_ok = false;
    s.high_since = t;
    s.low_since = t;
    stable_high = false;
    return false;
  }

  if (now) {
    if (s.high_since == 0) s.high_since = t;
    s.low_since = 0;
    if (t - s.high_since >= RADAR_ASSERT_MS) s.high_ok = true;
  } else {
    if (s.low_since == 0) s.low_since = t;
    s.high_since = 0;
    if (t - s.low_since >= RADAR_CLEAR_MS) s.high_ok = false;
  }
  stable_high = s.high_ok;
  return true;  // pin behaves like a presence output (not UART)
}

// LD2420 FW >= 1.5.3 prints "ON" / "OFF" / "Range <cm>" on OT1 at 115200.
// OT1 (GPIO12) is the RX of DriveUart; DriveUart TX still goes to the Uno.
static volatile int radar_range_cm = -1;
static volatile bool radar_on_txt = false;
static uint32_t radar_uart_ms = 0;
static uint32_t radar_uart_bytes = 0;
static int16_t radar_hist[3];
static uint8_t radar_hist_n = 0, radar_hist_i = 0;
static uint8_t radar_near_hits = 0, radar_far_hits = 0;
static bool radar_near = false;

static void updateRadarHumanPresence();

static void radarResetRange() {
  radar_range_cm = -1;
  radar_hist_n = radar_hist_i = 0;
  radar_near_hits = radar_far_hits = 0;
  radar_near = false;
}

static int radarMedian() {
  if (radar_hist_n < 3) return radar_hist[(radar_hist_i + 2) % 3];
  const int a = radar_hist[0], b = radar_hist[1], c = radar_hist[2];
  return max(min(a, b), min(max(a, b), c));
}

static void radarPushRange(int cm) {
  if (cm < 0 || cm > 1000) return;
  radar_hist[radar_hist_i] = (int16_t)cm;
  radar_hist_i = (radar_hist_i + 1) % 3;
  if (radar_hist_n < 3) radar_hist_n++;
  radar_range_cm = radarMedian();

  const int near_cm = (int)(RADAR_ALERT_MAX_M * 100.0f + 0.5f);
  const int far_cm = (int)((RADAR_ALERT_MAX_M + RADAR_CLEAR_HYST_M) * 100.0f + 0.5f);
  if (cm <= near_cm) {
    radar_far_hits = 0;
    if (radar_near_hits < 255) radar_near_hits++;
  } else if (cm > far_cm) {
    radar_near_hits = 0;
    if (radar_far_hits < 255) radar_far_hits++;
  } else {
    radar_near_hits = radar_far_hits = 0;
  }
  if (radar_near_hits >= RADAR_NEAR_HITS) radar_near = true;
  if (radar_far_hits >= RADAR_FAR_HITS) radar_near = false;
}

static void handleRadarLine(const char *line) {
  radar_uart_ms = millis();
  if (strstr(line, "OFF")) {
    radar_on_txt = false;
    radarResetRange();
  } else {
    if (strstr(line, "ON")) radar_on_txt = true;
    const char *r = strstr(line, "Range");
    if (r) {
      radar_on_txt = true;
      radarPushRange(atoi(r + 5));
    }
  }
  updateRadarHumanPresence();
}

static void pollRadarUart() {
  static char buf[40];
  static uint8_t len = 0;
  while (DriveUart.available()) {
    const char c = (char)DriveUart.read();
    radar_uart_bytes++;
    if (c == '\r' || c == '\n') {
      if (len) {
        buf[len] = 0;
        handleRadarLine(buf);
      }
      len = 0;
      continue;
    }
    if (len < sizeof(buf) - 1) buf[len++] = c;
    else len = 0;
  }
}

static void updateRadarHumanPresence() {
  bool p2 = false;
  const bool ot2_presence_line = radarPinIsPresence(PIN_RADAR_OT2, p2);
  radar_ot1 = digitalRead(PIN_RADAR_OT1) == HIGH;
  radar_ot2 = digitalRead(PIN_RADAR_OT2) == HIGH;

  const float f = front_m, l = left_m, r = right_m;
  const bool ranging_near =
      (!isnan(f) && f > 0.0f && f <= RADAR_ALERT_MAX_M) ||
      (!isnan(l) && l > 0.0f && l <= RADAR_ALERT_MAX_M) ||
      (!isnan(r) && r > 0.0f && r <= RADAR_ALERT_MAX_M);

  if (radar_uart_ms) {
    if (millis() - radar_uart_ms > RADAR_STALE_MS) {
      radar_on_txt = false;
      radarResetRange();
    }
    const bool present = radar_on_txt || (ot2_presence_line && p2);
    radar_occupied = present && (radar_near || ranging_near);
    return;
  }

  // Older LD2420 FW: OT1 is the presence output and there is no range text.
  bool p1 = false;
  const bool ot1_presence_line = radarPinIsPresence(PIN_RADAR_OT1, p1);
  const bool present = (ot2_presence_line && p2) || (ot1_presence_line && p1);
  radar_occupied = present && ranging_near;
}
static double lat = NAN, lon = NAN;
static uint8_t sats = 0;
static bool gps_ok = false;
static float speed_kmh = 0, heading = 0;
static uint32_t gps_baud = 9600;
static bool gps_38400 = false;
static const char *volatile local_zone = "SAFE";
static const char *volatile buzzer_state = "off";
static WiFiMulti wifiMulti;
static IPAddress gw_ip;
static uint32_t gw_ok_ms = 0;

static bool ip_ok(const IPAddress &ip) {
  return ip[0] != 0 && ip[0] != 127 && ip[0] != 255;
}

static bool mdns_lookup(const char *name, IPAddress &ip) {
  String s = name;
  s.replace(".local", "");
  s.replace(".LOCAL", "");
  if (!s.length()) return false;
  ip = MDNS.queryHost(s.c_str());
  return ip_ok(ip);
}

static bool resolve_gateway() {
  if (ip_ok(gw_ip) && millis() - gw_ok_ms < 30000) return true;
  IPAddress ip;
#ifdef GATEWAY_IP
  if (ip.fromString(GATEWAY_IP)) {
    gw_ip = ip;
    gw_ok_ms = millis();
    return true;
  }
#endif
  if (ip.fromString(GATEWAY_HOST)) {
    gw_ip = ip;
    gw_ok_ms = millis();
    return true;
  }
  if (WiFi.hostByName(GATEWAY_HOST, ip) == 1 && ip_ok(ip)) {
    gw_ip = ip;
    gw_ok_ms = millis();
    Serial.printf("dns %s -> %s\n", GATEWAY_HOST, ip.toString().c_str());
    return true;
  }
  const char *names[] = {GATEWAY_HOST, "minevision", "darshan"};
  for (uint8_t i = 0; i < 3; i++) {
    if (mdns_lookup(names[i], ip)) {
      gw_ip = ip;
      gw_ok_ms = millis();
      Serial.printf("mdns %s -> %s\n", names[i], ip.toString().c_str());
      return true;
    }
  }
  return false;
}

enum class Buzz { Off, Single, Repeated, Continuous };
static volatile Buzz buzz = Buzz::Off;
static uint32_t buzz_t = 0;
static bool buzz_on = false;

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
  accel_x = isnan(accel_x) ? x : (0.55f * x + 0.45f * accel_x);
  accel_y = isnan(accel_y) ? y : (0.55f * y + 0.45f * accel_y);
  accel_z = isnan(accel_z) ? z : (0.55f * z + 0.45f * accel_z);
  roll_deg = atan2f(accel_y, accel_z) * 180.0f / PI;
  pitch_deg = atan2f(-accel_x, sqrtf(accel_y * accel_y + accel_z * accel_z)) * 180.0f / PI;
}

static uint32_t lidar_ok_ms = 0;
static uint32_t lidar_frames = 0;
static uint32_t lidar_restart_ms = 0;
static uint16_t lidar_cm_dbg = 0;

static void lidarKick() {
  const uint8_t enable[] = {0x5A, 0x05, 0x07, 0x01, 0x67};
  Lidar.write(enable, sizeof(enable));
}

static void lidarSetRate(uint16_t hz) {
  uint8_t b[6] = {0x5A, 0x06, 0x03, (uint8_t)(hz & 0xFF), (uint8_t)(hz >> 8), 0};
  b[5] = (uint8_t)(b[0] + b[1] + b[2] + b[3] + b[4]);
  Lidar.write(b, sizeof(b));
}

static void lidarBegin() {
  Lidar.setRxBufferSize(1024);
  Lidar.setTimeout(1);
  Lidar.begin(115200, SERIAL_8N1, PIN_LIDAR_RX, PIN_LIDAR_TX);
  delay(20);
  lidarKick();
  delay(20);
  lidarSetRate(250);
}

static int readTfmini(float &dist, uint16_t &strength) {
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
    lidar_frames++;
    lidar_ok_ms = millis();
  }
  if (!got) return 0;
  lidar_cm_dbg = cm;
  strength = st;
  // Lost / too-weak return must NOT keep a stale close range (that left the buzzer on).
  if (cm < 3 || cm > 1200) return -1;
  // A hand / dark clothing at <1.6 m is a weak target — still a real obstacle.
  if (st < 80 && !(cm <= 160 && st >= 12)) return -1;
  dist = cm * 0.01f;
  return 1;
}

static void recoverLidarIfSilent() {
  const uint32_t now = millis();
  if (now < 2500) return;
  if (now - lidar_ok_ms < 1500) return;
  if (now - lidar_restart_ms < 2500) return;
  lidar_restart_ms = now;
  Serial.println("LIDAR UART restart — unplug CH343 from silk TX/RX, keep USB-OTG");
  Lidar.end();
  delay(15);
  lidarBegin();
}

static UsEcho usL = {PIN_US_L_TRIG, PIN_US_L_ECHO, 0, 0, 0, 0, NAN, 0, false, 0, 0, NAN, 0};
static UsEcho usR = {PIN_US_R_TRIG, PIN_US_R_ECHO, 0, 0, 0, 0, NAN, 0, false, 0, 0, NAN, 0};
static volatile bool lidarCloseLive = false;
static uint32_t lidar_close_ms = 0;

static void updateLidar();

static float usPulseToM(uint32_t us) {
  if (us < US_MIN_US || us >= US_TIMEOUT_US) return NAN;
  const float sos = 331.3f + 0.606f * (isnan(temperature) ? 25.0f : temperature);
  const float m = (us * sos) / 2000000.0f;
  if (m < US_MIN_M || m > US_MAX_M) return NAN;
  return m;
}

static void usWaitIdle(UsEcho *ch, uint32_t max_us) {
  const uint32_t t0 = micros();
  while (gpio_get_level((gpio_num_t)ch->echo)) {
    if (micros() - t0 > max_us) break;
    if (Lidar.available() >= 9) updateLidar();
  }
}

static float pingOnce(UsEcho *ch) {
  usWaitIdle(ch, 20000);
  ch->st = 0;
  ch->us = 0;

  digitalWrite(ch->trig, LOW);
  delayMicroseconds(2);
  digitalWrite(ch->trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(ch->trig, LOW);

  const uint32_t t0 = micros();
  while (ch->st != 2) {
    const uint32_t now = micros();
    if (now - t0 > (uint32_t)US_TIMEOUT_US + 400) break;
    if (Lidar.available() >= 9) updateLidar();
    const int high = gpio_get_level((gpio_num_t)ch->echo);
    if (high) {
      if (ch->st == 0) {
        ch->t0 = now;
        ch->st = 1;
      }
    } else if (ch->st == 1) {
      ch->us = now - ch->t0;
      ch->st = 2;
    }
  }
  usWaitIdle(ch, 20000);
  if (ch->st != 2) {
    ch->us = 0;
    return NAN;
  }
  return usPulseToM(ch->us);
}

// Left sensor often needs a second ping for mid-range targets (weaker echo).
static float pingOnceRetry(UsEcho *ch) {
  float m = pingOnce(ch);
  if (!isnan(m)) return m;
  delayMicroseconds(400);
  updateLidar();
  return pingOnce(ch);
}

static float pingEcho(UsEcho *ch) {
  const float m = (ch == &usL) ? pingOnceRetry(ch) : pingOnce(ch);
  if (isnan(m)) {
    if (ch->miss < 250) ch->miss++;
    // Keep last good range briefly so OLED/telemetry do not blank on one miss.
    if (!isnan(ch->lock) && (millis() - ch->last_ms) < 450) {
      return ch->lock;
    }
    if (ch->miss >= 3) {
      ch->confirm = 0;
      ch->ghost = 0;
      ch->had_echo = false;
    }
    ch->last = NAN;
    ch->lock = NAN;
    ch->last_us = 0;
    return NAN;
  }

  // Reject sudden close spikes after a stable far lock (crosstalk / multipath).
  if (!isnan(ch->lock) && ch->lock > 1.15f && m < ZONE_BUZZ_US_M && (ch->lock - m) > 0.35f) {
    ch->ghost++;
    if (ch->ghost < 3) {
      ch->last_ms = millis();
      return ch->lock;
    }
    ch->confirm = US_CONFIRM;
    ch->ghost = 0;
    ch->miss = 0;
    ch->had_echo = true;
    ch->last = m;
    ch->lock = m;
    ch->last_us = ch->us;
    ch->last_ms = millis();
    return m;
  }
  ch->ghost = 0;

  if (!isnan(ch->last) && fabsf(m - ch->last) < 0.45f) {
    if (ch->confirm < 10) ch->confirm++;
  } else {
    ch->confirm = 1;
  }
  ch->miss = 0;
  ch->had_echo = true;
  ch->last = m;
  ch->last_us = ch->us;
  ch->last_ms = millis();
  // Accept mid/far ranges quickly so left matches right/LiDAR behaviour.
  if (ch->confirm >= US_CONFIRM || m >= 0.55f) {
    ch->lock = m;
    return m;
  }
  return isnan(ch->lock) ? m : ch->lock;
}

static bool inRange(float m) {
  return !isnan(m) && m >= US_MIN_M;
}

static bool usWarn(float m) {
  return inRange(m) && m < ZONE_WARN_M;
}

static bool usCloseLive(const UsEcho *ch) {
  return ch->confirm >= US_CONFIRM && inRange(ch->lock) && ch->lock < ZONE_BUZZ_US_M &&
         (millis() - ch->last_ms) < 120;
}

static bool obstacleTooClose() {
  if (lidarCloseLive && (millis() - lidar_close_ms) < 80) return true;
  if (usCloseLive(&usL)) return true;
  if (usCloseLive(&usR)) return true;
  return false;
}

static const char *visLabel() {
  if (light_level < 25) return "VIS DARK";
  if (light_level < 50) return "VIS LOW";
  return "VIS OK";
}

static void fmtM(char *buf, size_t n, const char *tag, float m) {
  if (isnan(m)) snprintf(buf, n, "%s --", tag);
  else snprintf(buf, n, "%s%.2f", tag, m);
}

static void fmtUs(char *buf, size_t n, const char *tag, float m, const UsEcho *ch) {
  if (ch->miss >= 12 && isnan(m)) snprintf(buf, n, "%sNC", tag);
  else if (isnan(m)) snprintf(buf, n, "%s --", tag);
  else snprintf(buf, n, "%s%.2f", tag, m);
}

static bool tiltAlertActive() {
  return mpu_ok && !isnan(pitch_deg) &&
         ((fabsf(pitch_deg) > 25.0f) || (fabsf(roll_deg) > 25.0f));
}

static const char *cabAdvice() {
  const char *zone = (const char *)local_zone;
  if (strcmp(zone, "DANGER") == 0) return "STOP VEHICLE";
  if (tiltAlertActive()) return "TILT ALERT";
  if (strcmp(zone, "WARNING") == 0) return "CRAWL MODE";
  return "NORMAL SPEED";
}

static void drawCabOled() {
  if (!oled_ok) return;
  const char *zone = (const char *)local_zone;
  const float f = front_m, l = left_m, r = right_m;
  const int vis = light_level;
  const bool human = radar_occupied;
  const bool danger = strcmp(zone, "DANGER") == 0;
  char l1[22], l2[22], l3[22], l4[22];

  oled.clearBuffer();
  if (danger) {
    oled.drawBox(0, 0, 128, 16);
    oled.setDrawColor(0);
    oled.setFont(u8g2_font_helvB12_tr);
    oled.drawStr(8, 13, "DANGER");
    oled.setDrawColor(1);
    oled.setFont(u8g2_font_7x13B_tf);
    oled.drawStr(0, 30, human ? "STOP + HUMAN" : "STOP VEHICLE");
    fmtUs(l2, sizeof(l2), "L ", l, &usL);
    fmtUs(l3, sizeof(l3), "R ", r, &usR);
    snprintf(l1, sizeof(l1), "%s  %s", l2, l3);
    oled.drawStr(0, 46, l1);
    fmtM(l4, sizeof(l4), "F ", f);
    snprintf(l1, sizeof(l1), "%s VIS%d%%", l4, vis);
    oled.drawStr(0, 62, l1);
  } else {
    oled.setFont(u8g2_font_helvB12_tr);
    oled.drawStr(0, 13, zone);
    oled.setFont(u8g2_font_7x13B_tf);
    if (human) {
      oled.drawStr(128 - oled.getStrWidth("HUMAN"), 12, "HUMAN");
    } else {
      snprintf(l1, sizeof(l1), "VIS %d%%", vis);
      oled.drawStr(128 - oled.getStrWidth(l1), 12, l1);
    }
    fmtM(l1, sizeof(l1), "F ", f);
    snprintf(l2, sizeof(l2), "%sm", l1);
    oled.drawStr(0, 30, l2);
    fmtUs(l2, sizeof(l2), "L ", l, &usL);
    fmtUs(l3, sizeof(l3), "R ", r, &usR);
    snprintf(l1, sizeof(l1), "%s  %s", l2, l3);
    oled.drawStr(0, 46, l1);
  // Cab/dashboard: HUMAN only when radar sees a person within RADAR_ALERT_MAX_M
  if (human) {
      if (radar_range_cm >= 0) snprintf(l4, sizeof(l4), "HUMAN %dcm", (int)radar_range_cm);
      else snprintf(l4, sizeof(l4), "HUMAN <=%dcm", (int)(RADAR_ALERT_MAX_M * 100.0f + 0.5f));
  } else {
      char advice[14];
      strncpy(advice, cabAdvice(), sizeof(advice) - 1);
      advice[sizeof(advice) - 1] = 0;
      if (!isnan(temperature)) {
        snprintf(l4, sizeof(l4), "%.0fC %s", temperature, advice);
      } else {
        snprintf(l4, sizeof(l4), "%s", advice);
      }
    }
    oled.drawStr(0, 62, l4);
  }
  oled.sendBuffer();
}

static void usProbe(UsEcho *ch, const char *name) {
  digitalWrite(ch->trig, LOW);
  delayMicroseconds(4);
  digitalWrite(ch->trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(ch->trig, LOW);
  const uint32_t t0 = micros();
  bool saw = false;
  uint32_t w = 0;
  while (micros() - t0 < 25000) {
    if (gpio_get_level((gpio_num_t)ch->echo)) {
      saw = true;
      const uint32_t r = micros();
      while (gpio_get_level((gpio_num_t)ch->echo) && (micros() - r) < 25000) {}
      w = micros() - r;
      break;
    }
  }
  if (!saw) {
    Serial.printf("US %s ECHO DEAD GPIO%d — check 5V, common GND, 2.2k/3.3k divider\n",
                  name, ch->echo);
  } else {
    Serial.printf("US %s echo OK %luus\n", name, (unsigned long)w);
  }
}

static void applyBuzzerLeds() {
  const bool too_close = obstacleTooClose();
  const float f = front_m, l = left_m, r = right_m;
  const bool side_warn = usWarn(l) || usWarn(r);
  if (too_close) local_zone = "DANGER";
  else if (side_warn || (!isnan(f) && f < ZONE_SAFE_M)) local_zone = "WARNING";
  else if (isnan(f) && isnan(l) && isnan(r)) local_zone = "UNKNOWN";
  else local_zone = "SAFE";

  digitalWrite(PIN_BUZZER, too_close ? HIGH : LOW);
  buzzer_state = too_close ? "continuous" : "off";
  buzz = too_close ? Buzz::Continuous : Buzz::Off;
  const char *zone = (const char *)local_zone;
  digitalWrite(PIN_LED_GREEN, strcmp(zone, "SAFE") == 0);
  digitalWrite(PIN_LED_YELLOW, strcmp(zone, "WARNING") == 0);
  digitalWrite(PIN_LED_RED, too_close);
  digitalWrite(PIN_LED_FOG, light_level < 35);
  // PIN_DRIVE_STOP is driven in publishDriveSafety() — HIGH only on DANGER.

  static bool prev_buzz = false;
  if (prev_buzz != too_close) {
    prev_buzz = too_close;
    Serial.printf("BUZZ %s  F=%.2f L=%.2f R=%.2f lidarHit=%d\n",
                  too_close ? "ON" : "OFF", f, l, r, (int)lidarCloseLive);
  }
}

// ESP32 → Uno drive policy:
//   SAFE or WARNING  → allow phone drive (heartbeat SAFE / WARNING)
//   DANGER           → stop motors immediately
//   leaving DANGER   → CLEAR once, then SAFE/WARNING (does not auto-resume)
static void publishDriveSafety() {
  static uint32_t t = 0;
  static bool was_danger = false;
  const uint32_t gap = 1000u / DRIVE_UART_HZ;
  if (millis() - t < gap) return;
  t = millis();

  const char *zone = (const char *)local_zone;
  const bool danger = (strcmp(zone, "DANGER") == 0);
  // Hard estop pin: HIGH only in DANGER (SAFE + WARNING keep motors allowed).
  digitalWrite(PIN_DRIVE_STOP, danger ? HIGH : LOW);

  if (danger) {
    DriveUart.println("DANGER");
    was_danger = true;
  } else if (was_danger) {
    DriveUart.println("CLEAR");
    was_danger = false;
  } else if (strcmp(zone, "WARNING") == 0) {
    DriveUart.println("WARNING");  // Uno treats WARNING like SAFE (drive OK)
  } else {
    DriveUart.println("SAFE");
  }
}

static void maybeOled() {
  static const char *oled_shown = "";
  static uint32_t oled_t = 0;
  static float oled_f = NAN, oled_l = NAN, oled_r = NAN;
  static int oled_vis = -1;
  static bool oled_human = false;
  const char *zone = (const char *)local_zone;
  const bool too_close = (buzz == Buzz::Continuous);
  const bool zone_changed = (oled_shown != zone);
  const float f = front_m, l = left_m, r = right_m;
  const int vis = light_level;
  const bool human = radar_occupied;
  const bool moved =
      (isnan(oled_f) != isnan(f)) || (!isnan(f) && !isnan(oled_f) && fabsf(f - oled_f) >= OLED_DELTA_M) ||
      (isnan(oled_l) != isnan(l)) || (!isnan(l) && !isnan(oled_l) && fabsf(l - oled_l) >= OLED_DELTA_M) ||
      (isnan(oled_r) != isnan(r)) || (!isnan(r) && !isnan(oled_r) && fabsf(r - oled_r) >= OLED_DELTA_M) ||
      (abs(vis - oled_vis) >= 2) || (human != oled_human);
  const uint32_t oled_ms = too_close ? 25 : OLED_REFRESH_MS;
  if (zone_changed || moved || (millis() - oled_t >= oled_ms)) {
    oled_t = millis();
    oled_shown = zone;
    oled_f = f;
    oled_l = l;
    oled_r = r;
    oled_vis = vis;
    oled_human = human;
    strncpy(oled_zone, zone, sizeof(oled_zone) - 1);
    drawCabOled();
  }
}

// HTTP ingest must never stall the OLED path — latest body wins on core 0 net task.
static constexpr size_t PUB_BODY_MAX = 896;
static char pubBody[PUB_BODY_MAX];
static volatile bool pubReady = false;
static portMUX_TYPE pubMux = portMUX_INITIALIZER_UNLOCKED;

static void queueIngest(const String &body) {
  if (body.length() == 0 || body.length() >= PUB_BODY_MAX) return;
  portENTER_CRITICAL(&pubMux);
  memcpy(pubBody, body.c_str(), body.length() + 1);
  pubReady = true;
  portEXIT_CRITICAL(&pubMux);
}

static void netTask(void *) {
  static uint32_t http_block_until = 0;
  static uint32_t http_backoff = 150;
  for (;;) {
    wifiMulti.run();
    if (WiFi.status() != WL_CONNECTED) {
      gw_ok_ms = 0;
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    if (!pubReady) {
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    char local[PUB_BODY_MAX];
    portENTER_CRITICAL(&pubMux);
    memcpy(local, pubBody, PUB_BODY_MAX);
    pubReady = false;
    portEXIT_CRITICAL(&pubMux);

    if (millis() < http_block_until) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    if (!resolve_gateway()) {
      http_block_until = millis() + 800;
      Serial.println("gateway name not found");
      continue;
    }

    WiFiClient client;
    HTTPClient http;
    http.setConnectTimeout(HTTP_CONNECT_MS);
    http.setTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(client, gw_ip.toString().c_str(), GATEWAY_PORT, "/api/v1/ingest")) {
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    http.addHeader("Content-Type", "application/json");
    const int code = http.POST(local);
    http.end();
    if (code <= 0) {
      gw_ok_ms = 0;
      http_backoff = http_backoff < 800 ? http_backoff * 2 : 800;
      http_block_until = millis() + http_backoff;
      Serial.printf("ingest fail %d backoff %lums\n", code, (unsigned long)http_backoff);
    } else {
      http_backoff = 150;
      http_block_until = 0;
      Serial.printf("ingest %d -> %s\n", code, gw_ip.toString().c_str());
    }
  }
}

static void publish() {
  const float f = front_m, l = left_m, r = right_m;
  const uint16_t st = lidar_strength;
  const char *zone = (const char *)local_zone;
  const char *buzzs = (const char *)buzzer_state;

  JsonDocument doc;
  doc["vehicle_id"] = VEHICLE_ID;
  if (!isnan(f)) doc["front_distance"] = f;
  else doc["front_distance"] = nullptr;
  if (!isnan(l)) doc["left_distance"] = l;
  else doc["left_distance"] = nullptr;
  if (!isnan(r)) doc["right_distance"] = r;
  else doc["right_distance"] = nullptr;
  doc["lidar_strength"] = st;
  if (!isnan(temperature)) doc["temperature"] = temperature;
  if (!isnan(humidity)) doc["humidity"] = humidity;
  if (!isnan(pressure)) doc["pressure_hpa"] = pressure;
  doc["tilt_alert"] = tiltAlertActive();
  if (mpu_ok && !isnan(pitch_deg)) {
    doc["pitch_deg"] = pitch_deg;
    doc["roll_deg"] = roll_deg;
    doc["accel_x_g"] = accel_x;
    doc["accel_y_g"] = accel_y;
    doc["accel_z_g"] = accel_z;
  }
  doc["cab_advice"] = cabAdvice();
  doc["light_level"] = light_level;
  doc["visibility_pct"] = light_level;
  doc["light_raw"] = light_raw;
  doc["motion_detected"] = radar_occupied;
  doc["radar_occupied"] = radar_occupied;
  doc["radar_ot1"] = radar_ot1;
  doc["radar_ot2"] = radar_ot2;
  doc["radar_distance_m"] = nullptr;  // LD2420 board has no UART TX
  doc["gps_valid"] = gps_ok;
  doc["gps_sats"] = sats;
  if (gps_ok) {
    doc["latitude"] = lat;
    doc["longitude"] = lon;
    doc["speed_kmh_gps"] = speed_kmh;
    doc["heading_deg"] = heading;
  } else {
    doc["latitude"] = nullptr;
    doc["longitude"] = nullptr;
    doc["speed_kmh_gps"] = 0;
    doc["heading_deg"] = 0;
  }
  doc["local_zone"] = zone;
  doc["buzzer_state"] = buzzs;
  doc["firmware"] = FIRMWARE_VERSION;

  String body;
  serializeJson(doc, body);
  static uint32_t ser_t = 0;
  if (millis() - ser_t >= 400) {
    ser_t = millis();
    Serial.println(body);
  }

  JsonDocument v2v;
  v2v["vehicle_id"] = VEHICLE_ID;
  v2v["latitude"] = gps_ok ? lat : 0;
  v2v["longitude"] = gps_ok ? lon : 0;
  v2v["speed"] = speed_kmh;
  v2v["direction"] = heading;
  v2v["risk_level"] = zone;
  v2v["fog_mode"] = light_level < 35;
  v2v["emergency"] = strcmp(zone, "DANGER") == 0;
  String v2vBody;
  serializeJson(v2v, v2vBody);
  uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bcast, (uint8_t *)v2vBody.c_str(), v2vBody.length());

  queueIngest(body);
}

void setup() {
  setCpuFrequencyMhz(240);
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(250);
  Serial.println("MineVision Guardian hub " FIRMWARE_VERSION);
  Serial.printf("cpu %u MHz  gateway %s:%d  ssid %s\n",
                getCpuFrequencyMhz(), GATEWAY_HOST, GATEWAY_PORT, WIFI_SSID);

  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_FOG, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_DRIVE_STOP, OUTPUT);
  digitalWrite(PIN_DRIVE_STOP, LOW);
  pinMode(PIN_RADAR_OT2, INPUT_PULLDOWN);
  DriveUart.setRxBufferSize(256);
  DriveUart.begin(115200, SERIAL_8N1, PIN_RADAR_OT1, PIN_DRIVE_UART_TX);
  DriveUart.setRxTimeout(1);
  Serial.printf("drive UART TX=GPIO%d + STOP=GPIO%d\n", PIN_DRIVE_UART_TX, PIN_DRIVE_STOP);
  Serial.printf("LD2420 range text on OT1=GPIO%d, presence OT2=GPIO%d\n",
                PIN_RADAR_OT1, PIN_RADAR_OT2);
  digitalWrite(PIN_BUZZER, LOW);
  pinMode(PIN_US_L_TRIG, OUTPUT);
  pinMode(PIN_US_R_TRIG, OUTPUT);
  digitalWrite(PIN_US_L_TRIG, LOW);
  digitalWrite(PIN_US_R_TRIG, LOW);
  pinMode(PIN_US_L_ECHO, INPUT);
  pinMode(PIN_US_R_ECHO, INPUT);
  usProbe(&usL, "LEFT");
  delay(70);
  usProbe(&usR, "RIGHT");
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_LDR_AO, ADC_11db);

  lidarBegin();
  GpsUart.setRxBufferSize(512);
  GpsUart.begin(gps_baud, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);
  Wire.setTimeOut(40);

  uint8_t oled_addr = OLED_I2C_ADDR;
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
    char splash[22];
    snprintf(splash, sizeof(splash), "MineVision Hub %s", FIRMWARE_VERSION);
    oled.drawStr(0, 12, splash);
    oled.drawStr(0, 28, "LiDAR+US+LD2420");
    char human_line[24];
    snprintf(human_line, sizeof(human_line), "human<=%dcm alert",
             (int)(RADAR_ALERT_MAX_M * 100.0f + 0.5f));
    oled.drawStr(0, 44, human_line);
    oled.drawStr(0, 60, GATEWAY_HOST);
    oled.sendBuffer();
  }

  bme_ok = bme.begin(0x76, &Wire) || bme.begin(0x77, &Wire);
  Serial.println(bme_ok ? "BME OK" : "BME --");

  Wire1.begin(PIN_MPU_SDA, PIN_MPU_SCL);
  Wire1.setClock(100000);
  Wire1.setTimeOut(80);
  tryMpu(0x68) || tryMpu(0x69);
  if (mpu_ok) Serial.printf("MPU OK who=0x%02X @0x%02X\n", mpu_who, mpu_addr);
  else Serial.println("MPU --");

  wifiMulti.addAP(WIFI_SSID, WIFI_PASSWORD);
#ifdef WIFI_SSID_2
  if (WIFI_SSID_2[0]) wifiMulti.addAP(WIFI_SSID_2, WIFI_PASSWORD_2);
#endif
#ifdef WIFI_SSID_3
  if (WIFI_SSID_3[0]) wifiMulti.addAP(WIFI_SSID_3, WIFI_PASSWORD_3);
#endif
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setBandMode(WIFI_BAND_MODE_2G_ONLY);
  // Do not raise min security — phone hotspots vary (WPA2/WPA3).
  Serial.print("Wi-Fi ");
  uint32_t t0 = millis();
  while (wifiMulti.run() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(WiFi.localIP());
    if (!MDNS.begin("dumper01")) Serial.println("mdns begin fail");
  } else {
    Serial.println(" offline (local safety still runs)");
  }

  if (esp_now_init() == ESP_OK) {
    uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, bcast, 6);
    peer.channel = 0;
    peer.encrypt = false;
    esp_now_add_peer(&peer);
  }
}

static void updateLidar() {
  float d;
  uint16_t st;
  int lr = readTfmini(d, st);
  if (lr == 1) {
    front_m = d;
    lidar_strength = st;
    lidarCloseLive = (d < ZONE_BUZZ_LIDAR_M);
    if (lidarCloseLive) lidar_close_ms = millis();
  } else if (lr == -1) {
    front_m = NAN;
    lidar_strength = st;
    lidarCloseLive = false;
  } else if (millis() - lidar_close_ms > 20) {
    lidarCloseLive = false;
    if (!isnan((float)front_m) && (millis() - lidar_ok_ms) > 40) {
      front_m = NAN;
      lidar_strength = 0;
    }
  }
  applyBuzzerLeds();
}

static void usGapMs(uint32_t ms) {
  // Drain LiDAR during HC-SR04 settle; yield often enough for the task WDT.
  const uint32_t t0 = millis();
  uint32_t spins = 0;
  while (millis() - t0 < ms) {
    updateLidar();
    delayMicroseconds(120);
    if ((++spins & 15) == 0) vTaskDelay(1);
  }
}

static void safetyTask(void *) {
  uint32_t rec_t = 0;
  for (;;) {
    updateLidar();
    // Ping left every cycle (same as right) — old miss throttle made L blank until danger.
    left_m = pingEcho(&usL);
    usGapMs(US_PING_GAP_MS);
    right_m = pingEcho(&usR);
    usGapMs(US_SIDE_GAP_MS);
    if (millis() - rec_t >= 500) {
      rec_t = millis();
      recoverLidarIfSilent();
    }
  }
}

// OLED + BME on core 0 so the display never waits on the ultrasonic safety loop.
static void uiTask(void *) {
  uint32_t env_t = 0;
  for (;;) {
    maybeOled();
    if (millis() - env_t >= 600) {
      env_t = millis();
      if (bme_ok) {
        temperature = bme.readTemperature();
        humidity = bme.readHumidity();
        pressure = bme.readPressure() / 100.0f;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(12));
  }
}

void loop() {
  static bool started = false;
  if (!started) {
    started = true;
    xTaskCreatePinnedToCore(safetyTask, "safe", 6144, nullptr, 5, nullptr, 1);
    xTaskCreatePinnedToCore(netTask, "net", 8192, nullptr, 1, nullptr, 0);
    xTaskCreatePinnedToCore(uiTask, "ui", 6144, nullptr, 3, nullptr, 0);
    Serial.println("safe@1 net+ui@0  cpu 240 MHz (safe max)");
  }

  static uint32_t slow_t = 0;
  if (millis() - slow_t >= 100) {
    slow_t = millis();
    light_raw = analogRead(PIN_LDR_AO);
    light_level = constrain(map(light_raw, 0, 4095, 100, 0), 0, 100);
    sampleMpu();
    updateRadarHumanPresence();
  }
  pollRadarUart();

  uint8_t n = 0;
  while (GpsUart.available() && n < 32) {
    gps.encode(GpsUart.read());
    n++;
  }
  if (!gps_38400 && millis() > 4000 && gps.charsProcessed() < 20) {
    gps_38400 = true;
    gps_baud = 38400;
    GpsUart.end();
    GpsUart.begin(gps_baud, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);
  }
  if (gps.location.isValid()) {
    gps_ok = true;
    lat = gps.location.lat();
    lon = gps.location.lng();
    sats = gps.satellites.value();
    speed_kmh = gps.speed.kmph();
    heading = gps.course.deg();
  }

  static uint32_t log_t = 0;
  if (millis() - log_t >= 400) {
    log_t = millis();
    Serial.printf("LIDAR F=%.2f  US L=%.2f (%luus miss%u c%u) R=%.2f (%luus miss%u c%u) "
                  "RADAR occ=%d on=%d rng=%dcm bytes=%lu ot2=%d\n",
                  (float)front_m, (float)left_m, (unsigned long)usL.last_us, (unsigned)usL.miss,
                  (unsigned)usL.confirm,
                  (float)right_m, (unsigned long)usR.last_us, (unsigned)usR.miss,
                  (unsigned)usR.confirm,
                  (int)radar_occupied, (int)radar_on_txt, (int)radar_range_cm,
                  (unsigned long)radar_uart_bytes, (int)radar_ot2);
  }

  static uint32_t pub_t = 0;
  static bool pub_human = false;
  const bool human_changed = radar_occupied != pub_human;
  const uint32_t pub_gap = obstacleTooClose() ? 80 : (1000u / TELEMETRY_HZ);
  if (human_changed || millis() - pub_t > pub_gap) {
    pub_human = radar_occupied;
    pub_t = millis();
    publish();
  }
  publishDriveSafety();
  delay(1);
}
