/*
  =============================================================================
  MineTruck / MineVision — Arduino Uno R3 Drive Controller
  =============================================================================
  Hardware:
    - HC-05 Bluetooth (phone drive commands)  → SoftwareSerial
    - ESP32-S3 safety status                   → Hardware Serial (pins 0/1)
    - L298N dual H-bridge                     → 4 DC motors (skid steer)

  Safety priority (highest first):
    1) ESP32 DANGER / STOP  (+ UART link timeout after link is established)
    2) Manual STOP from phone (S / 0)
    3) Normal movement / speed commands from phone

  CRITICAL RULES:
    - DANGER/STOP always beats Bluetooth drive commands
    - CLEAR does NOT restart motors; a NEW phone command is required
    - No delay() in the control loop (millis() only)
    - Motors are NEVER powered from the Arduino 5V pin

  Board: Arduino Uno
  IDE:   Arduino IDE 2.x
  =============================================================================
*/

#include <SoftwareSerial.h>
#include <ctype.h>

// =============================================================================
// CONFIGURATION — change these safely
// =============================================================================

// If no valid ESP32 status line arrives for this long AFTER the link is up,
// treat it as communication failure and stop the vehicle.
// Change this if your ESP32 heartbeat is slower/faster (e.g. 1500 or 2000).
const unsigned long ESP32_TIMEOUT_MS = 1000;

// Expected ESP32 status cadence (documentation only; timeout above is what matters)
// ESP32 should send SAFE / DANGER / STOP / CLEAR about every 200–500 ms.

// Set to false ONLY for early bench tests (motors / Bluetooth) without ESP32.
// MUST be true for any floor/demo run that needs safety interlock.
const bool REQUIRE_ESP32 = true;

// Baud rates
const long USB_ESP32_BAUD = 115200;  // Hardware Serial: USB Monitor + ESP32 UART
const long HC05_BAUD      = 9600;    // Typical HC-05 default (MUST VERIFY on your module)

// Speed defaults (PWM 0–255)
const int DEFAULT_SPEED = 150;
const int MAX_SPEED     = 255;

// Phone digits 1–5 → PWM. Edit these numbers to tune your chassis.
const int SPEED_MAP[6] = {
  0,    // 0 = stop (also handled as command)
  80,   // 1 low
  120,  // 2 medium-low
  160,  // 3 medium
  200,  // 4 medium-high
  255   // 5 high
};

// =============================================================================
// PIN ASSIGNMENT (chosen to avoid conflicts — see README)
// =============================================================================
//
// Why this map?
// - D0/D1 = ONLY hardware UART on Uno → ESP32 safety link (most reliable)
// - HC-05 on SoftwareSerial (cannot share a second SoftSerial RX reliably)
// - ENA/ENB on PWM pins D5/D6
// - Direction pins on free digital pins
// - Keeps HC-05 pins close to the older MineVision drive_uno wiring (D4/D7)
//
// | Arduino | Device        | Function                          |
// |---------|---------------|-----------------------------------|
// | D5      | L298N ENA     | Left channel PWM                  |
// | D8      | L298N IN1     | Left direction                    |
// | D9      | L298N IN2     | Left direction                    |
// | D6      | L298N ENB     | Right channel PWM                 |
// | D10     | L298N IN3     | Right direction                   |
// | D11     | L298N IN4     | Right direction                   |
// | D7      | HC-05 TXD     | SoftSerial RX (listen to phone)   |
// | D4      | HC-05 RXD     | SoftSerial TX via LEVEL DIVIDER   |
// | D0 (RX) | ESP32 TX      | Hardware Serial RX (3.3 V OK)     |
// | D1 (TX) | ESP32 RX      | Hardware Serial TX — LEVEL SHIFT! |
// | 5V/VIN  | logic supply | NOT motor power                   |
// | GND     | common ground | Arduino + L298N + modules         |

const int PIN_ENA = 5;
const int PIN_IN1 = 8;
const int PIN_IN2 = 9;
const int PIN_ENB = 6;
const int PIN_IN3 = 10;
const int PIN_IN4 = 11;

const int PIN_BT_RX = 7;  // Arduino listens  ← HC-05 TXD
const int PIN_BT_TX = 4;  // Arduino talks    → HC-05 RXD (through divider)

