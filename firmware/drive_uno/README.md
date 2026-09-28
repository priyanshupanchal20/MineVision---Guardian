# Arduino Uno Drive Box — Safety-Controlled 4WD (HC-05 + L298N + ESP32-S3 UART)

Complete drive firmware for the college / SIH MineTruck prototype.

Open `drive_uno.ino` in **Arduino IDE 2.x**, board **Arduino Uno**, upload.

---

## A. Assumptions checklist (read before wiring)

| Topic | Assumption / action |
|---|---|
| Motor battery voltage | **MUST VERIFY** — must match motor rating and L298N motor-supply limits (typical hobby: 7–12 V). Do not invent a value. |
| Motor current | **MUST VERIFY** — L298N continuous current is limited (~1–2 A/channel class; real parts vary). If motors stall/hot, use a stronger driver. |
| HC-05 baud | Assumed **9600** (common default). **MUST VERIFY** (AT+UART) if pairing works but commands fail. |
| ESP32-S3 board | Exact GPIO numbers for a spare UART **depend on your board**. Your MineVision YD-ESP32-S3 already uses many UARTs for LiDAR/GPS/radar — pick a **free** UART pair. **MUST VERIFY** pinout for *your* module. |
| ESP32 5 V tolerance | **Do not assume** ESP32-S3 GPIO is 5 V tolerant. Treat RX as **3.3 V only**. |
| Arduino TX → ESP32 RX | **Requires level shifting** (divider or shifter). |
| ESP32 TX → Arduino RX | 3.3 V into Uno RX is normally OK (logic HIGH). |
| Arduino TX → HC-05 RX | **Requires** voltage divider / level shift (HC-05 RX is 3.3 V). |
| HC-05 TX → Arduino RX | Usually OK (HC-05 TX is typically ~3.3 V). |

---

## B. Why this serial arrangement?

Arduino Uno has **one** hardware UART (pins **D0/D1**, shared with USB).

| Link | Bus | Reason |
|---|---|---|
| ESP32-S3 ↔ Uno | **Hardware Serial** (D0/D1) | Safety messages must be reliable |
| Phone ↔ HC-05 ↔ Uno | **SoftwareSerial** (D7 RX, D4 TX) | Drive commands; SoftSerial is OK here |
| USB Serial Monitor | Same as Hardware Serial | Debug prints share the ESP32 wires |

**SoftwareSerial limitation:** only **one** SoftSerial port can receive reliably. Therefore both ESP32 and HC-05 cannot use SoftSerial at once.

**Upload tip:** disconnect ESP32 from **D0** while uploading sketches (USB uses D0/D1).

**Debug tip:** Serial Monitor at **115200**. You can type `SAFE`, `DANGER`, `STOP`, `CLEAR` + Enter to simulate ESP32. ESP32 firmware should **ignore** Uno debug lines that are not protocol words.

---

## C. Pin table (final)

| Arduino Pin | Connected Device | Function |
|---|---|---|
| D5 | L298N ENA | Left PWM |
| D8 | L298N IN1 | Left direction |
| D9 | L298N IN2 | Left direction |
| D6 | L298N ENB | Right PWM |
| D10 | L298N IN3 | Right direction |
| D11 | L298N IN4 | Right direction |
| D7 | HC-05 TXD | SoftSerial RX (Arduino listens) |
| D4 | HC-05 RXD | SoftSerial TX **via divider** |
| D0 (RX) | ESP32 GPIO38 TX | Hardware Serial RX (3.3 V OK) |
| D1 (TX) | ESP32 GPIO39 RX | optional TX via level shift |
| D3 | ESP32 GPIO5 | Hard estop (HIGH = DANGER stop) |
| GND | All modules + L298N GND | **Common ground** |
| VIN / USB / barrel | Logic supply for Uno | **Not** motor power |

**Conflict check**

- PWM used: D5, D6 — OK.
- SoftSerial RX/TX: D7, D4 — free of L298N.
- D0/D1 reserved for ESP32 + USB — OK if you accept shared debug.
- D3 hard estop + UART `DANGER` both stop motors (UART also heartbeats `SAFE`).

---

## D. Wiring diagram (text)

### 1) Power — keep MOTOR and LOGIC separate

```
MOTOR BATTERY +  ----->  L298N +12V / VMS (motor supply terminal)
MOTOR BATTERY -  ----->  L298N GND

Regulated logic supply / USB / VIN ----->  Arduino Uno power
Arduino Uno GND  ----------------------+
                                       +--->  COMMON GROUND
L298N GND  ---------------------------+
HC-05 GND  ---------------------------+
ESP32 GND  ---------------------------+
```

**Never** power the four DC motors from Arduino **5V**.

Arduino needs a proper regulated source (USB for bench, or VIN with suitable adapter — **MUST VERIFY** voltage for your Uno board).

