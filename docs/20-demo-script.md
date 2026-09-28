# Demo script for judges (≈ 7 minutes)

**Setup before they arrive:** dashboard open on a projector at http://\<pi-or-pc\>:8000, DUMPER_01 in sim or live, RC dumper on a 3 m table “haul road”, cardboard box under the table, mug of warm water, dark cloth, USB humidifier if allowed.

---

**0:00 — Problem (45 s)**  
“NMDC Bailadila dumpers lose 3–5 m of visibility in monsoon fog. Collisions, halted fleets, control-room blindness. We built **MineVision Guardian**: an operator-assistance system, not an autonomous truck.”

**0:45 — Architecture (60 s)**  
Point at the Architecture tab. “Seven layers. ESP32-S3 does hard real-time ranging and the buzzer even if Wi-Fi dies. Pi 3 fuses LiDAR, ultrasonics, 24 GHz radar, thermal, weather, and camera confidence into a 0–100 Mine Safety Risk Score.”

**1:45 — Scenario 1 Normal (40 s)**  
Click **Scenario 1**. Green SAFE, low fog, NORMAL SPEED. “This is a clear-shift haul.”

**2:25 — Scenario 2 Fog (70 s)**  
Click **Scenario 2** and/or drape cloth + humidifier. Show Fog Index climb, **FOG SAFETY MODE**, weights shift to LiDAR/radar/thermal, RGB confidence drops, speed advice REDUCE. “We do not pretend the webcam sees through fog.”

**3:35 — Scenario 3 Obstacle (60 s)**  
Place box in front of TFMini-S or click **Scenario 3**. Read metres on the HUD. WARNING → REDUCE/CRAWL. Alert list: obstacle ahead of DUMPER_01.

**4:35 — Scenario 4 Presence (50 s)**  
Warm mug or person; **Scenario 4**. Thermal cluster + mmWave → **HIGH CONFIDENCE PRESENCE**. “32×24 cannot identify a person. Two physics channels agreeing is the claim.”

**5:25 — Scenario 5 Critical (50 s)**  
Object at ~1.2 m. Cab buzzer continuous, STOP VEHICLE, red card. At ~2.5 m the HUD can show DANGER with **no beep**.

**6:15 — V2V + limits (45 s)**  
Show DUMPER_02 on the map. “ESP-NOW prototype; production is private 5G / V2X. GPS here is NEO-6M — map only, not centimetre docking. 12 m LiDAR is not enough for a real dumper at 30 km/h — industrial LiDAR is the upgrade.”

**7:00 — Close**  
“Practical, honest, scalable. Operator stays in the loop. Questions on fusion weights or pin map are in the docs pack.”

---

## Backup if hardware fails

Keep simulation Scenario buttons. Say: “Same decision engine the ESP32/Pi run; sensors are injected.” Never fake a LiDAR number as if the sensor saw it without labelling **SIM**. The HUD shows a `SIMULATION` badge in sim mode.