// Hard estop from ESP32 GPIO5 (PIN_DRIVE_STOP). HIGH = force SAFETY_STOP.
// Works even if UART text is missed. Wire: ESP32 GPIO5 → Uno D3, common GND.
const int PIN_ESTOP = 3;

SoftwareSerial btSerial(PIN_BT_RX, PIN_BT_TX);

// =============================================================================
// STATE MACHINE
// =============================================================================

enum VehicleState {
  WAIT_FOR_ESP32,         // Motors off until first valid SAFE (if required)
  NORMAL_OPERATION,       // Accept drive commands; watch ESP32 + timeout
  SAFETY_STOP,            // DANGER/STOP latched; ignore move cmds until CLEAR
  COMMUNICATION_FAILURE   // Link lost; ignore move cmds until SAFE again
};

VehicleState vehicleState = WAIT_FOR_ESP32;

int currentSpeed = DEFAULT_SPEED;
char lastDriveCommand = 'S';   // remembered only while allowed to move
bool motorsEnabled = false;    // true only when actively commanded to move

unsigned long lastEsp32MessageMs = 0;
bool esp32LinkEstablished = false;

// Line buffer for ESP32 messages (Hardware Serial)
const int ESP_LINE_MAX = 32;
char espLineBuf[ESP_LINE_MAX];
int espLineLen = 0;

// =============================================================================
// FORWARD DECLARATIONS
// =============================================================================

void setLeftMotor(int speed);
void setRightMotor(int speed);
void moveForward(int speed);
void moveBackward(int speed);
void turnLeft(int speed);
void turnRight(int speed);
void stopMotors();
void emergencyStop(const char *reason);
void applyDriveCommand(char cmd);
void handleBluetoothChar(char c);
void handleEsp32Line(const char *line);
void pollBluetooth();
void pollEsp32();
void checkEsp32Timeout();
void pollHardEstop();
int mapSpeedDigit(char digit);

// =============================================================================
// SETUP
// =============================================================================

void setup() {
  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_ENB, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  pinMode(PIN_ESTOP, INPUT);  // ESP32 drives HIGH on DANGER (use INPUT, ESP is push-pull)

  stopMotors();

  // Hardware Serial = USB Serial Monitor AND ESP32 UART on pins 0/1
  Serial.begin(USB_ESP32_BAUD);
  btSerial.begin(HC05_BAUD);

  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F("MineTruck Uno drive controller"));
  Serial.println(F("========================================"));
  Serial.print(F("ESP32 timeout ms: "));
  Serial.println(ESP32_TIMEOUT_MS);
  Serial.print(F("Default speed: "));
  Serial.println(DEFAULT_SPEED);
  Serial.print(F("REQUIRE_ESP32: "));
  Serial.println(REQUIRE_ESP32 ? F("YES") : F("NO (TEST ONLY)"));

  if (REQUIRE_ESP32) {
    vehicleState = WAIT_FOR_ESP32;
    Serial.println(F("State: WAIT_FOR_ESP32"));
    Serial.println(F("Waiting for ESP32 status: SAFE ..."));
    Serial.println(F("Motors locked OFF until ESP32 link + SAFE."));
  } else {
    vehicleState = NORMAL_OPERATION;
    esp32LinkEstablished = false;
    Serial.println(F("State: NORMAL_OPERATION (ESP32 not required)"));
    Serial.println(F("WARNING: safety UART interlock disabled."));
  }
}

// =============================================================================
// MAIN LOOP — non-blocking
// =============================================================================

void loop() {
  // 0) Hard GPIO estop from ESP32 PIN_DRIVE_STOP (GPIO5 → Uno D3)
  pollHardEstop();

  // 1) Always listen to ESP32 UART (SAFE / DANGER / CLEAR)
  pollEsp32();

  // 2) Fail-safe timeout only after the link was established at least once
  if (REQUIRE_ESP32 && esp32LinkEstablished) {
    checkEsp32Timeout();
  }

  // 3) Listen to phone / Bluetooth
  pollBluetooth();

  // 4) Enforce stop in unsafe states (in case a bug tried to enable motors)
  if (vehicleState == WAIT_FOR_ESP32 ||
      vehicleState == SAFETY_STOP ||
      vehicleState == COMMUNICATION_FAILURE) {
    if (motorsEnabled) {
      stopMotors();
      motorsEnabled = false;
    }
  }
}

