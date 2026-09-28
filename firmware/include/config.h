#pragma once
#include <stdint.h>

#if __has_include("secrets.h")
#include "secrets.h"
#else
#define WIFI_SSID     "Home"
#define WIFI_PASSWORD "Home"
#define GATEWAY_HOST  "minevision.local"
#define GATEWAY_PORT  8000
#define VEHICLE_ID    "DUMPER_01"
#endif

// MineVision Guardian — ESP32-S3-WROOM-N16R8 pin map
// Dual USB-C DevKitC-1 class. Do NOT use GPIO 19/20 (USB), 35/36/37 (octal PSRAM).

#define VEHICLE_ID_DEFAULT "DUMPER_01"

// UART0 TFMini-S 115200 — YD-ESP32-S3 silkscreen TX/RX (GPIO43/44)
// Do not reuse these pads for GPS. Serial Monitor = USB-OTG CDC, not COM.
#define PIN_LIDAR_RX 44
#define PIN_LIDAR_TX 43

// UART2 NEO-6M 9600 — numbered pins 15/16, NOT the TX/RX labels
#define PIN_GPS_RX 15
#define PIN_GPS_TX 16

// I2C0 BME280 (0x76/0x77) + 1.3" OLED (0x3C) on pads 8 / 9
#define PIN_I2C_SDA 8
#define PIN_I2C_SCL 9
#define OLED_I2C_ADDR 0x3C
#define OLED_IS_SH1106 1

// I2C1 MPU — raw WHO_AM_I (clones may be 0x70)
#define PIN_MPU_SDA 17
#define PIN_MPU_SCL 18

#define PIN_LDR_AO 4

// Ultrasonics stay LEFT / RIGHT (not remapped)
#define PIN_US_L_TRIG 13
#define PIN_US_L_ECHO 7
#define PIN_US_R_TRIG 21
#define PIN_US_R_ECHO 47

#define PIN_LED_GREEN 1
#define PIN_LED_YELLOW 2
#define PIN_LED_RED 42
#define PIN_LED_FOG 41
#define PIN_BUZZER 6

// HLK-LD2420 24 GHz — human presence (moving OR standing / micro-motion)
// Newer FW (typ. V2.1): OT2 = presence OUT, OT1 = UART TX
// Older FW:            OT1 = presence OUT, OT2 = UART TX
// We debounce the stable presence pin and ignore UART chatter on the other.
#define PIN_RADAR_OT1 12
#define PIN_RADAR_OT2 14
#define RADAR_ASSERT_MS 280   // must stay HIGH this long → human present
#define RADAR_CLEAR_MS  700   // must stay LOW this long → clear (standing hold)
// Cab/dashboard human alert only if ranging also sees someone within this distance.
#define RADAR_ALERT_MAX_M 0.30f
#define RADAR_CLEAR_HYST_M 0.05f  // clear only once the target is beyond MAX + HYST
#define RADAR_NEAR_HITS 2         // consecutive in-range reports to assert
#define RADAR_FAR_HITS  3         // consecutive out-of-range reports to clear
#define RADAR_STALE_MS  500       // no radar text this long → drop the range

// Drive interlock to Arduino Uno (L298N + HC-05 drive box)
// GPIO HIGH = hard estop (wire to Uno D3). UART = SAFE/DANGER/CLEAR heartbeat.
#define PIN_DRIVE_STOP 5
#define PIN_DRIVE_UART_RX 39  // optional Uno D1 → ESP (use 1k/2k divider); can leave unconnected
#define PIN_DRIVE_UART_TX 38  // ESP TX → Uno D0 (3.3 V OK)
#define DRIVE_UART_HZ 4

#define ZONE_SAFE_M 8.0f
#define ZONE_WARN_M 4.0f
#define ZONE_BUZZ_LIDAR_M 1.5f
#define ZONE_BUZZ_US_M 1.0f

#define TELEMETRY_HZ 10
// Net task only — never block the OLED / safety path with multi-second waits.
#define HTTP_CONNECT_MS 600
#define HTTP_TIMEOUT_MS 900
#define US_TIMEOUT_US 22000
#define US_MIN_US 300
#define US_MIN_M 0.06f
#define US_MAX_M 4.50f
// Crosstalk gap between left and right transducers (HC-SR04 needs settle time).
#define US_PING_GAP_MS 38
#define US_SIDE_GAP_MS 4
#define US_CONFIRM 2
#define OLED_REFRESH_MS 30
#define OLED_DELTA_M 0.015f

struct UsEcho {
  int trig;
  int echo;
  volatile uint32_t t0;
  volatile uint32_t us;
  volatile uint8_t st;
  uint8_t miss;
  float last;
  uint32_t last_ms;
  bool had_echo;
  uint32_t last_us;
  uint8_t confirm;
  float lock;
  uint8_t ghost;
};

#define FIRMWARE_VERSION "1.5.19"
