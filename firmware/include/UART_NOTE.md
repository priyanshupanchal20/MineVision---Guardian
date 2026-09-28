# UART note — YD-ESP32-S3

Silkscreen **TX / RX** = GPIO43 / GPIO44 = UART0 = **TFMini-S only**.

| UART | Pins | Device |
|---|---|---|
| UART0 | silk RX=44, silk TX=43 | TFMini-S |
| UART1 | GPIO11 RX, GPIO10 TX | S3KM1110 |
| UART2 | GPIO15 RX, GPIO16 TX | NEO-6M GPS |
| USB CDC | USB-OTG Type-C | Serial Monitor |

The **COM** Type-C is wired to the same TX/RX pads. Do not use COM for debug while the LiDAR is attached.
