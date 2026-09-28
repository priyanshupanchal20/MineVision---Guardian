/*
  1.30" IIC V2.2 OLED — SH1106 128x64 on I2C0 with BME280.
  Front silk left → right: VCC  GND  SCK  SDA
  VCC → 3V3   GND → GND   SCK → GPIO9   SDA → GPIO8
  Do NOT use pads 17/18 (those are MPU-6050).
*/
#include <Wire.h>
#include <U8g2lib.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

static bool probe(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
  Wire.setClock(400000);

  uint8_t addr = 0x3C;
  if (!probe(addr) && probe(0x3D)) addr = 0x3D;
  if (!probe(addr)) {
    Serial.println("OLED not found. Check 3V3, GND, SCK=GPIO9, SDA=GPIO8.");
    while (1) delay(1000);
  }

  oled.setI2CAddress(addr << 1);
  oled.begin();
  Serial.printf("OLED OK at 0x%02X  (if image is shifted, this board may be SSD1306)\n", addr);
}

void loop() {
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "MINEVISION CAB");
  oled.setFont(u8g2_font_helvB12_tr);
  oled.drawStr(0, 28, "DANGER");
  oled.setFont(u8g2_font_helvB18_tr);
  oled.drawStr(0, 48, "2.4 m");
  oled.setFont(u8g2_font_7x13B_tf);
  oled.drawStr(0, 63, "STOP VEHICLE");
  oled.sendBuffer();
  delay(1500);

  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "MINEVISION CAB");
  oled.setFont(u8g2_font_helvB12_tr);
  oled.drawStr(0, 28, "WARNING");
  oled.setFont(u8g2_font_helvB18_tr);
  oled.drawStr(0, 48, "5.1 m");
  oled.setFont(u8g2_font_7x13B_tf);
  oled.drawStr(0, 63, "CRAWL MODE");
  oled.sendBuffer();
  delay(1500);

  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);
  oled.drawStr(0, 10, "MINEVISION CAB");
  oled.setFont(u8g2_font_helvB12_tr);
  oled.drawStr(0, 28, "SAFE");
  oled.setFont(u8g2_font_helvB18_tr);
  oled.drawStr(0, 48, "9.2 m");
  oled.setFont(u8g2_font_7x13B_tf);
  oled.drawStr(0, 63, "NORMAL SPEED");
  oled.sendBuffer();
  delay(1500);
}
