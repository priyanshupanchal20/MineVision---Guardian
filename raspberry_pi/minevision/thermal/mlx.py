"""Live MLX90640 / MLX90641 on Raspberry Pi I2C1 (pins 1/3/5/6)."""

from __future__ import annotations

import threading
import time

import numpy as np

from minevision import config


def _upsample_16x12(frame: np.ndarray) -> np.ndarray:
    """MLX90641 is 16×12; analyzer expects 24×32."""
    src = np.asarray(frame, dtype=np.float32).reshape(12, 16)
    out = np.empty((config.THERMAL_ROWS, config.THERMAL_COLS), dtype=np.float32)
    ys = np.linspace(0, 11, config.THERMAL_ROWS)
    xs = np.linspace(0, 15, config.THERMAL_COLS)
    for r, y in enumerate(ys):
        y0 = int(np.floor(y))
        y1 = min(11, y0 + 1)
        fy = y - y0
        for c, x in enumerate(xs):
            x0 = int(np.floor(x))
            x1 = min(15, x0 + 1)
            fx = x - x0
            out[r, c] = (
                src[y0, x0] * (1 - fy) * (1 - fx)
                + src[y1, x0] * fy * (1 - fx)
                + src[y0, x1] * (1 - fy) * fx
                + src[y1, x1] * fy * fx
            )
    return out


class MlxCamera:
    """Returns 24×32 °C frames, or None if the chip is not on I2C1."""

    def __init__(self) -> None:
        self.kind = "none"
        self._cam = None
        self._buf: list[float] | None = None
        self._last: np.ndarray | None = None
        self._last_t = 0.0
        self._lock = threading.Lock()
        self._open()

    def _open(self) -> None:
        try:
            import board
            import busio
        except Exception:
            return
        i2c = None
        for hz in (100000, 400000):
            try:
                i2c = busio.I2C(board.SCL, board.SDA, frequency=hz)
                break
            except Exception:
                i2c = None
        if i2c is None:
            return
        try:
            import adafruit_mlx90640

            cam = adafruit_mlx90640.MLX90640(i2c)
            # 8 Hz drops frames on Pi I2C; 2 Hz is the rate that actually returns a picture.
            cam.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
            self._cam = cam
            self._buf = [0.0] * 768
            self.kind = "mlx90640"
            return
        except Exception:
            pass
        try:
            import adafruit_mlx90641

            cam = adafruit_mlx90641.MLX90641(i2c)
            cam.refresh_rate = adafruit_mlx90641.RefreshRate.REFRESH_2_HZ
            self._cam = cam
            self._buf = [0.0] * 192
            self.kind = "mlx90641"
        except Exception:
            self._cam = None
            self.kind = "none"

    def peek(self) -> np.ndarray | None:
        return self._last

    def read(self) -> np.ndarray | None:
        if self._cam is None or self._buf is None:
            return None
        with self._lock:
            now = time.time()
            if self._last is not None and now - self._last_t < 0.45:
                return self._last
            frame = None
            for _ in range(2):
                try:
                    self._cam.getFrame(self._buf)
                    raw = np.asarray(self._buf, dtype=np.float32)
                    if self.kind == "mlx90641":
                        frame = _upsample_16x12(raw)
                    else:
                        frame = raw.reshape(config.THERMAL_ROWS, config.THERMAL_COLS)
                    break
                except Exception:
                    time.sleep(0.05)
            if frame is None:
                return self._last
            self._last = frame
            self._last_t = now
            return frame
