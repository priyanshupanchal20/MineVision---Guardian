# LDR (LM393) test

| | |
|---|---|
| Wiring | 3.3V, GND, A0 → GPIO4. D0 unused. |
| Library | none |
| Expected | Covering sensor changes `raw` and `light_level` 0–100 |
| Note | Fusion uses analog A0 only. |
| Mapping | If values invert on your board, swap the map() ends in firmware. |
