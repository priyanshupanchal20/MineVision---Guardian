/*
  YD-ESP32-S3 board health — USB-OTG Serial 115200.
  No sensors required. 5Vin is NOT tested in software (IN-OUT jumper).
*/
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <esp_chip_info.h>
#include <esp_flash.h>
#include <esp_system.h>
#include <esp_mac.h>

static int i2cCount(TwoWire &bus, int sda, int scl) {
  bus.begin(sda, scl);
  bus.setClock(100000);
  bus.setTimeOut(50);
  int n = 0;
  for (uint8_t a = 0x08; a <= 0x77; a++) {
    bus.beginTransmission(a);
    if (bus.endTransmission() == 0) n++;
  }
  return n;
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  delay(800);
  Serial.println();
  Serial.println("=== YD-ESP32-S3 HEALTH CHECK ===");

  esp_chip_info_t chip;
  esp_chip_info(&chip);
  uint32_t flash_sz = 0;
  esp_flash_get_size(NULL, &flash_sz);
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);

  Serial.printf("chip: ESP32-S3  rev=%d  cores=%d\n", chip.revision, chip.cores);
  Serial.printf("features: %s%s%s\n",
                (chip.features & CHIP_FEATURE_WIFI_BGN) ? "WiFi " : "",
                (chip.features & CHIP_FEATURE_BLE) ? "BLE " : "",
                (chip.features & CHIP_FEATURE_EMB_PSRAM) ? "PSRAM-flag " : "");
  Serial.printf("CPU %u MHz  flash %u MB\n", getCpuFrequencyMhz(), (unsigned)(flash_sz / (1024 * 1024)));
  Serial.printf("MAC %02X:%02X:%02X:%02X:%02X:%02X\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  Serial.printf("heap free %u  min %u\n",
                (unsigned)ESP.getFreeHeap(), (unsigned)ESP.getMinFreeHeap());
  Serial.printf("PSRAM size %u  free %u\n",
                (unsigned)ESP.getPsramSize(), (unsigned)ESP.getFreePsram());
  Serial.printf("chip temp %.1f C\n", temperatureRead());

  const bool flash_ok = flash_sz >= 16 * 1024 * 1024;
  const bool psram_ok = ESP.getPsramSize() >= 7 * 1024 * 1024;
  const bool heap_ok = ESP.getFreeHeap() > 100000;
  Serial.printf("FLASH %s  PSRAM %s  HEAP %s\n",
                flash_ok ? "OK" : "FAIL", psram_ok ? "OK" : "FAIL", heap_ok ? "OK" : "FAIL");

  pinMode(1, OUTPUT);
  pinMode(2, OUTPUT);
  digitalWrite(1, HIGH);
  digitalWrite(2, HIGH);
  delay(50);
  const int g1 = digitalRead(1);
  const int g2 = digitalRead(2);
  digitalWrite(1, LOW);
  digitalWrite(2, LOW);
  Serial.printf("GPIO1/2 latch %d/%d %s\n", g1, g2, (g1 == 1 && g2 == 1) ? "OK" : "CHECK");

  const int n0 = i2cCount(Wire, 8, 9);
  const int n1 = i2cCount(Wire1, 17, 18);
  Serial.printf("I2C 8/9 devices=%d  (0 expected, no sensors)\n", n0);
  Serial.printf("I2C 17/18 devices=%d  (0 expected, no sensors)\n", n1);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  const int nets = WiFi.scanNetworks();
  Serial.printf("WiFi scan %s  APs=%d\n", nets >= 0 ? "OK" : "FAIL", nets);
  WiFi.scanDelete();
  WiFi.mode(WIFI_OFF);

  Serial.println("3V3: measure header 3V3 to GND with meter (expect ~3.3 V)");
  Serial.println("5Vin ~0.5 V is NORMAL if IN-OUT pads are unsoldered. Not chip damage.");
  Serial.println("=== HEALTH DONE ===");
}

void loop() {
  digitalWrite(1, (millis() / 300) % 2);
  delay(50);
}
