/*
  BME280 I2C — SDA GPIO8, SCL GPIO9, 3.3V
  Library: Adafruit BME280
*/
#include <Wire.h>
#include <Adafruit_BME280.h>
Adafruit_BME280 bme;
void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
  if (!bme.begin(0x76) && !bme.begin(0x77)) {
    Serial.println("BME280 not found. Check SDO address and 3.3V.");
    while (1) delay(1000);
  }
  Serial.println("BME280 OK");
}
void loop() {
  Serial.printf("T=%.2f C  RH=%.1f %%  P=%.1f hPa\n",
                bme.readTemperature(), bme.readHumidity(), bme.readPressure() / 100.0f);
  delay(500);
}
