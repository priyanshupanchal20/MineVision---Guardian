# Limitations of this prototype

These are intentional, documented constraints — not bugs to hide from judges.

1. **NEO-6M GPS is metre-class at best**, worse under pit walls. It cannot separate two dumpers in fog. Not for automatic collision closure.
2. **HC-SR04** fails on soft/angled targets, wind, rain, and mud. Crosstalk if both fire together.
3. **MLX90640** is 32×24. It cannot identify humans or read PPE. Hot rock ≠ person.
4. **TFMini-S 12 m** is far below HEMM braking distance at operational speed.
5. **Wi-Fi / ESP-NOW** is not a mine-wide, QoS-guaranteed V2X fabric. Multipath in steel + rock is hostile.
6. **Raspberry Pi 3 / 1 GB** cannot run modern detection transformers or full YOLO in real time.
7. **OV7670** on Pi 3 is a software-sampled DVP (160×120, a few Hz). Contrast/edges are enough for the fog metric; it is not a sharp dashboard camera.
8. **No vehicle actuation.** Speed advice is a string. We do not command real dump-truck brakes.
9. **No intrinsic safety / explosion-proof / IP67** housing. Open wiring is a lab/demo setup.
10. **BME280 humidity ≠ visibility.** Fog index is a proxy, not a transmissometer.
11. **mmWave** detects presence/micro-motion in a short cone (~8.5 m class). It is not a 360° pedestrian airbag radar.
12. **Single-point Pi dashboard** is not redundant. Radio loss blanks the control room (cab buzzer still works).
13. **Simulation mode** is labelled. It is for software and judge backup, not a substitute for Phase 2 sensor sign-off.
14. **Legal / statutory** mine traffic rules, DGMS guidelines, and OEM manuals override this prototype in every real pit.

See `docs/23-industrial-upgrade-path.md` for the component-for-component replacement list.
