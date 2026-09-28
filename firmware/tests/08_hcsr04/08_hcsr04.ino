/*
  HC-SR04 ×2 on YD-ESP32-S3. ECHO MUST go through a 5V→3.3V divider.
  Left:  TRIG pad 13, ECHO pad 7
  Right: TRIG pad 21, ECHO pad 47
  GPIO14 is not broken out on this board.
*/
#define LT 13
#define LE 7
#define RT 21
#define RE 47
float ping(int trig, int echo) {
  digitalWrite(trig, LOW); delayMicroseconds(2);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 25000);
  if (!us) return NAN;
  return us * 0.0343f / 2.0f;
}
void setup() {
  Serial.begin(115200);
  pinMode(LT, OUTPUT); pinMode(RT, OUTPUT);
  pinMode(LE, INPUT); pinMode(RE, INPUT);
  Serial.println("HC-SR04  L:13/7  R:21/47  echo via divider");
}
void loop() {
  float L = ping(LT, LE);
  delay(70);
  float R = ping(RT, RE);
  Serial.printf("left_m=%.2f right_m=%.2f\n", L, R);
  delay(70);
}
