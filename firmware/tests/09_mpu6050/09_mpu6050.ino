/*
  MPU-6050 on I2C1 — does NOT use pads 8/9 (those are BME280).
  YD-ESP32-S3: SDA pad 17, SCL pad 18, VCC 3V3, AD0 to GND (0x68).
*/
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
Adafruit_MPU6050 mpu;
void setup() {
  Serial.begin(115200);
  Wire1.begin(17, 18);
  if (!mpu.begin(0x68, &Wire1) && !mpu.begin(0x69, &Wire1)) {
    Serial.println("MPU-6050 not found. Check 3V3, SDA=17, SCL=18, AD0=GND.");
    while (1) delay(1000);
  }
  Serial.println("MPU-6050 OK on GPIO17/18  tilt the board");
}
void loop() {
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  float roll = atan2f(a.acceleration.y, a.acceleration.z) * 180.0f / PI;
  float pitch = atan2f(-a.acceleration.x,
                       sqrtf(a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z)) *
                180.0f / PI;
  Serial.printf("ax=%.2f ay=%.2f az=%.2f g  pitch=%.1f roll=%.1f\n",
                a.acceleration.x / 9.81f, a.acceleration.y / 9.81f, a.acceleration.z / 9.81f,
                pitch, roll);
  delay(200);
}