// =============================================================================
// MOTOR PRIMITIVES
// speed: signed-ish API — pass 0..255 forward magnitude;
// setLeftMotor / setRightMotor use signed: +fwd, -back, 0 stop
// =============================================================================

void setLeftMotor(int speed) {
  speed = constrain(speed, -MAX_SPEED, MAX_SPEED);

  if (speed > 0) {
    digitalWrite(PIN_IN1, HIGH);
    digitalWrite(PIN_IN2, LOW);
    analogWrite(PIN_ENA, speed);
  } else if (speed < 0) {
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, HIGH);
    analogWrite(PIN_ENA, -speed);
  } else {
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, LOW);
    analogWrite(PIN_ENA, 0);
  }
}

void setRightMotor(int speed) {
  speed = constrain(speed, -MAX_SPEED, MAX_SPEED);

  if (speed > 0) {
    digitalWrite(PIN_IN3, HIGH);
    digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_ENB, speed);
  } else if (speed < 0) {
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, HIGH);
    analogWrite(PIN_ENB, -speed);
  } else {
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_ENB, 0);
  }
}

void moveForward(int speed) {
  speed = constrain(speed, 0, MAX_SPEED);
  setLeftMotor(speed);
  setRightMotor(speed);
}

void moveBackward(int speed) {
  speed = constrain(speed, 0, MAX_SPEED);
  setLeftMotor(-speed);
  setRightMotor(-speed);
}

// Skid steer LEFT: left reverse, right forward (simple & reliable)
void turnLeft(int speed) {
  speed = constrain(speed, 0, MAX_SPEED);
  setLeftMotor(-speed);
  setRightMotor(speed);
}

// Skid steer RIGHT: left forward, right reverse
void turnRight(int speed) {
  speed = constrain(speed, 0, MAX_SPEED);
  setLeftMotor(speed);
  setRightMotor(-speed);
}

void stopMotors() {
  setLeftMotor(0);
  setRightMotor(0);
}

// Immediate fail-safe: zero PWM, safe direction pins, latch unsafe state
void emergencyStop(const char *reason) {
  stopMotors();
  motorsEnabled = false;
  lastDriveCommand = 'S';

  Serial.print(F("[SAFETY] Vehicle stopped — "));
  Serial.println(reason);
}

// =============================================================================
// DRIVE COMMAND APPLICATION
// =============================================================================

bool movementAllowed() {
  return (vehicleState == NORMAL_OPERATION);
}

void applyDriveCommand(char cmd) {
  cmd = toupper(cmd);

  if (!movementAllowed()) {
    // Manual STOP is still accepted (harmless) but movement is blocked
    if (cmd == 'S') {
      stopMotors();
      motorsEnabled = false;
      lastDriveCommand = 'S';
      Serial.println(F("[HC05] S (stop while safety active)"));
    } else if (cmd == 'F' || cmd == 'B' || cmd == 'L' || cmd == 'R') {
      Serial.print(F("[HC05] "));
      Serial.print(cmd);
      Serial.println(F(" — IGNORED, SAFETY ACTIVE"));
    }
    return;
  }

  switch (cmd) {
    case 'F':
      moveForward(currentSpeed);
      motorsEnabled = true;
      lastDriveCommand = 'F';
      Serial.println(F("[MOTOR] Forward"));
      break;
    case 'B':
      moveBackward(currentSpeed);
      motorsEnabled = true;
      lastDriveCommand = 'B';
      Serial.println(F("[MOTOR] Backward"));
      break;
    case 'L':
      turnLeft(currentSpeed);
      motorsEnabled = true;
      lastDriveCommand = 'L';
      Serial.println(F("[MOTOR] Left"));
      break;
    case 'R':
      turnRight(currentSpeed);
      motorsEnabled = true;
      lastDriveCommand = 'R';
      Serial.println(F("[MOTOR] Right"));
      break;
    case 'S':
      stopMotors();
      motorsEnabled = false;
      lastDriveCommand = 'S';
      Serial.println(F("[MOTOR] Stop"));
      break;
    default:
      break;
  }
}

