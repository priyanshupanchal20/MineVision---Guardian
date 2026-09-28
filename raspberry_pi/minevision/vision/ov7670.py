"""OV7670 on Raspberry Pi 3 — SCCB GPIO10/11, XCLK GPIO4, DVP parallel.

Does not use I2C1 (GPIO2/3); those belong to MLX9064X.
Python only does SCCB. Pixel sampling is ov7670_grab.c (line-sync).
A background thread publishes luma (Y) as JPEG. GPIO chroma is not used.
"""

from __future__ import annotations

import ctypes
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from minevision import config

_PID_REG = 0x0A
_OV7670_ADDR = 0x21
_MAX_LINE = 1280
_MAX_ROWS = 240
_MAX_BYTES = _MAX_LINE * _MAX_ROWS
_MIN_SCENE = 0.18

_INIT_REGS: list[tuple[int, int]] = [
    (0x12, 0x80),
]


_YUV_COMMON: list[tuple[int, int]] = [
    (0x12, 0x10),  # COM7 QVGA YUV
    (0x0C, 0x04),  # COM3 DCW
    (0x70, 0x3A),
    (0x71, 0x35),
    (0x73, 0xF1),
    (0xA2, 0x02),
    (0x15, 0x00),
    (0x40, 0xC0),  # COM15 YUV full range
    (0x3A, 0x04),  # TSLB YUYV
    (0x8C, 0x00),
    (0x3D, 0xC0),
    (0x17, 0x16),
    (0x18, 0x04),
    (0x32, 0x80),
    (0x19, 0x02),
    (0x1A, 0x7A),
    (0x03, 0x0A),
    (0x13, 0xE7),
    (0x00, 0x00),
    (0x10, 0x40),
    (0x04, 0x00),
    (0x0D, 0x80),
    (0x14, 0x6A),
    (0x3B, 0x0A),
    (0x55, 0x18),
    (0x56, 0x50),
    (0x4F, 0x80),
    (0x50, 0x80),
    (0x51, 0x00),
    (0x52, 0x22),
    (0x53, 0x5E),
    (0x54, 0x80),
]


def _qvga_fast() -> list[tuple[int, int]]:
    """QVGA, CLKRC /2, PCLK /2 — first choice for higher fps."""
    return [(0x11, 0x81), (0x3E, 0x19), (0x72, 0x11), *_YUV_COMMON]


def _qvga_yuv() -> list[tuple[int, int]]:
    """QVGA, CLKRC /4, PCLK /4 — fallback if fast mode tears."""
    return [(0x11, 0x83), (0x3E, 0x1A), (0x72, 0x11), *_YUV_COMMON]


def _qqvga_yuv() -> list[tuple[int, int]]:
    """Slowest complete-line set for this Pi 3."""
    return [(0x11, 0x87), (0x3E, 0x1B), (0x72, 0x11), *_YUV_COMMON]


def yuyv_to_rgb(buf: bytes | bytearray | memoryview, width: int = 320, height: int = 240) -> np.ndarray:
    raw = np.frombuffer(buf, dtype=np.uint8, count=width * height * 2).reshape(height, width * 2)
    rgb, _gray = _planes_to_rgb(raw, yuyv=True, swap_uv=False)
    return rgb


def _upsample_chroma(c: np.ndarray, width: int) -> np.ndarray:
    if c.shape[1] == 0:
        return np.full((c.shape[0], width), 128.0, dtype=np.float32)
    up = np.repeat(c, 2, axis=1)
    if up.shape[1] < width:
        up = np.pad(up, ((0, 0), (0, width - up.shape[1])), mode="edge")
    return up[:, :width]


def _box5(a: np.ndarray) -> np.ndarray:
    g = np.asarray(a, dtype=np.float32)
    p = np.pad(g, 2, mode="edge")
    acc = np.zeros_like(g)
    for i in range(5):
        for j in range(5):
            acc += p[i : i + g.shape[0], j : j + g.shape[1]]
    return acc / 25.0


