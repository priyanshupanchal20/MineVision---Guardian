"""1.28 inch 240x240 GC9A01 round TFT.

Hardware SPI0 (GPIO10/11) belongs to the OV7670. Pixel data is clocked
with mmap GPIO (gc9a01_blit.c). pigpio 500 kHz is only the fallback.
Module silk (left to right): RST CS DC SDA SCL GND VCC. IC GC9A01.
"""

from __future__ import annotations

import ctypes
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from minevision import config

_SLPOUT, _DISPON = 0x11, 0x29
_CASET, _RASET, _RAMWR = 0x2A, 0x2B, 0x2C
_INVON, _MADCTL, _COLMOD, _TEON = 0x21, 0x36, 0x3A, 0x35

# Proven GC9A01 bring-up (TFT_eSPI / Adafruit GC9A01A).
_INIT: list[tuple[int, bytes, int]] = [
    (0xEF, b"", 0),
    (0xEB, b"\x14", 0),
    (0xFE, b"", 0),
    (0xEF, b"", 0),
    (0xEB, b"\x14", 0),
    (0x84, b"\x40", 0),
    (0x85, b"\xff", 0),
    (0x86, b"\xff", 0),
    (0x87, b"\xff", 0),
    (0x88, b"\x0a", 0),
    (0x89, b"\x21", 0),
    (0x8A, b"\x00", 0),
    (0x8B, b"\x80", 0),
    (0x8C, b"\x01", 0),
    (0x8D, b"\x01", 0),
    (0x8E, b"\xff", 0),
    (0x8F, b"\xff", 0),
    (0xB6, b"\x00\x20", 0),
    (0x36, b"", 0),  # MADCTL filled at runtime
    (0x3A, b"\x05", 0),
    (0x90, b"\x08\x08\x08\x08", 0),
    (0xBD, b"\x06", 0),
    (0xBC, b"\x00", 0),
    (0xFF, b"\x60\x01\x04", 0),
    (0xC3, b"\x13", 0),
    (0xC4, b"\x13", 0),
    (0xC9, b"\x22", 0),
    (0xBE, b"\x11", 0),
    (0xE1, b"\x10\x0e", 0),
    (0xDF, b"\x21\x0c\x02", 0),
    (0xF0, b"\x45\x09\x08\x08\x26\x2a", 0),
    (0xF1, b"\x43\x70\x72\x36\x37\x6f", 0),
    (0xF2, b"\x45\x09\x08\x08\x26\x2a", 0),
    (0xF3, b"\x43\x70\x72\x36\x37\x6f", 0),
    (0xED, b"\x1b\x0b", 0),
    (0xAE, b"\x77", 0),
    (0xCD, b"\x63", 0),
    (0x70, b"\x07\x07\x04\x0e\x0f\x09\x07\x08\x03", 0),
    (0xE8, b"\x34", 0),
    (0x62, b"\x18\x0d\x71\xed\x70\x70\x18\x0f\x71\xef\x70\x70", 0),
    (0x63, b"\x18\x11\x71\xf1\x70\x70\x18\x13\x71\xf3\x70\x70", 0),
    (0x64, b"\x28\x29\xf1\x01\xf1\x00\x07", 0),
    (0x66, b"\x3c\x00\xcd\x67\x45\x45\x10\x00\x00\x00", 0),
    (0x67, b"\x00\x3c\x00\x00\x00\x01\x54\x10\x32\x98", 0),
    (0x74, b"\x10\x85\x80\x00\x00\x4e\x00", 0),
    (0x98, b"\x3e\x07", 0),
    (0x35, b"", 0),
    (0x21, b"", 0),
    (0x11, b"", 120),
    (0x29, b"", 20),
]


def fit_square(gray: np.ndarray, width: int = 240, height: int = 240) -> np.ndarray:
    g = np.asarray(gray, dtype=np.float32)
    if g.ndim == 3:
        g = g.mean(axis=2)
    if g.size == 0:
        return np.zeros((height, width), dtype=np.float32)
    if float(g.max()) > 1.5:
        g = g / 255.0
    g = np.clip(g, 0.0, 1.0)
    h, w = g.shape
    side = min(h, w)
    y0 = (h - side) // 2
    x0 = (w - side) // 2
    sq = g[y0 : y0 + side, x0 : x0 + side]
    ys = np.linspace(0, side - 1, height).astype(np.int32)
    xs = np.linspace(0, side - 1, width).astype(np.int32)
    return sq[ys][:, xs]