ESP32-S3: power with the voltage your **specific development board** expects (often 5 V on USB / 5V pin, onboard regulator to 3.3 V). **MUST VERIFY** silkscreen; do not feed 5 V into a 3.3 V-only pin.

### 2) L298N ↔ motors (skid steer)

```
L298N OUT1 / OUT2  --->  LEFT motors (Motor1 + Motor2 in parallel or both on same channel)
L298N OUT3 / OUT4  --->  RIGHT motors (Motor3 + Motor4)

Channel A = LEFT
Channel B = RIGHT
```

If a motor runs backward, swap that motor’s two leads (or swap IN1/IN2 logic in code).

### 3) Arduino ↔ L298N signal

```
Uno D5  --->  ENA
Uno D8  --->  IN1
Uno D9  --->  IN2
Uno D6  --->  ENB
Uno D10 --->  IN3
Uno D11 --->  IN4
Uno GND --->  L298N GND
```

**ENA/ENB jumpers:** remove the metal jumpers on ENA and ENB so Arduino PWM can control speed. If jumpers stay installed, channels stay fully enabled and `analogWrite` on ENA/ENB will not throttle as intended.

If your board has a 5V regulator jumper from motor supply: only enable it if motor battery voltage is within the onboard regulator’s allowed range — **MUST VERIFY**. Many setups power logic separately and leave that jumper off.

### 4) HC-05 ↔ Arduino

```
HC-05 TXD  --->  Arduino D7     (direct; 3.3 V TX into Uno is OK)
HC-05 RXD  <---  Arduino D4     **** THROUGH LEVEL DIVIDER ****
HC-05 GND  --->  Arduino GND
HC-05 VCC  --->  5 V (typical HC-05 modules) — MUST VERIFY your module label
```

**Safe 5 V → 3.3 V for HC-05 RX (voltage divider example):**

```
Arduino D4 ----[ 1 kΩ ]----+---- HC-05 RXD
                           |
                         [ 2 kΩ ]
                           |
                          GND
```

(1k series from Uno TX, 2k to GND, tap = ~3.3 V). Other divider ratios / a bidirectional level shifter also work. **MUST VERIFY** resistor values if you change them.

### 5) ESP32-S3 ↔ Arduino (hub firmware 1.5.11+)

```
ESP32 GPIO38 (TX)  --->  Arduino D0 (RX)     [3.3 V OK, no divider]
ESP32 GPIO5        --->  Arduino D3          [HIGH = hard stop]
ESP32 GND          --->  Arduino GND

Optional (not required for stop):
Arduino D1 (TX) ---1k/2k divider---> ESP32 GPIO39 (RX)
```

Hub sends `SAFE` / `DANGER` / `CLEAR` ~4×/sec on GPIO38. GPIO5 is a backup hard estop.

**Which line needs shifting?**

| Direction | Shift? |
|---|---|
| ESP32 TX GPIO38 → Uno RX (D0) | **No** |
| Uno TX (D1) → ESP32 RX GPIO39 | **Yes** if you wire it |
| ESP32 GPIO5 → Uno D3 | **No** (3.3 V HIGH is enough) |

### 6) Baud

- USB / ESP32 link: **115200**
- HC-05: **9600** (default assumption)

---

## E. Communication protocol

### Phone → HC-05 → Arduino

| Char | Meaning |
|---|---|
| `F` | Forward |
| `B` | Backward |
| `L` | Left (skid) |
| `R` | Right (skid) |
| `S` | Stop |
| `0` | Stop |
| `1`…`5` | Speed presets (80…255 PWM) |

Unknown characters and whitespace are ignored.

### ESP32-S3 → Arduino (newline-terminated)

| Message | Meaning |
|---|---|
| `SAFE` | Normal operation allowed (also heartbeat) |
| `DANGER` | Immediate stop; latch SAFETY_STOP |
| `STOP` | Immediate emergency stop; latch SAFETY_STOP |
| `CLEAR` | Danger gone; **do not** auto-resume motion |
| other | Ignored (does not refresh timeout) |

ESP32 should send a status line every **~200–500 ms**.

### Timeout

```cpp
const unsigned long ESP32_TIMEOUT_MS = 1000;
```

After the link is established, if no **valid** status word arrives for 1000 ms → stop + `COMMUNICATION_FAILURE`.

To change: edit that constant at the top of `drive_uno.ino` (e.g. `1500` or `2000` if your ESP32 sends slower).

Startup does **not** timeout before the first valid message; motors stay off in `WAIT_FOR_ESP32`.

---

## F. Safety state diagram