def _planes_to_rgb(packed: np.ndarray, yuyv: bool, swap_uv: bool) -> tuple[np.ndarray, np.ndarray]:
    if yuyv:
        y = packed[:, 0::2].astype(np.float32)
        c = packed[:, 1::2].astype(np.float32)
    else:
        y = packed[:, 1::2].astype(np.float32)
        c = packed[:, 0::2].astype(np.float32)
    u = _upsample_chroma(c[:, 0::2], y.shape[1])
    v = _upsample_chroma(c[:, 1::2], y.shape[1])
    if swap_uv:
        u, v = v, u
    uf = (u - 128.0) * 0.35
    vf = (v - 128.0) * 0.35
    r = np.clip(y + 1.402 * vf, 0, 255)
    g = np.clip(y - 0.344136 * uf - 0.714136 * vf, 0, 255)
    b = np.clip(y + 1.772 * uf, 0, 255)
    rgb = np.stack([r, g, b], axis=-1) / 255.0
    gray = np.clip(y / 255.0, 0.0, 1.0)
    return rgb, gray


def _color_quality(rgb: np.ndarray) -> float:
    sat = float(np.std(rgb, axis=2).mean())
    y = rgb.mean(axis=2)
    sp = spatial_score(y)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    magenta = float(np.mean(np.maximum(0.0, (r + b) * 0.5 - g)))
    if sat < 0.01:
        return sp * 0.2
    if sat > 0.22 or magenta > 0.12:
        return sp - 2.0 * magenta
    return float(sp) + 0.6 * sat - 1.5 * magenta


def yuyv_to_gray(buf: bytes | bytearray | memoryview, width: int = 320, height: int = 240) -> np.ndarray:
    raw = np.frombuffer(buf, dtype=np.uint8, count=width * height * 2)
    y = raw[0::2].reshape(height, width)
    return y.astype(np.float32) / 255.0


