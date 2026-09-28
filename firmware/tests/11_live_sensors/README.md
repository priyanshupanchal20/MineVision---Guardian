# Live bench test (no GPS, no mmWave)

Flash this after the OLED smoke test. Serial 115200 on USB-OTG.

Expected: I2C scan shows `0x3C` (OLED) and `0x76` or `0x77` (BME280) on bus 0, `0x68` on bus 1. LiDAR frames when something is in front of the TFMini-S. Ultrasonics need the echo divider.
