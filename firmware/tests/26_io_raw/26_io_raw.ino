/*
  NEW operator I/O test — 5mm LEDs + active buzzer.
  Green GPIO1, Yellow GPIO2, Red GPIO42, Fog GPIO41.
  Buzzer GPIO6. 5 V buzzer: use NPN, do not feed 5 V into the pin.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <stdio.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
static bool oled_ok = false;

static const int PIN_G = 1, PIN_Y = 2, PIN_R = 42, PIN_F = 41, PIN_BZ = 6;

static void allOff() {
  digitalWrite(PIN_G, LOW);
  digitalWrite(PIN_Y, LOW);
  digitalWrite(PIN_R, LOW);
  digitalWrite(PIN_F, LOW);
  digitalWrite(PIN_BZ, LOW);
}

static void show(const char *led, const char *buzz) {
  if (!oled_ok) return;
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "NEW IO RAW");
  oled.drawStr(0, 26, led);
  oled.drawStr(0, 40, buzz);
  oled.drawStr(0, 52, "5mm LED + 330R");
  oled.drawStr(0, 62, "5V buzz via NPN");
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(400);
  Serial.println("NEW IO RAW  G1 Y2 R42 F41  BZ6");

  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_Y, OUTPUT);
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_F, OUTPUT);
  pinMode(PIN_BZ, OUTPUT);
  allOff();

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
  struct Step {
    const char *led;
    const char *buzz;
    int g, y, r, f, bz;
    int ms;
  };
  static const Step steps[] = {
    {"LED green  GPIO1", "buzz off", 1, 0, 0, 0, 0, 700},
    {"LED yellow GPIO2", "buzz off", 0, 1, 0, 0, 0, 700},
    {"LED red    GPIO42", "buzz off", 0, 0, 1, 0, 0, 700},
    {"LED fog    GPIO41", "buzz off", 0, 0, 0, 1, 0, 700},
    {"LEDs all on", "buzz BEEP", 1, 1, 1, 1, 1, 400},
    {"LEDs all on", "buzz off", 1, 1, 1, 1, 0, 400},
    {"LEDs all on", "buzz BEEP", 1, 1, 1, 1, 1, 400},
    {"all off", "buzz off", 0, 0, 0, 0, 0, 500},
  };

  for (const Step &s : steps) {
    digitalWrite(PIN_G, s.g);
    digitalWrite(PIN_Y, s.y);
    digitalWrite(PIN_R, s.r);
    digitalWrite(PIN_F, s.f);
    digitalWrite(PIN_BZ, s.bz);
    show(s.led, s.buzz);
    Serial.printf("%s  %s\n", s.led, s.buzz);
    delay(s.ms);
  }
}