def fit_128(gray: np.ndarray, width: int = 128, height: int = 128) -> np.ndarray:
    return fit_square(gray, width, height)


def gray_to_rgb565(gray: np.ndarray) -> bytes:
    u8 = np.clip(np.asarray(gray, dtype=np.float32) * 255.0, 0, 255).astype(np.uint16)
    pix = ((u8 >> 3) << 11) | ((u8 >> 2) << 5) | (u8 >> 3)
    return np.asarray(pix, dtype=">u2").tobytes()


def rgb_to_rgb565(rgb: np.ndarray) -> bytes:
    u8 = np.clip(np.asarray(rgb, dtype=np.float32) * 255.0, 0, 255).astype(np.uint16)
    r, g, b = u8[..., 0], u8[..., 1], u8[..., 2]
    pix = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return np.asarray(pix, dtype=">u2").tobytes()


def _nn_resize(img: np.ndarray, height: int, width: int) -> np.ndarray:
    src = np.asarray(img)
    if src.shape[0] == height and src.shape[1] == width:
        return src
    ys = np.linspace(0, src.shape[0] - 1, height).astype(np.int32)
    xs = np.linspace(0, src.shape[1] - 1, width).astype(np.int32)
    return src[ys][:, xs]


def thermal_to_rgb(temps: np.ndarray) -> np.ndarray:
    """Ironbow: cold=blue, mid=yellow, hot=white. Shape matches input."""
    t = np.asarray(temps, dtype=np.float32)
    lo, hi = np.percentile(t, (8, 92))
    if hi - lo < 0.4:
        lo, hi = float(np.min(t)), float(np.max(t)) + 1e-3
    n = np.clip((t - lo) / (hi - lo), 0.0, 1.0)
    r = np.clip(1.5 * n - 0.15, 0.0, 1.0)
    g = np.clip(1.7 * n - 0.45, 0.0, 1.0)
    b = np.clip(1.0 - 1.4 * n, 0.0, 0.55) + np.clip(2.2 * n - 1.6, 0.0, 1.0)
    return np.stack((r, g, np.clip(b, 0.0, 1.0)), axis=-1).astype(np.float32)


def compose_dual(gray: np.ndarray | None, temps: np.ndarray | None, size: int = 240) -> np.ndarray:
    """Top half = OV7670 luma, bottom half = MLX90640 ironbow, 240×240."""
    out = np.zeros((size, size, 3), dtype=np.float32)
    split = size // 2
    if gray is not None:
        vis = fit_square(np.asarray(gray, dtype=np.float32), size, size)
        vis = _nn_resize(vis, split - 2, size)
        out[: vis.shape[0], :, 0] = vis
        out[: vis.shape[0], :, 1] = vis
        out[: vis.shape[0], :, 2] = vis
    else:
        out[: split - 2, :, :] = 0.06
    out[split - 2 : split + 2, :, 0] = 0.85
    out[split - 2 : split + 2, :, 1] = 0.45
    out[split - 2 : split + 2, :, 2] = 0.05
    if temps is not None:
        heat = thermal_to_rgb(np.asarray(temps, dtype=np.float32))
        heat = _nn_resize(heat, size - (split + 2), size)
        out[split + 2 : split + 2 + heat.shape[0], : heat.shape[1], :] = heat
    else:
        out[split + 2 :, :, 0] = 0.15
        out[split + 2 :, :, 1] = 0.35
        out[split + 2 :, :, 2] = 0.55
    return out


def _ensure_blit_lib():
    src = Path(__file__).with_name("gc9a01_blit.c")
    so = Path(__file__).with_name("gc9a01_blit.so")
    stamp = Path(__file__).with_name("gc9a01_blit.abi")
    abi = "2"
    need = True
    if so.exists() and stamp.exists() and stamp.read_text().strip() == abi:
        if so.stat().st_mtime >= src.stat().st_mtime:
            need = False
    if need:
        cmds = [
            [
                "gcc",
                "-O3",
                "-march=armv8-a",
                "-mtune=cortex-a53",
                "-fomit-frame-pointer",
                "-shared",
                "-fPIC",
                "-o",
                str(so),
                str(src),
            ],
            ["gcc", "-O3", "-fomit-frame-pointer", "-shared", "-fPIC", "-o", str(so), str(src)],
        ]
        last = None
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            last = r
            if r.returncode == 0 and so.exists():
                break
        if last is None or last.returncode != 0 or not so.exists():
            err = ((last.stderr if last else "") or (last.stdout if last else "") or "gcc failed").strip()[:300]
            raise RuntimeError(err)
        stamp.write_text(abi)
    lib = ctypes.CDLL(str(so))
    lib.gc9a01_init.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.gc9a01_init.restype = ctypes.c_int
    lib.gc9a01_write.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
    lib.gc9a01_write.restype = ctypes.c_int
    return lib


