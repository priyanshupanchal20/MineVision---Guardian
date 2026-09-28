/*
  NEO-6M GPS — outdoor sky required.
  TX of GPS -> GPIO15 (ESP RX), RX of GPS -> GPIO16 (ESP TX)
  9600 8N1. Library: TinyGPSPlus
*/
#include <TinyGPSPlus.h>
HardwareSerial GpsUart(2);
TinyGPSPlus gps;
void setup() {
  Serial.begin(115200);
  GpsUart.begin(9600, SERIAL_8N1, 15, 16);
  Serial.println("NEO-6M test — wait for FIX outdoors");
}
void loop() {
  while (GpsUart.available()) gps.encode(GpsUart.read());
  static uint32_t t;
  if (millis() - t < 1000) return;
  t = millis();
  Serial.printf("chars=%lu valid=%d lat=%.6f lon=%.6f sats=%d hdop=%.1f\n",
                gps.charsProcessed(), gps.location.isValid(),
                gps.location.lat(), gps.location.lng(),
                gps.satellites.value(), gps.hdop.hdop());
}
