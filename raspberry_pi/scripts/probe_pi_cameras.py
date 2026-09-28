#!/usr/bin/env python3
"""Check MLX9064X on I2C1 and OV7670 SCCB on the Pi 3 pin map."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from minevision import config


def main() -> None:
    print("MLX9064X  VIN pin", config.PI_MLX_VIN_PHYS, "(3V3 by SD card)")
    print("          GND pin", config.PI_MLX_GND_PHYS)
    print("          SDA pin", config.PI_MLX_SDA_PHYS, "BCM GPIO" + str(config.PI_MLX_SDA_BCM))
    print("          SCL pin", config.PI_MLX_SCL_PHYS, "BCM GPIO" + str(config.PI_MLX_SCL_BCM))
    print("          i2cdetect -y 1  → expect 0x33")
    try:
        from minevision.thermal.mlx import MlxCamera

        mlx = MlxCamera()
        print("MLX driver:", mlx.kind)
        frame = mlx.read()
        if frame is not None:
            print(f"MLX frame min={frame.min():.1f} max={frame.max():.1f} °C")
        else:
            print("MLX no frame — enable I2C, 3.3 V only, pip install adafruit-circuitpython-mlx90640")
    except Exception as exc:
        print("MLX error:", exc)

    print()
    print("OV7670    VCC pin 17  GND pin 9")
    print("          SIOD pin 19 / GPIO10   SIOC pin 23 / GPIO11")
    print("          XCLK pin 7 / GPIO4     (needs pigpiod for 8 MHz)")
    print("          PWDN pin 16 must be LOW, RESET pin 18 HIGH")
    from pathlib import Path as P

    spidev = list(P("/dev").glob("spidev*"))
    if spidev:
        print("WARNING: SPI is on (", [p.name for p in spidev], ") — GPIO10/11 busy. raspi-config → SPI No, then reboot.")
    try:
        import subprocess

        r = subprocess.run(["pigs", "t"], capture_output=True, text=True, timeout=2)
        print("pigpiod:", "OK" if r.returncode == 0 else "NOT RUNNING — sudo pigpiod")
    except Exception:
        print("pigpiod: pigs not found")
    try:
        from minevision.vision.ov7670 import Ov7670Camera

        ov = Ov7670Camera()
        print("OV7670:", ov.note)
        frame = ov.wait_frame(12.0)
        if frame is not None:
            print(
                f"OV7670 frame {frame.shape[1]}x{frame.shape[0]} "
                f"min={frame.min():.2f} max={frame.max():.2f} mean={frame.mean():.2f}"
            )
        else:
            print("OV7670 no DVP frame yet —", ov.note)
        ov.close()
    except Exception as exc:
        print("OV7670 error:", exc)

    print()
    print("GC9A01    1.28in round 240x240 — do NOT enable SPI0")
    print("          silk RST CS DC SDA SCL GND VCC")
    print("          VCC pin", config.PI_ST_VCC_PHYS, "(5V display only)")
    print("          GND pin", config.PI_ST_GND_PHYS)
    print("          SCL pin 12 / GPIO" + str(config.PI_ST_SCK_BCM))
    print("          SDA pin 32 / GPIO" + str(config.PI_ST_MOSI_BCM))
    print("          DC  pin 22 / GPIO" + str(config.PI_ST_DC_BCM))
    print("          CS  pin 24 / GPIO" + str(config.PI_ST_CS_BCM))
    print("          RST pin 26 / GPIO" + str(config.PI_ST_RST_BCM))
    try:
        from minevision.vision.st7735 import Gc9a01

        panel = Gc9a01()
        print("GC9A01:", panel.note)
        panel.close()
    except Exception as exc:
        print("GC9A01 error:", exc)


if __name__ == "__main__":
    main()
