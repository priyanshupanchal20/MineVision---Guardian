# S3KM1110 mmWave test

| | |
|---|---|
| Wiring | **3.3 V only**, GND, radar TX → GPIO11, radar RX → GPIO10, OUT → GPIO12 optional |
| Baud | 115200 |
| Protocol | Report header `F4 F3 F2 F1`, occupied byte, distance, energy gates, tail `08 07 06 05` |
| Expected | `occupied=1` when a person walks in (~0.2–8.5 m class) |
| Fail | 5 V on a 3.3 V module, TX/RX not crossed, metal plate in near field |
| Honest claim | Presence / micro-motion — not skeleton tracking |
