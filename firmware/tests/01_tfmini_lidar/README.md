# TFMini-S test — YD-ESP32-S3 silkscreen TX / RX

Those two pads are **reserved for the LiDAR**. GPS must not use them.

| | |
|---|---|
| Board | YD-ESP32-S3 V1120 2022-V1.3 · silk **TX = GPIO43**, **RX = GPIO44** |
| Wiring | 5V, GND, green TX → board **RX**, white RX → board **TX** |
| ESP32 | UART0 115200 8N1 |
| USB | Logs on **USB-OTG**. COM shares TX/RX with the LiDAR — leave COM unplugged while ranging |
| Expected | `dist_m=x.xx strength=nnn` |
| Fail: TX/RX swapped | Swap green/white |
| Fail: garbage + COM plugged | Unplug COM Type-C |
