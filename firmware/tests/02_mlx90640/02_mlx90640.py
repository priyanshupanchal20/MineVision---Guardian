#!/usr/bin/env python3
"""Print one MLX90640 frame. Run on Raspberry Pi 3 with I2C enabled."""
import time

try:
    import board
    import busio
    import adafruit_mlx90640
except ImportError:
    print("Install: pip install adafruit-circuitpython-mlx90640")
    raise SystemExit(1)

i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
frame = [0] * 768
print("MLX90640 32x24 °C  (Ctrl+C to stop)")
while True:
    try:
        mlx.getFrame(frame)
    except ValueError:
        continue
    print("-" * 40)
    for r in range(24):
        row = frame[r * 32 : (r + 1) * 32]
        print(" ".join(f"{v:5.1f}" for v in row))
    print(f"min={min(frame):.1f} max={max(frame):.1f}")
    time.sleep(0.4)
