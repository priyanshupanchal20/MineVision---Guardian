"""Canon PowerShot (PTP) live preview via gphoto2. Not a UVC webcam."""

from __future__ import annotations

import io
import subprocess
import threading
import time

import numpy as np

from minevision import config


def _jpeg_to_rgb(data: bytes) -> np.ndarray | None:
    if not data or len(data) < 32:
        return None
    try:
        from PIL import Image
    except Exception:
        return None
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = img.resize((config.PI_OV_WIDTH, config.PI_OV_HEIGHT))
    return np.asarray(img, dtype=np.float32) / 255.0


def _kill_ptp_claimers() -> None:
    for cmd in (
        ["pkill", "-f", "gvfs-gphoto2-volume-monitor"],
        ["pkill", "-f", "gvfsd-gphoto2"],
        ["pkill", "-f", "gvfs-gphoto2"],
    ):
        subprocess.run(cmd, capture_output=True, check=False)


class GphotoCamera:
    def __init__(self) -> None:
        self.ok = False
        self.note = "USB camera not probed"
        self._rgb: np.ndarray | None = None
        self._gray: np.ndarray | None = None
        self._lock = threading.Lock()
        self._run = False
        self._thread: threading.Thread | None = None
        self._open()

    def close(self) -> None:
        self._run = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def read_rgb(self) -> np.ndarray | None:
        with self._lock:
            return None if self._rgb is None else self._rgb.copy()

    def read_gray(self) -> np.ndarray | None:
        with self._lock:
            return None if self._gray is None else self._gray.copy()

    def wait_frame(self, timeout_s: float = 12.0) -> np.ndarray | None:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            g = self.read_rgb()
            if g is not None:
                return g
            time.sleep(0.2)
        return None

    def _open(self) -> None:
        if subprocess.run(["which", "gphoto2"], capture_output=True).returncode != 0:
            self.note = "gphoto2 missing — sudo apt-get install gphoto2"
            return
        _kill_ptp_claimers()
        time.sleep(0.4)
        det = subprocess.run(
            ["gphoto2", "--auto-detect"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        text = (det.stdout or "") + (det.stderr or "")
        if "usb:" not in text.lower() and "canon" not in text.lower() and "ptp" not in text.lower():
            self.note = "No PTP USB camera detected — power the Canon on, USB cable seated"
            return
        model = "Canon USB"
        for line in text.splitlines():
            if "usb:" in line.lower():
                model = line.split("usb:")[0].strip(" -") or model
                break
        self.ok = True
        self.note = f"{model} — starting PTP preview"
        self._run = True
        self._thread = threading.Thread(target=self._loop, name="canon-usb", daemon=True)
        self._thread.start()

    def _grab_jpeg(self) -> bytes | None:
        r = subprocess.run(
            [
                "gphoto2",
                "--quiet",
                "--capture-preview",
                "--stdout",
            ],
            capture_output=True,
            timeout=8,
        )
        data = r.stdout or b""
        if data[:3] == b"\xff\xd8\xff":
            return data
        err = (r.stderr or b"").decode("utf-8", "replace")
        if "busy" in err.lower() or "claim" in err.lower():
            _kill_ptp_claimers()
            self.note = "Canon USB busy — retrying after releasing other PTP programs"
        elif "unsupported" in err.lower() or "not possible" in err.lower():
            self.note = "Canon SX430 preview rejected — set camera to playback/PC connect and keep it awake"
            self._run = False
        elif err.strip():
            self.note = "Canon USB: " + err.strip().splitlines()[-1][:160]
        return None

    def _loop(self) -> None:
        while self._run:
            try:
                jpeg = self._grab_jpeg()
            except subprocess.TimeoutExpired:
                self.note = "Canon USB timed out — keep the camera awake, not in sleep"
                time.sleep(0.4)
                continue
            except Exception as exc:
                self.note = f"Canon USB error ({exc})"
                time.sleep(0.6)
                continue
            if jpeg:
                rgb = _jpeg_to_rgb(jpeg)
                if rgb is not None:
                    gray = rgb.mean(axis=2)
                    with self._lock:
                        self._rgb = rgb
                        self._gray = gray
                    self.note = f"Canon USB {rgb.shape[1]}×{rgb.shape[0]} color live"
            time.sleep(0.12)