def spatial_score(gray: np.ndarray) -> float:
    """Neighbour correlation. Rejects PCLK static and half-black torn frames."""
    g = np.asarray(gray, dtype=np.float32)
    if g.ndim != 2 or g.shape[1] < 8 or g.shape[0] < 8:
        return -1.0
    h, w = g.shape
    left, right = g[:, : w // 2], g[:, w // 2 :]
    mid = g[:, w // 3 : 2 * w // 3]
    if float(right.mean()) < 0.04 and float(left.mean()) > 0.08:
        return -1.0
    if float(mid.mean()) < 0.05 and float(g.mean()) > 0.12:
        return -1.0
    if float(g.std()) < 0.012:
        return -1.0
    a = g[:, :-1].ravel()
    b = g[:, 1:].ravel()
    c = g[:-1, :].ravel()
    d = g[1:, :].ravel()
    if min(float(a.std()), float(b.std()), float(c.std()), float(d.std())) < 1e-6:
        return -1.0
    hc = float(np.corrcoef(a, b)[0, 1])
    vc = float(np.corrcoef(c, d)[0, 1])
    if not (np.isfinite(hc) and np.isfinite(vc)):
        return -1.0
    return min(hc, vc)


def _bitrev_u8(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.uint8, copy=True)
    x = ((x & 0xF0) >> 4) | ((x & 0x0F) << 4)
    x = ((x & 0xCC) >> 2) | ((x & 0x33) << 2)
    return ((x & 0xAA) >> 1) | ((x & 0x55) << 1)


def _rgb565_gray(raw: np.ndarray, width: int, height: int) -> np.ndarray:
    hi = raw[0::2].astype(np.uint16)
    lo = raw[1::2].astype(np.uint16)
    p = (hi << 8) | lo
    r = ((p >> 11) & 31).astype(np.float32) / 31.0
    g = ((p >> 5) & 63).astype(np.float32) / 63.0
    b = (p & 31).astype(np.float32) / 31.0
    y = (0.299 * r + 0.587 * g + 0.114 * b).reshape(height, width)
    return y


def _to01(img: np.ndarray) -> np.ndarray:
    g = np.asarray(img, dtype=np.float32)
    if g.max() > 1.5:
        g = g / 255.0
    return np.clip(g, 0.0, 1.0)


def _fit_preview(img: np.ndarray) -> np.ndarray:
    g = np.asarray(img, dtype=np.float32)
    if g.size == 0:
        h, w = config.PI_OV_HEIGHT, config.PI_OV_WIDTH
        return np.zeros((h, w, 3) if g.ndim == 3 else (h, w), dtype=np.float32)
    if float(g.max()) > 1.5:
        g = g / 255.0
    g = np.clip(g, 0.0, 1.0)
    h, w = config.PI_OV_HEIGHT, config.PI_OV_WIDTH
    ys = max(1, int(np.ceil(h / g.shape[0])))
    xs = max(1, int(np.ceil(w / g.shape[1])))
    g = np.repeat(np.repeat(g, ys, axis=0), xs, axis=1)
    return g[:h, :w]


def _trim_stripe_lead(gray: np.ndarray) -> np.ndarray:
    """Drop a noisy HREF lead-in when the left side is a chroma beat."""
    g = _to01(gray)
    if g.shape[1] < 24:
        return g
    gx = np.abs(np.diff(g, axis=1))
    left = float(gx[:, : g.shape[1] // 5].mean())
    right = float(gx[:, g.shape[1] // 2 :].mean())
    if right > 1e-6 and left > 2.2 * right:
        return g[:, g.shape[1] // 5 :]
    return g


def _despeckle(gray: np.ndarray) -> np.ndarray:
    """3-tap horizontal median — kills single-pixel chroma ticks, not edges."""
    g = np.asarray(gray, dtype=np.float32)
    p = np.pad(g, ((0, 0), (1, 1)), mode="edge")
    return np.median(np.stack([p[:, :-2], p[:, 1:-1], p[:, 2:]], axis=0), axis=0)


def _stretch(gray: np.ndarray) -> np.ndarray:
    g = np.clip(np.asarray(gray, dtype=np.float32), 0.0, 1.0)
    lo, hi = np.percentile(g, (3.0, 97.0))
    if float(hi - lo) < 0.08:
        return g
    return np.clip((g - lo) / (hi - lo), 0.0, 1.0)


def _gray_jpeg(gray: np.ndarray) -> bytes | None:
    try:
        from io import BytesIO

        from PIL import Image
    except Exception:
        return None
    g = np.clip(np.asarray(gray, dtype=np.float32) * 255.0, 0, 255).astype(np.uint8)
    if g.ndim != 2:
        return None
    buf = BytesIO()
    Image.fromarray(g, mode="L").save(buf, format="JPEG", quality=50)
    return buf.getvalue()


def _row_luma(packed: np.ndarray) -> np.ndarray:
    """Pick Y vs U/V independently on each line so phase flips do not tear."""
    rows, lb = packed.shape
    w = lb // 2
    out = np.empty((rows, w), dtype=np.float32)
    for i in range(rows):
        even = packed[i, 0::2].astype(np.float32)
        odd = packed[i, 1::2].astype(np.float32)
        se = abs(float(even.mean()) - 128.0) + float(even.std())
        so = abs(float(odd.mean()) - 128.0) + float(odd.std())
        out[i] = even if se >= so else odd
    return out / 255.0


def _decode_yuyv(
    raw: np.ndarray, line_bytes: int, rows: int, prefer: str | None = None
) -> tuple[str, np.ndarray, np.ndarray, float]:
    """Luma only. GPIO chroma is what painted the green/pink stripes."""
    lb = int(line_bytes) & ~1
    z = np.zeros((config.PI_OV_HEIGHT, config.PI_OV_WIDTH), dtype=np.float32)
    zc = np.zeros((config.PI_OV_HEIGHT, config.PI_OV_WIDTH, 3), dtype=np.float32)
    if lb < 40 or rows < 8:
        return "empty", z, zc, -1.0
    packed = np.asarray(raw[: lb * rows], dtype=np.uint8).reshape(rows, lb)
    if prefer == "luma":
        gray = packed[:, 0::2].astype(np.float32) / 255.0
        q = 1.0
    else:
        gray = _row_luma(packed)
        q = spatial_score(gray)
        gray = _despeckle(gray)
        gray = _stretch(gray)
    gray = _fit_preview(gray)
    rgb = np.stack([gray, gray, gray], axis=-1)
    return "luma", gray, rgb, float(q)


def _ensure_grab_lib() -> Path:
    src = Path(__file__).with_name("ov7670_grab.c")
    so = Path(__file__).with_name("ov7670_grab.so")
    stamp = Path(__file__).with_name("ov7670_grab.abi")
    abi = "11"
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
    return so


class Ov7670Camera:
    def __init__(self) -> None:
        self.ok = False
        self.pid: int | None = None
        self.note = "OV7670 not probed"
        self.frames = 0
        self._gpio = None
        self._pi = None
        self._pg = None
        self._lib = None
        self._gray: np.ndarray | None = None
        self._rgb: np.ndarray | None = None
        self._jpeg: bytes | None = None
        self._jpeg_t = 0.0
        self._lock = threading.Lock()
        self._run = False
        self._thread: threading.Thread | None = None
        self._bb = False
        self.last_dvp = "no grab yet"
        self._open()

    def close(self) -> None:
        self._run = False
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
        if self._pi is not None:
            try:
                if self._bb:
                    self._pi.bb_i2c_close(config.PI_OV_SIOD_BCM)
            except Exception:
                pass
            try:
                self._pi.write(config.PI_OV_PWDN_BCM, 1)
            except Exception:
                pass

    def read_gray(self) -> np.ndarray | None:
        with self._lock:
            return self._gray

    def read_rgb(self) -> np.ndarray | None:
        with self._lock:
            return self._rgb

    def read_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def wait_frame(self, timeout_s: float = 8.0) -> np.ndarray | None:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            g = self.read_gray()
            if g is not None:
                return g
            time.sleep(0.15)
        return None

    def _open(self) -> None:
        try:
            import pigpio
        except Exception:
            self.note = "pigpio Python missing — pip install pigpio"
            return
        pi = pigpio.pi()
        if not pi.connected:
            self.note = "pigpiod is not running — sudo pigpiod"
            return
        self._pi = pi
        self._pg = pigpio

        pi.set_mode(config.PI_OV_PWDN_BCM, pigpio.OUTPUT)
        pi.set_mode(config.PI_OV_RESET_BCM, pigpio.OUTPUT)
        pi.write(config.PI_OV_PWDN_BCM, 1)
        pi.write(config.PI_OV_RESET_BCM, 1)
        pi.set_mode(config.PI_OV_SIOC_BCM, pigpio.OUTPUT)
        pi.write(config.PI_OV_SIOC_BCM, 1)
        pi.set_mode(config.PI_OV_SIOD_BCM, pigpio.INPUT)
        pi.set_pull_up_down(config.PI_OV_SIOD_BCM, pigpio.PUD_UP)
        for pin in (config.PI_OV_PCLK_BCM, config.PI_OV_VSYNC_BCM, config.PI_OV_HREF_BCM, *config.PI_OV_D_BCM):
            pi.set_mode(pin, pigpio.INPUT)
            pi.set_pull_up_down(pin, pigpio.PUD_OFF)

        pi.hardware_clock(config.PI_OV_XCLK_BCM, 8_000_000)
        time.sleep(0.08)
        pi.write(config.PI_OV_PWDN_BCM, 0)
        pi.write(config.PI_OV_RESET_BCM, 0)
        time.sleep(0.01)
        pi.write(config.PI_OV_RESET_BCM, 1)
        time.sleep(0.30)

        self._bb_open()

        pid = None
        for _ in range(8):
            pid = self._sccb_read(_PID_REG)
            if pid == 0x76:
                break
            time.sleep(0.05)
        if pid != 0x76 and self._bb:
            try:
                pi.bb_i2c_close(config.PI_OV_SIOD_BCM)
            except Exception:
                pass
            self._bb = False
            for _ in range(4):
                pid = self._sccb_read(_PID_REG)
                if pid == 0x76:
                    break
                time.sleep(0.05)
        self.pid = pid
        if pid == 0x76:
            self.ok = True
            self.note = "OV7670 PID 0x76 — starting QVGA YUV grab"
            self._run = True
            self._thread = threading.Thread(target=self._loop, name="ov7670", daemon=True)
            self._thread.start()
        elif pid in (None, 0xFF, 0x00):
            self.note = (
                "OV7670 SCCB no chip (got "
                f"{'none' if pid is None else hex(pid)}) — sudo pigpiod, 3V3 pin 17, "
                "GND pin 9, SIOD 19, SIOC 23, XCLK 7. SPI must be off."
            )
        else:
            self.note = f"SCCB device ID 0x{pid:02X} (expected 0x76)"

    def _set_xclk(self, hz: int) -> None:
        if self._pi is not None:
            try:
                self._pi.hardware_clock(config.PI_OV_XCLK_BCM, hz)
                return
            except Exception:
                pass
        try:
            subprocess.run(
                ["pigs", "hc", str(config.PI_OV_XCLK_BCM), str(int(hz))],
                check=False,
                capture_output=True,
                timeout=2,
            )
        except Exception:
            pass

    def _bb_open(self) -> None:
        pi = self._pi
        sda = config.PI_OV_SIOD_BCM
        scl = config.PI_OV_SIOC_BCM
        self._bb = False
        if pi is None:
            return
        try:
            pi.bb_i2c_close(sda)
        except Exception:
            pass
        try:
            pi.bb_i2c_open(sda, scl, 20000)
            self._bb = True
        except Exception:
            self._bb = False

    def _sda(self, level: int) -> None:
        pi = self._pi
        pg = self._pg
        sda = config.PI_OV_SIOD_BCM
        if level:
            pi.set_mode(sda, pg.INPUT)
            pi.set_pull_up_down(sda, pg.PUD_UP)
        else:
            pi.set_mode(sda, pg.OUTPUT)
            pi.write(sda, 0)

    def _scl(self, level: int) -> None:
        self._pi.write(config.PI_OV_SIOC_BCM, 1 if level else 0)
        time.sleep(0.00002)

    def _sccb_start(self) -> None:
        self._sda(1)
        self._scl(1)
        self._sda(0)
        self._scl(0)

    def _sccb_stop(self) -> None:
        self._sda(0)
        self._scl(1)
        self._sda(1)

    def _sccb_write_byte(self, val: int) -> None:
        for i in range(7, -1, -1):
            self._sda((val >> i) & 1)
            self._scl(1)
            self._scl(0)
        self._sda(1)
        self._scl(1)
        self._scl(0)

    def _sccb_read_byte(self) -> int:
        pi = self._pi
        sda = config.PI_OV_SIOD_BCM
        self._sda(1)
        val = 0
        for _ in range(8):
            self._scl(1)
            val = (val << 1) | int(pi.read(sda))
            self._scl(0)
        self._sda(1)
        self._scl(1)
        self._scl(0)
        return val

    def _sccb_read(self, reg: int) -> int | None:
        if self._bb:
            try:
                n, data = self._pi.bb_i2c_zip(
                    config.PI_OV_SIOD_BCM,
                    [4, _OV7670_ADDR, 2, 7, 1, reg & 0xFF, 3, 2, 6, 1, 3],
                )
                if n >= 1 and data:
                    return int(data[0])
            except Exception:
                pass
        try:
            self._sccb_start()
            self._sccb_write_byte((_OV7670_ADDR << 1) | 0)
            self._sccb_write_byte(reg)
            self._sccb_stop()
            time.sleep(0.002)
            self._sccb_start()
            self._sccb_write_byte((_OV7670_ADDR << 1) | 1)
            val = self._sccb_read_byte()
            self._sccb_stop()
            return val
        except Exception:
            return None

    def _sccb_write(self, reg: int, val: int) -> None:
        if self._bb:
            try:
                self._pi.bb_i2c_zip(
                    config.PI_OV_SIOD_BCM,
                    [4, _OV7670_ADDR, 2, 7, 2, reg & 0xFF, val & 0xFF, 3],
                )
                time.sleep(0.002)
                return
            except Exception:
                pass
        self._sccb_start()
        self._sccb_write_byte((_OV7670_ADDR << 1) | 0)
        self._sccb_write_byte(reg & 0xFF)
        self._sccb_write_byte(val & 0xFF)
        self._sccb_stop()
        time.sleep(0.002)

    def _apply_regs(self, regs: list[tuple[int, int]]) -> None:
        for reg, val in _INIT_REGS:
            self._sccb_write(reg, val)
        time.sleep(0.30)
        for reg, val in regs:
            self._sccb_write(reg, val)
        time.sleep(0.25)

    def _load_lib(self):
        so = _ensure_grab_lib()
        lib = ctypes.CDLL(str(so))
        lib.ov7670_grab.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.ov7670_grab.restype = ctypes.c_int
        lib.ov7670_levels.argtypes = []
        lib.ov7670_levels.restype = ctypes.c_int
        return lib

    def _grab_raw(self, rising: int, timeout_ms: int = 900) -> tuple[np.ndarray, int, int] | None:
        if self._lib is None:
            return None
        buf = (ctypes.c_uint8 * _MAX_BYTES)()
        line_b = ctypes.c_int(0)
        rows = ctypes.c_int(0)
        n = int(
            self._lib.ov7670_grab(
                buf, _MAX_BYTES, timeout_ms, rising, ctypes.byref(line_b), ctypes.byref(rows)
            )
        )
        if n == -2:
            self.note = "OV7670 cannot open /dev/gpiomem — add user to the gpio group"
            self.last_dvp = "gpiomem denied"
            return None
        lb, nr = int(line_b.value), int(rows.value)
        levels = ""
        try:
            lv = int(self._lib.ov7670_levels())
            if lv >= 0:
                levels = f" vs={bool(lv & 4)} href={bool(lv & 2)} pclk={bool(lv & 1)}"
        except Exception:
            pass
        self.last_dvp = f"line={lb} rows={nr} n={n} rising={rising}{levels}"
        if lb < 80 or (lb % 2) or nr < 30 or n < lb * 30:
            return None
        nr = min(nr, n // lb)
        if nr < 30:
            return None
        return np.ctypeslib.as_array(buf)[: lb * nr].copy(), lb, nr

    def _publish(self, gray: np.ndarray, rgb: np.ndarray) -> None:
        now = time.time()
        jpeg = None
        if now - self._jpeg_t >= 0.20:
            jpeg = _gray_jpeg(gray)
            self._jpeg_t = now
        with self._lock:
            self._gray = gray
            self._rgb = rgb
            if jpeg:
                self._jpeg = jpeg

    def _grab_scored(
        self, rising: int, prefer: str | None = None, timeout_ms: int = 900
    ) -> tuple[np.ndarray, np.ndarray, str, float] | None:
        got = self._grab_raw(rising, timeout_ms=timeout_ms)
        if got is None:
            return None
        raw, line_b, rows = got
        name, gray, rgb, score = _decode_yuyv(raw, line_b, rows, prefer=prefer)
        return gray, rgb, name, score

    def _loop(self) -> None:
        try:
            self._lib = self._load_lib()
        except Exception as exc:
            self.note = f"OV7670 SCCB OK — install gcc to grab frames ({exc})"
            return

        modes = (
            (8_000_000, _qvga_fast(), "QVGA-fast"),
            (8_000_000, _qvga_yuv(), "QVGA"),
            (8_000_000, _qqvga_yuv(), "QQVGA"),
        )
        locked_rising: int | None = None
        locked_fmt: str | None = None
        for hz, regs, label in modes:
            try:
                self._set_xclk(hz)
                self._apply_regs(regs)
            except Exception as exc:
                self.note = f"OV7670 register write failed ({exc})"
                return
            for com10 in (0x00, 0x20):
                if com10 == 0x20:
                    try:
                        self._sccb_write(0x15, 0x20)
                        time.sleep(0.15)
                    except Exception:
                        continue
                for rising in (1, 0):
                    if not self._run:
                        return
                    got = self._grab_scored(rising, timeout_ms=1400)
                    if got is None:
                        continue
                    gray, rgb, fmt, score = got
                    locked_rising = rising
                    locked_fmt = fmt
                    self._publish(gray, rgb)
                    self.frames = 1
                    edge = "rising" if rising else "falling"
                    self.note = (
                        f"OV7670 {gray.shape[1]}×{gray.shape[0]} live · "
                        f"{label} PCLK {edge}"
                    )
                    break
                if locked_rising is not None:
                    break
            if locked_rising is not None:
                break

        if locked_rising is None:
            self.note = f"OV7670 SCCB OK but DVP incomplete — {self.last_dvp}"
            return

        while self._run:
            got = self._grab_scored(locked_rising, prefer=locked_fmt, timeout_ms=900)
            if got is not None:
                gray, rgb, fmt, score = got
                locked_fmt = fmt
                self._publish(gray, rgb)
                self.frames += 1
                self.note = f"OV7670 {gray.shape[1]}×{gray.shape[0]} live"
            time.sleep(0.0)
