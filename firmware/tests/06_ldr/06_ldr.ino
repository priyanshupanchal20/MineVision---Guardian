/*
  LM393 LDR module — A0 GPIO4 (ADC). D0 unused.
*/
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  Serial.println("LDR test cover/uncover the LDR (A0 on GPIO4)");
}
void loop() {
  int raw = analogRead(4);
  int pct = constrain(map(raw, 0, 4095, 100, 0), 0, 100);
  Serial.printf("raw=%d light_level=%d\n", raw, pct);
  delay(200);
}