```
              power-up
                 |
                 v
         WAIT_FOR_ESP32
         (motors OFF)
                 |
            SAFE received
                 |
                 v
         NORMAL_OPERATION <------------------------------+
         (accept F/B/L/R/S)                              |
                 |                                       |
        DANGER or STOP                                   |
                 |                                       |
                 v                                       |
           SAFETY_STOP                                   |
           (motors OFF, ignore F/B/L/R)                  |
                 |                                       |
              CLEAR                                      |
                 |                                       |
                 v                                       |
      WAIT FOR NEW DRIVER COMMAND -----------------------+
      (still stopped; next F/B/L/R resumes)
      
      
      NORMAL_OPERATION
                 |
         UART silence > ESP32_TIMEOUT_MS
                 |
                 v
      COMMUNICATION_FAILURE
           (motors OFF)
                 |
            SAFE again
                 |
                 v
      NORMAL_OPERATION (still stopped until new command)
```

**Priorities**

1. ESP32 DANGER / STOP / link failure  
2. Manual `S` / `0`  
3. Movement commands  

Bluetooth **cannot** override an active safety latch.

---

## G. Changing the ESP32 timeout

In `drive_uno.ino`:

```cpp
const unsigned long ESP32_TIMEOUT_MS = 1000;
```

- Raise it if ESP32 status is slow and you get false “communication failure”.
- Lower it for stricter fail-safe (stops sooner if the cable fails).

---

## H. Recommended test sequence

| Test | Action | Expected |
|---|---|---|
| 1 | Uno powered, motors disconnected | Serial: boot + Waiting for ESP32 |
| 2 | HC-05 commands (optional `REQUIRE_ESP32 = false`) | F/B/L/R/S logged |
| 3 | One motor on OUT1/OUT2 | Spins correctly |
| 4 | Both channels | Left + right OK |
| 5 | All four motors | Skid steer works |
| 6 | ESP32 `DANGER` | Immediate stop |
| 7 | Phone `F` during DANGER | Ignored |
| 8 | `CLEAR` | Remains stopped |
| 9 | `F` after CLEAR | Moves forward |
| 10 | Unplug ESP32 while moving | Stops after ~1 s |

For early motor tests only:

```cpp
const bool REQUIRE_ESP32 = false;  // TEST ONLY — re-enable for demos
```

---

## I. Minimal ESP32 status sender (for bring-up)

Use a **free** UART on your ESP32-S3 (**MUST VERIFY** pins). Example pattern only:

```cpp
// CONCEPT — adapt pins to YOUR board. Do not copy GPIO blindly.
HardwareSerial& SafetySerial = Serial1;  // or Serial2, etc.

void setup() {
  SafetySerial.begin(115200, SERIAL_8N1, /*rx*/RX_GPIO, /*tx*/TX_GPIO);
}

void loop() {
  // Call every 200–500 ms from your safety logic:
  // SafetySerial.println("SAFE");
  // SafetySerial.println("DANGER");
  // SafetySerial.println("STOP");
  // SafetySerial.println("CLEAR");
  delay(300);  // OK on ESP32 test sketch; Uno drive loop stays non-blocking
}
```

Your main MineVision firmware currently drives **GPIO5 HIGH = stop** into Uno D3. This UART sketch is the richer SIH protocol. Integrate by printing `SAFE`/`DANGER`/`STOP`/`CLEAR` on a spare UART instead of (or in addition to) the GPIO line — **MUST VERIFY** free pins on the YD-ESP32-S3.

---

## J. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Motors not moving | No common GND; ENA/ENB jumpers still on (or PWM wires loose); still in WAIT_FOR_ESP32; battery disconnected; `REQUIRE_ESP32` waiting for SAFE |
| One side dead | Check that channel’s IN/EN wires; motor connectors; L298N channel damage |
| Motor reverse | Swap that motor’s leads |
| HC-05 not pairing | 3.3/5 V power; default PIN often 1234; module powered? |
| BT paired but no motion | SoftSerial pins swapped (TX↔RX); baud not 9600; still safety-locked; send uppercase F |
| ESP32 messages missing | TX↔RX crossed wrong; baud 115200; wrong GPIO; USB upload conflict on D0; divider wrong on ESP32 RX |
| Arduino resetting | Motor noise — add bulk caps near L298N, separate supplies, solid common GND; avoid brownout from shared weak USB |
| L298N hot | Stall current too high; wrong supply; prolonged stall — **MUST VERIFY** current |
| Serial Monitor garbled / fights ESP32 | Expected on shared UART — disconnect ESP32 to upload; ESP32 must ignore debug text |
| Moves when it should stop | Safety not latched / wrong firmware / ESP32 not sending DANGER; verify Serial log |
| No recovery after CLEAR | By design stays stopped until new `F`/`B`/`L`/`R` |

---

## K. Critical safety requirements (implemented)

1. DANGER > Bluetooth  
2. STOP > Bluetooth  
3. Comm loss → stop  
4. CLEAR does not auto-start  
5. New driver command required after CLEAR  
6. Motors not powered from Arduino 5V (wiring rule)  
7. No 5 V into ESP32 RX without shifting  
8. HC-05 RX protected with divider  
9. Common GND documented  
10. No `delay()` in Uno control loop  
11. Software latch blocks HC-05 override  
12. Beginner-friendly comments in `.ino`
