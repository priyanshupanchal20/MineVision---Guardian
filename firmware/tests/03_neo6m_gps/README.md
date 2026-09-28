# NEO-6M GPS test

**Not** the silkscreen TX/RX (those are the LiDAR). Use numbered **15** and **16**.

| | |
|---|---|
| Wiring | GND common. GPS **TX → GPIO15**. GPS **RX → GPIO16**. |
| VCC | 3.3 V unless the breakout silkscreen / LDO clearly allows 5 V |
| Library | TinyGPSPlus |
| Expected | `chars` climbing immediately; `valid=1` outdoors after cold start (up to 15 min) |
| Indoor | `valid=0` is **normal** |
| Limitation | Not centimetre RTK — map tracking only |
| No `chars` | TX/RX not crossed, or clone baud 38400 |