int mapSpeedDigit(char digit) {
  if (digit < '0' || digit > '5') {
    return currentSpeed;
  }
  return SPEED_MAP[digit - '0'];
}

void handleBluetoothChar(char c) {
  // Ignore whitespace / CR / LF so they never become "mystery" motion
  if (c == '\r' || c == '\n' || c == ' ' || c == '\t') {
    return;
  }

  c = toupper(c);

  if (c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S') {
    Serial.print(F("[HC05] "));
    Serial.println(c);
    applyDriveCommand(c);
    return;
  }

  if (c >= '0' && c <= '5') {
    if (c == '0') {
      Serial.println(F("[HC05] 0 (speed stop)"));
      applyDriveCommand('S');
      return;
    }

    currentSpeed = mapSpeedDigit(c);
    Serial.print(F("[HC05] Speed digit "));
    Serial.print(c);
    Serial.print(F(" -> PWM "));
    Serial.println(currentSpeed);

    // If already moving and allowed, refresh motion at new speed
    if (movementAllowed() && motorsEnabled && lastDriveCommand != 'S') {
      applyDriveCommand(lastDriveCommand);
    }
    return;
  }

  // Unknown characters: ignore quietly (no flood)
}

void pollBluetooth() {
  while (btSerial.available()) {
    handleBluetoothChar((char)btSerial.read());
  }
}

// =============================================================================
// ESP32 UART PROTOCOL
// Lines: SAFE / DANGER / STOP / CLEAR  (optional \\r before \\n)
// =============================================================================

void enterSafetyStop(const char *why) {
  emergencyStop(why);
  vehicleState = SAFETY_STOP;
  Serial.println(F("!!! SAFETY STOP !!!"));
  Serial.println(F("State: SAFETY_STOP (waiting for CLEAR)"));
}

void enterCommFailure() {
  emergencyStop("ESP32 communication timeout");
  vehicleState = COMMUNICATION_FAILURE;
  Serial.println(F("!!! COMMUNICATION FAILURE !!!"));
  Serial.println(F("State: COMMUNICATION_FAILURE (waiting for SAFE)"));
}

void handleEsp32Line(const char *line) {
  if (line == NULL || line[0] == '\0') {
    return;
  }

  // Any valid protocol word refreshes the heartbeat timestamp
  bool known = false;

  if (strcmp(line, "SAFE") == 0 || strcmp(line, "WARNING") == 0) {
    known = true;
    // SAFE and WARNING both allow Bluetooth drive; only DANGER stops.
    Serial.print(F("[ESP32] "));
    Serial.println(line);

    lastEsp32MessageMs = millis();
    esp32LinkEstablished = true;

    if (vehicleState == WAIT_FOR_ESP32) {
      vehicleState = NORMAL_OPERATION;
      stopMotors();
      motorsEnabled = false;
      lastDriveCommand = 'S';
      Serial.println(F("ESP32 status: drive allowed (SAFE/WARNING)"));
      Serial.println(F("System ready — motors run until DANGER"));
      Serial.println(F("State: NORMAL_OPERATION"));
    } else if (vehicleState == COMMUNICATION_FAILURE) {
      // Recover link, but do NOT resume previous motion
      vehicleState = NORMAL_OPERATION;
      stopMotors();
      motorsEnabled = false;
      lastDriveCommand = 'S';
      Serial.println(F("ESP32 link recovered (SAFE/WARNING)"));
      Serial.println(F("Vehicle remains stopped — send a new drive command"));
      Serial.println(F("State: NORMAL_OPERATION"));
    }
    // Heartbeat while NORMAL; does NOT clear SAFETY_STOP (need CLEAR)
    return;
  }

  if (strcmp(line, "DANGER") == 0) {
    known = true;
    Serial.println(F("[ESP32] DANGER"));
    lastEsp32MessageMs = millis();
    esp32LinkEstablished = true;
    enterSafetyStop("ESP32 DANGER");
    return;
  }

  if (strcmp(line, "STOP") == 0) {
    known = true;
    Serial.println(F("[ESP32] STOP"));
    lastEsp32MessageMs = millis();
    esp32LinkEstablished = true;
    enterSafetyStop("ESP32 STOP");
    return;
  }

  if (strcmp(line, "CLEAR") == 0) {
    known = true;
    Serial.println(F("[ESP32] CLEAR"));
    lastEsp32MessageMs = millis();
    esp32LinkEstablished = true;

    if (vehicleState == SAFETY_STOP) {
      // Danger cleared — stay stopped; require a NEW phone command
      vehicleState = NORMAL_OPERATION;
      stopMotors();
      motorsEnabled = false;
      lastDriveCommand = 'S';
      Serial.println(F("Safety condition cleared"));
      Serial.println(F("Vehicle remains stopped"));
      Serial.println(F("State: NORMAL_OPERATION (awaiting new driver command)"));
    } else {
      Serial.println(F("[ESP32] CLEAR (no active SAFETY_STOP)"));
    }
    return;
  }

  // Unknown lines: ignore (may be USB debug echo noise). Do NOT refresh timeout
  // unless you intentionally treat any line as heartbeat — we do not.
  if (!known) {
    // Optional quiet ignore; uncomment to debug garbage:
    // Serial.print(F("[ESP32] ignored: ")); Serial.println(line);
  }
}