class Gc9a01:
    def __init__(self) -> None:
        self.ok = False
        self.note = "GC9A01 not probed"
        self._pi = None
        self._fast = None
        self._open()

    def close(self) -> None:
        if self._pi is None:
            return
        try:
            self._pi.bb_spi_close(config.PI_ST_CS_BCM)
        except Exception:
            pass
        try:
            self._pi.stop()
        except Exception:
            pass
        self._pi = None
        self._fast = None

    def show_gray(self, gray: np.ndarray) -> None:
        rgb = np.repeat(fit_square(gray, config.PI_ST_WIDTH, config.PI_ST_HEIGHT)[..., None], 3, axis=2)
        self.show_rgb(rgb)

    def show_rgb(self, rgb: np.ndarray) -> None:
        if not self.ok:
            return
        frame = rgb_to_rgb565(rgb)
        w, h = config.PI_ST_WIDTH, config.PI_ST_HEIGHT
        stride = w * 2
        # Two windows so the thermal half is not the tail of one long SPI burst.
        for y0, y1 in ((0, h // 2 - 1), (h // 2, h - 1)):
            self._window(0, y0, w - 1, y1)
            self._cmd(_RAMWR)
            self._data(frame[y0 * stride : (y1 + 1) * stride])

    def _open(self) -> None:
        try:
            import pigpio
        except Exception:
            self.note = "GC9A01 needs pigpio"
            return
        pi = pigpio.pi()
        if not pi.connected:
            self.note = "GC9A01: pigpiod is not running — sudo pigpiod"
            return
        self._pi = pi
        for pin in (
            config.PI_ST_CS_BCM,
            config.PI_ST_MOSI_BCM,
            config.PI_ST_SCK_BCM,
            config.PI_ST_DC_BCM,
            config.PI_ST_RST_BCM,
        ):
            pi.set_mode(pin, pigpio.OUTPUT)
        try:
            pi.bb_spi_close(config.PI_ST_CS_BCM)
        except Exception:
            pass
        pi.write(config.PI_ST_CS_BCM, 1)
        pi.write(config.PI_ST_SCK_BCM, 0)
        pi.write(config.PI_ST_DC_BCM, 1)
        pi.write(config.PI_ST_RST_BCM, 0)
        time.sleep(0.05)
        pi.write(config.PI_ST_RST_BCM, 1)
        time.sleep(0.15)
        try:
            lib = _ensure_blit_lib()
            if int(
                lib.gc9a01_init(
                    config.PI_ST_CS_BCM,
                    config.PI_ST_MOSI_BCM,
                    config.PI_ST_SCK_BCM,
                    config.PI_ST_DC_BCM,
                )
            ) == 0:
                self._fast = lib
        except Exception:
            self._fast = None
        if self._fast is None and not self._open_pigpio_spi(pi):
            self.note = "GC9A01 SPI open failed (need gcc for fast blit, or pigpio 500k)"
            return
        try:
            self._init_panel()
        except Exception as exc:
            self.note = f"GC9A01 init failed ({exc})"
            return
        self.ok = True
        demo = np.linspace(0.08, 0.85, config.PI_ST_HEIGHT * config.PI_ST_WIDTH, dtype=np.float32)
        demo = demo.reshape(config.PI_ST_HEIGHT, config.PI_ST_WIDTH)
        heat = np.linspace(18.0, 70.0, 24 * 32, dtype=np.float32).reshape(24, 32)
        self.show_rgb(compose_dual(demo, heat, config.PI_ST_WIDTH))
        how = "fast GPIO" if self._fast is not None else "pigpio 500k"
        self.note = f"GC9A01 240×240 {how} · SCL pin12 SDA pin32 CS pin24 DC pin22 RST pin26"

    def _open_pigpio_spi(self, pi) -> bool:
        try:
            pi.bb_spi_close(config.PI_ST_CS_BCM)
        except Exception:
            pass
        for baud in (500_000, 250_000, 125_000):
            try:
                err = pi.bb_spi_open(
                    config.PI_ST_CS_BCM,
                    config.PI_ST_MISO_BCM,
                    config.PI_ST_MOSI_BCM,
                    config.PI_ST_SCK_BCM,
                    baud,
                    0,
                )
            except Exception:
                try:
                    pi.bb_spi_close(config.PI_ST_CS_BCM)
                except Exception:
                    pass
                continue
            if err == 0:
                return True
            try:
                pi.bb_spi_close(config.PI_ST_CS_BCM)
            except Exception:
                pass
        return False

    def _init_panel(self) -> None:
        for cmd, payload, delay_ms in _INIT:
            if cmd == _MADCTL:
                payload = bytes([config.PI_ST_MADCTL & 0xFF])
            self._cmd(cmd)
            if payload:
                self._data(payload)
            if delay_ms:
                time.sleep(delay_ms / 1000.0)

    def _window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        x0 += config.PI_ST_COLSTART
        x1 += config.PI_ST_COLSTART
        y0 += config.PI_ST_ROWSTART
        y1 += config.PI_ST_ROWSTART
        self._cmd(_CASET)
        self._data(bytes([(x0 >> 8) & 0xFF, x0 & 0xFF, (x1 >> 8) & 0xFF, x1 & 0xFF]))
        self._cmd(_RASET)
        self._data(bytes([(y0 >> 8) & 0xFF, y0 & 0xFF, (y1 >> 8) & 0xFF, y1 & 0xFF]))

    def _cmd(self, cmd: int) -> None:
        self._xfer(0, bytes([cmd & 0xFF]))

    def _data(self, payload: bytes) -> None:
        if payload:
            self._xfer(1, payload)

    def _xfer(self, dc: int, payload: bytes) -> None:
        if not payload:
            return
        if self._fast is not None:
            buf = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
            self._fast.gc9a01_write(int(dc), buf, len(payload))
            return
        pi = self._pi
        if pi is None:
            return
        pi.write(config.PI_ST_DC_BCM, 1 if dc else 0)
        step = 4096
        for i in range(0, len(payload), step):
            pi.bb_spi_xfer(config.PI_ST_CS_BCM, payload[i : i + step])


St7735 = Gc9a01


class CameraTft:
    """Pushes OV7670 (top) + MLX90640 (bottom) onto the GC9A01 round TFT."""

    def __init__(self, camera, mlx=None) -> None:
        self.ok = False
        self.note = "GC9A01 disabled"
        self._cam = camera
        self._mlx = mlx
        self._panel: Gc9a01 | None = None
        self._run = False
        self._thread: threading.Thread | None = None
        if not config.ST7735:
            return
        try:
            panel = Gc9a01()
        except Exception as exc:
            self.note = f"GC9A01 failed ({exc})"
            return
        self.note = panel.note
        self.ok = panel.ok
        if not panel.ok:
            panel.close()
            return
        self._panel = panel
        self._run = True
        self._thread = threading.Thread(target=self._loop, name="gc9a01", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._run = False
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
        if self._panel is not None:
            self._panel.close()
            self._panel = None

    def _loop(self) -> None:
        panel = self._panel
        if panel is None:
            return
        last_gray = None
        last_temps = None
        next_mlx = 0.0
        last_fid = -1
        last_mlx_id = -1
        seen_mlx = -1
        while self._run:
            try:
                ov = getattr(self._cam, "ov", None)
                fid = int(getattr(ov, "frames", 0) or 0)
                if self._cam is not None:
                    gray = self._cam.read_gray(0.0)
                    if gray is not None:
                        last_gray = gray
                now = time.time()
                mlx = self._mlx
                if mlx is not None:
                    peeked = mlx.peek() if hasattr(mlx, "peek") else None
                    if peeked is not None:
                        if last_temps is None:
                            last_mlx_id += 1
                        last_temps = peeked
                    if now >= next_mlx:
                        next_mlx = now + 0.40
                        temps = mlx.read()
                        if temps is not None:
                            last_temps = temps
                            last_mlx_id += 1
                if last_gray is None and last_temps is None:
                    time.sleep(0.01)
                    continue
                if fid == last_fid and last_mlx_id == seen_mlx:
                    time.sleep(0.004)
                    continue
                seen_mlx = last_mlx_id
                last_fid = fid
                panel.show_rgb(compose_dual(last_gray, last_temps, config.PI_ST_WIDTH))
                if self.ok:
                    kind = getattr(mlx, "kind", "none") if mlx is not None else "none"
                    if last_temps is not None:
                        src = f"OV7670+{kind}"
                    else:
                        src = f"OV7670, thermal {kind} no frame"
                    how = "fast" if panel._fast is not None else "500k"
                    self.note = f"GC9A01 240×240 {src} {how}"
            except Exception as exc:
                self.note = f"GC9A01 blit failed ({exc})"
            time.sleep(0.001)
