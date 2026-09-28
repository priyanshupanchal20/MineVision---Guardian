/*
  Minimal ESP32-S3 → Arduino Uno safety UART test sender
  ------------------------------------------------------
  Purpose: bench-test drive_uno.ino without full MineVision firmware.

  IMPORTANT:
  - Set SAFETY_TX_PIN / SAFETY_RX_PIN to a FREE UART pair on YOUR board.
  - On YD-ESP32-S3 used by MineVision, silkscreen TX/RX are often already
    taken by LiDAR — do NOT blindly reuse them.
  - Arduino D1 (5 V) → ESP32 RX requires a level shifter / divider.
  - ESP32 TX (3.3 V) → Arduino D0 is usually OK.
  - Common GND with the Uno is required.

  Board: ESP32-S3 (any DevKit — MUST VERIFY pins)
  Baud:  115200  (must match drive_uno.ino)
*/

// ====== MUST VERIFY for your ESP32-S3 board ======
static const int SAFETY_RX_PIN = -1;  // ESP32 RX  ← from Uno D1 (via divider)
static const int SAFETY_TX_PIN = -1;  // ESP32 TX  → to Uno D0
// Example placeholders only (DO NOT assume these are free on your PCB):
// static const int SAFETY_RX_PIN = 18;
// static const int SAFETY_TX_PIN = 17;

static const unsigned long HEARTBEAT_MS = 300;

enum Mode {
  MODE_SAFE_HEARTBEAT,
  MODE_DANGER,
  MODE_STOP,
  MODE_CLEAR_THEN_SAFE
};

// Change this to exercise TESTS 6–9 quickly
Mode mode = MODE_SAFE_HEARTBEAT;

unsigned long lastSendMs = 0;
unsigned long modeStartMs = 0;

void sendLine(const char *msg) {
  Serial1.println(msg);
  Serial.print("[TO UNO] ");
  Serial.println(msg);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  if (SAFETY_RX_PIN < 0 || SAFETY_TX_PIN < 0) {
    Serial.println("Set SAFETY_RX_PIN and SAFETY_TX_PIN before use.");
    while (true) {
      delay(1000);
    }
  }

  Serial1.begin(115200, SERIAL_8N1, SAFETY_RX_PIN, SAFETY_TX_PIN);
  modeStartMs = millis();
  Serial.println("ESP32 safety UART tester ready");
}

void loop() {
  unsigned long now = millis();
  if (now - lastSendMs < HEARTBEAT_MS) {
    return;
  }
  lastSendMs = now;

  switch (mode) {
    case MODE_SAFE_HEARTBEAT:
      sendLine("SAFE");
      break;

    case MODE_DANGER:
      sendLine("DANGER");
      break;

    case MODE_STOP:
      sendLine("STOP");
      break;

    case MODE_CLEAR_THEN_SAFE:
      // First second: CLEAR once-ish, then SAFE heartbeats
      if (now - modeStartMs < 1000) {
        sendLine("CLEAR");
      } else {
        sendLine("SAFE");
      }
      break;
  }
}
