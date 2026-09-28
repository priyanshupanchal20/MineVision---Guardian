"""Visible-camera visibility confidence (contrast, edges, blur)."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

import numpy as np

from minevision import config


def gray_to_png(gray: np.ndarray) -> bytes:
    """Minimal 8-bit grayscale PNG (stdlib only)."""
    img = np.asarray(gray, dtype=np.float32)
    if img.ndim == 3:
        img = img.mean(axis=2)
    if img.size == 0:
        img = np.full((16, 16), 0.45, dtype=np.float32)
    if float(img.max()) <= 1.5:
        u8 = np.clip(img * 255.0, 0, 255).astype(np.uint8)
    else:
        u8 = np.clip(img, 0, 255).astype(np.uint8)
    h, w = int(u8.shape[0]), int(u8.shape[1])

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + u8[y].tobytes() for y in range(h))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 1))
        + chunk(b"IEND", b"")
    )


def rgb_to_png(rgb: np.ndarray) -> bytes:
    """Minimal 8-bit RGB PNG (stdlib only)."""
    img = np.asarray(rgb, dtype=np.float32)
    if img.ndim == 2:
        return gray_to_png(img)
    if img.size == 0:
        img = np.full((16, 16, 3), 0.45, dtype=np.float32)
    if float(img.max()) <= 1.5:
        u8 = np.clip(img * 255.0, 0, 255).astype(np.uint8)
    else:
        u8 = np.clip(img, 0, 255).astype(np.uint8)
    if u8.shape[-1] > 3:
        u8 = u8[..., :3]
    h, w = int(u8.shape[0]), int(u8.shape[1])

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + u8[y].tobytes() for y in range(h))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 1))
        + chunk(b"IEND", b"")
    )


def gray_to_jpeg(gray: np.ndarray, quality: int = 50) -> bytes | None:
    """Fast JPEG for the dashboard. None if Pillow is missing."""
    try:
        from PIL import Image
    except Exception:
        return None
    from io import BytesIO

    g = np.asarray(gray, dtype=np.float32)
    if g.ndim == 3:
        g = 0.299 * g[..., 0] + 0.587 * g[..., 1] + 0.114 * g[..., 2]
    if g.size == 0:
        g = np.full((16, 16), 0.45, dtype=np.float32)
    if float(g.max()) <= 1.5:
        u8 = np.clip(g * 255.0, 0, 255).astype(np.uint8)
    else:
        u8 = np.clip(g, 0, 255).astype(np.uint8)
    buf = BytesIO()
    Image.fromarray(u8, mode="L").save(buf, format="JPEG", quality=int(quality))
    return buf.getvalue()


def preview_bytes(img: np.ndarray) -> tuple[bytes, str]:
    """Encode a gray or RGB frame for the dashboard (JPEG if possible)."""
    jpg = gray_to_jpeg(img)
    if jpg:
        return jpg, "image/jpeg"
    g = np.asarray(img, dtype=np.float32)
    if g.ndim == 3:
        return rgb_to_png(g), "image/png"
    return gray_to_png(g), "image/png"


def preview_rgb(rgb: np.ndarray) -> np.ndarray:
    """Stretch luminance for the dashboard; keep hue."""
    img = np.asarray(rgb, dtype=np.float32)
    if img.ndim != 3:
        g = preview_gray(img)
        return np.stack([g, g, g], axis=-1)
    if float(img.max()) > 1.5:
        img = img / 255.0
    img = np.clip(img, 0.0, 1.0)
    y = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
    lo, hi = np.percentile(y, (4.0, 96.0))
    if float(hi - lo) < 0.08:
        return img
    y2 = np.clip((y - lo) / (hi - lo), 0.0, 1.0)
    gain = y2 / np.maximum(y, 1e-4)
    gain = np.clip(gain, 0.4, 2.5)
    return np.clip(img * gain[..., None], 0.0, 1.0)


def preview_gray(gray: np.ndarray) -> np.ndarray:
    """Percentile stretch for the dashboard still. Fusion still uses the raw frame."""
    g = np.asarray(gray, dtype=np.float32)
    if g.ndim == 3:
        g = g.mean(axis=2)
    if g.size == 0:
        return g
    if float(g.max()) > 1.5:
        g = g / 255.0
    lo, hi = np.percentile(g, (4.0, 96.0))
    if float(hi - lo) < 0.08:
        return np.clip(g, 0.0, 1.0)
    return np.clip((g - lo) / (hi - lo), 0.0, 1.0)


@dataclass
class VisibilityResult:
    confidence: float
    label: str
    contrast: float
    edge_density: float
    blur_score: float


def _label(conf: float) -> str:
    if conf >= 0.65:
        return "GOOD"
    if conf >= 0.35:
        return "DEGRADED"
    return "POOR"


def visibility_from_gray(gray: np.ndarray) -> VisibilityResult:
    img = np.asarray(gray, dtype=np.float32)
    if img.ndim == 3:
        img = img.mean(axis=2)
    if img.max() > 1.5:
        img = img / 255.0

    contrast = float(np.clip(img.std() / 0.5, 0.0, 1.0))  # σ/0.5 ≈ σ_px/128 if 0–1

    # Sobel-ish edge density without requiring cv2
    gy, gx = np.gradient(img)
    mag = np.hypot(gx, gy)
    edge = float(np.clip((mag > 0.08).mean() / 0.25, 0.0, 1.0))

    lap = (
        np.roll(img, 1, 0)
        + np.roll(img, -1, 0)
        + np.roll(img, 1, 1)
        + np.roll(img, -1, 1)
        - 4 * img
    )
    lap_var = float(lap.var()) * (255.0**2)  # back to 8-bit-ish variance
    blur_n = float(np.clip(lap_var / 200.0, 0.0, 1.0))

    conf = float(np.clip(0.45 * contrast + 0.35 * edge + 0.20 * blur_n, 0.0, 1.0))
    return VisibilityResult(
        confidence=round(conf, 3),
        label=_label(conf),
        contrast=round(contrast, 3),
        edge_density=round(edge, 3),
        blur_score=round(blur_n, 3),
    )


def synthetic_scene(fog_amount: float, rng: np.random.Generator | None = None) -> np.ndarray:
    """fog_amount 0=clear textured scene, 1=uniform grey."""
    rng = rng or np.random.default_rng(1)
    h, w = 180, 320
    yy, xx = np.mgrid[0:h, 0:w]
    road = 0.35 + 0.15 * np.sin(xx / 12.0) + 0.1 * (yy / h)
    rocks = (np.sin(xx / 7) * np.cos(yy / 9) > 0.4).astype(float) * 0.3
    img = np.clip(road + rocks, 0, 1)
    fog = fog_amount * 0.75 + (1 - fog_amount) * img
    noise = rng.normal(0, 0.02 * (1 - 0.7 * fog_amount), img.shape)
    return np.clip(fog + noise, 0, 1).astype(np.float32)


def no_signal_frame(h: int | None = None, w: int | None = None) -> np.ndarray:
    """Live-mode placeholder — not a fake haul-road scene."""
    h = h or config.PI_OV_HEIGHT
    w = w or config.PI_OV_WIDTH
    img = np.full((h, w), 0.10, dtype=np.float32)
    img[h // 2 - 3 : h // 2 + 3, :] = 0.32
    return img


class CameraSource:
    """OV7670 on the Pi header. USB Canon if MINEVISION_USB_CAM=1. Sim uses synthetic."""

    def __init__(self) -> None:
        self.cap = None
        self.ov = None
        self.usb = None
        self.source = "synthetic"
        self.ov_note = ""
        if config.USB_CAM and config.MODE == "live":
            self._open_usb()
        if self.usb is None and config.OV7670_CAM:
            self._open_ov7670()
        if self.usb is None and self.ov is None and config.MODE == "live":
            self.source = "none"
            if not self.ov_note:
                self.ov_note = "No camera — check OV7670 wiring or plug USB Canon"

    def _open_usb(self) -> None:
        try:
            from minevision.vision.usb_canon import GphotoCamera

            cam = GphotoCamera()
            self.ov_note = cam.note
            if cam.ok:
                cam.wait_frame(12.0)
                self.ov_note = cam.note
                self.usb = cam
                self.source = "usb"
                return
            cam.close()
        except Exception as exc:
            self.ov_note = f"USB camera error ({exc})"
        if self.usb is None:
            try:
                import cv2

                for idx in range(4):
                    cap = cv2.VideoCapture(idx)
                    if cap is None or not cap.isOpened():
                        if cap is not None:
                            cap.release()
                        continue
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        self.cap = cap
                        self.source = "usb"
                        self.ov_note = f"V4L2 /dev/video{idx}"
                        return
                    cap.release()
            except Exception:
                self.cap = None

    def _open_ov7670(self) -> None:
        try:
            from minevision.vision.ov7670 import Ov7670Camera

            ov = Ov7670Camera()
            if ov.ok:
                ov.wait_frame(16.0)
            self.ov_note = ov.note
            if ov.ok:
                self.ov = ov
                self.source = "ov7670"
            elif config.MODE == "live" and self.source != "usb":
                self.source = "none"
        except Exception as exc:
            self.ov_note = str(exc)
            if config.MODE == "live" and self.usb is None:
                self.source = "none"

    def read_rgb(self, fog_amount: float = 0.0) -> np.ndarray:
        if self.usb is not None:
            rgb = self.usb.read_rgb()
            if rgb is not None:
                self.source = "usb"
                self.ov_note = self.usb.note
                return rgb
            self.source = "usb"
            self.ov_note = self.usb.note
            if config.MODE == "live":
                g = no_signal_frame()
                return np.stack([g, g, g], axis=-1)
        if self.ov is not None:
            rgb = self.ov.read_rgb()
            if rgb is not None:
                self.source = "ov7670"
                self.ov_note = self.ov.note
                return rgb
            g = self.ov.read_gray()
            if g is not None:
                self.source = "ov7670"
                self.ov_note = self.ov.note
                return np.stack([g, g, g], axis=-1)
            self.source = "ov7670"
            self.ov_note = self.ov.note
            if config.MODE == "live":
                g = no_signal_frame()
                return np.stack([g, g, g], axis=-1)
        if self.cap is not None:
            ok, frame = self.cap.read()
            if ok:
                import cv2

                small = cv2.resize(frame, (320, 240))
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                return rgb.astype(np.float32) / 255.0
        g = self.read_gray(fog_amount)
        if g.ndim == 3:
            return g
        return np.stack([g, g, g], axis=-1)

    def read_gray(self, fog_amount: float = 0.0) -> np.ndarray:
        if self.usb is not None:
            g = self.usb.read_gray()
            if g is not None:
                self.source = "usb"
                self.ov_note = self.usb.note
                return g
            rgb = self.usb.read_rgb()
            if rgb is not None:
                self.source = "usb"
                self.ov_note = self.usb.note
                return rgb.mean(axis=2)
            self.source = "usb"
            self.ov_note = self.usb.note
            if config.MODE == "live":
                return no_signal_frame()
        if self.ov is not None:
            g = self.ov.read_gray()
            if g is not None:
                self.source = "ov7670"
                self.ov_note = self.ov.note
                return g
            self.source = "ov7670"
            self.ov_note = self.ov.note
            if config.MODE == "live":
                return no_signal_frame()
        if self.cap is not None:
            ok, frame = self.cap.read()
            if ok:
                import cv2

                small = cv2.resize(frame, (320, 240))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                return gray.astype(np.float32) / 255.0
        if config.MODE == "live":
            return no_signal_frame()
        return synthetic_scene(fog_amount)

    def preview_image(self) -> tuple[bytes, str]:
        """Cached JPEG from the OV7670 thread, else a still encode."""
        if self.ov is not None:
            jpeg = self.ov.read_jpeg()
            if jpeg:
                return jpeg, "image/jpeg"
        g = self.read_gray(0.0)
        data, mime = preview_bytes(preview_gray(g))
        return data, mime