void pollHardEstop() {
  static bool latched = false;
  const bool estop = (digitalRead(PIN_ESTOP) == HIGH);

  if (estop) {
    if (vehicleState != SAFETY_STOP) {
      emergencyStop("GPIO ESTOP from ESP32");
      vehicleState = SAFETY_STOP;
      Serial.println(F("State: SAFETY_STOP (GPIO5/D3)"));
    }
    stopMotors();
    motorsEnabled = false;
    esp32LinkEstablished = true;
    lastEsp32MessageMs = millis();
    latched = true;
    return;
  }

  if (latched) {
    // Pin released acts like CLEAR — stay stopped until a new phone command.
    latched = false;
    vehicleState = NORMAL_OPERATION;
    stopMotors();
    motorsEnabled = false;
    lastDriveCommand = 'S';
    Serial.println(F("[ESP32] GPIO CLEAR — send F/B/L/R to move again"));
  }
}

void pollEsp32() {
  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      espLineBuf[espLineLen] = '\0';
      if (espLineLen > 0) {
        handleEsp32Line(espLineBuf);
      }
      espLineLen = 0;
      continue;
    }

    if (espLineLen < ESP_LINE_MAX - 1) {
      // Store uppercase for case-insensitive match
      espLineBuf[espLineLen++] = (char)toupper((unsigned char)c);
    } else {
      // Overflow — reset buffer
      espLineLen = 0;
    }
  }
}

void checkEsp32Timeout() {
  if (vehicleState == WAIT_FOR_ESP32) {
    // Startup: do NOT trip timeout before first valid message
    return;
  }

  if (vehicleState == COMMUNICATION_FAILURE) {
    return;
  }

  unsigned long now = millis();
  if ((now - lastEsp32MessageMs) >= ESP32_TIMEOUT_MS) {
    enterCommFailure();
  }
}

/*
  =============================================================================
  TEST MODE NOTES (bench — wheels off the floor / motors disconnected first)
  =============================================================================
  TEST 1: Power Arduino only, motors disconnected. Open Serial Monitor 115200.
  TEST 2: Pair phone → HC-05; send F/B/L/R/S (REQUIRE_ESP32=false for early BT).
  TEST 3: One motor on OUT1/OUT2; confirm direction.
  TEST 4: Both L298N channels.
  TEST 5: All four motors (left pair + right pair).
  TEST 6: ESP32 sends DANGER → all motors stop immediately.
  TEST 7: Phone sends F while DANGER → ignored.
  TEST 8: ESP32 sends CLEAR → remains stopped.
  TEST 9: Phone sends F after CLEAR → moves forward.
  TEST 10: Unplug ESP32 TX while moving → stop after ESP32_TIMEOUT_MS.

  Tip: With REQUIRE_ESP32=true you can also type SAFE/DANGER/STOP/CLEAR
  into the Serial Monitor (same UART) to simulate the ESP32 during bring-up.
  =============================================================================
*/
