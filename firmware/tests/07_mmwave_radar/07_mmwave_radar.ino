/*
  Waveshare S3KM1110 / HMMD — 3.3V, TX->GPIO11, RX->GPIO10, 115200
  Optional OUT -> GPIO12
*/
HardwareSerial Radar(1);
void setup() {
  Serial.begin(115200);
  pinMode(12, INPUT_PULLDOWN);
  Radar.begin(115200, SERIAL_8N1, 11, 10);
  Serial.println("mmWave test — walk into FOV");
}
void loop() {
  static uint8_t buf[64];
  static int n = 0;
  while (Radar.available()) {
    uint8_t c = Radar.read();
    if (n == 0 && c != 0xF4) continue;
    buf[n++] = c;
    if (n == 4 && !(buf[0]==0xF4 && buf[1]==0xF3 && buf[2]==0xF2 && buf[3]==0xF1)) { n = 0; continue; }
    if (n >= 6) {
      uint16_t len = buf[4] | (buf[5] << 8);
      int total = 6 + len + 4;
      if (total > 64) { n = 0; continue; }
      if (n < total) continue;
      bool occ = buf[6] == 1;
      uint16_t dist = buf[7] | (buf[8] << 8);
      Serial.printf("occupied=%d dist_cm=%u OUT=%d\n", occ, dist, digitalRead(12));
      n = 0;
    }
  }
}
