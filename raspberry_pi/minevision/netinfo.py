"""LAN addresses and a stable mDNS name so the dashboard is not tied to one IP."""

from __future__ import annotations

import shutil
import socket
import subprocess
import threading
import time

LAN_NAME = "minevision"


def ipv4_addrs() -> list[str]:
    found: list[str] = []
    try:
        r = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2)
        for tok in r.stdout.split():
            if tok.count(".") == 3 and not tok.startswith("127."):
                found.append(tok)
    except Exception:
        pass
    if not found:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect(("1.1.1.1", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip.count(".") == 3 and not ip.startswith("127."):
                found.append(ip)
        except Exception:
            pass
    seen: set[str] = set()
    out: list[str] = []
    for ip in found:
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out


def host_stem() -> str:
    return socket.gethostname().split(".")[0].strip() or "raspberrypi"


def dashboard_urls(port: int) -> list[str]:
    names = [LAN_NAME, host_stem()]
    urls: list[str] = []
    seen: set[str] = set()
    for name in names:
        u = f"http://{name}.local:{port}"
        if u not in seen:
            seen.add(u)
            urls.append(u)
    for ip in ipv4_addrs():
        u = f"http://{ip}:{port}"
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


class LanAdvertiser:
    """Publish minevision.local via Avahi so the name follows DHCP."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.note = "mDNS off"
        self._run = True
        self._proc: subprocess.Popen | None = None
        self._svc: subprocess.Popen | None = None
        self._thread = threading.Thread(target=self._loop, name="mdns", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._run = False
        self._kill()

    def _kill(self) -> None:
        for proc in (self._proc, self._svc):
            if proc is None:
                continue
            try:
                proc.terminate()
            except Exception:
                pass
        self._proc = None
        self._svc = None

    def _loop(self) -> None:
        last = ""
        while self._run:
            ips = ipv4_addrs()
            key = ",".join(ips)
            if key != last:
                last = key
                self._kill()
                if ips:
                    self._publish(ips[0])
            time.sleep(8)

    def _publish(self, ip: str) -> None:
        pub = shutil.which("avahi-publish")
        if not pub:
            self.note = (
                f"no Avahi — http://{ip}:{self.port}  (sudo apt install avahi-daemon avahi-utils)"
            )
            return
        try:
            self._proc = subprocess.Popen(
                [pub, "-a", "-R", f"{LAN_NAME}.local", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._svc = subprocess.Popen(
                [pub, "-s", "MineVision", "_http._tcp", str(self.port), "MineVision Guardian"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.note = f"{LAN_NAME}.local → {ip}"
        except Exception as exc:
            self.note = f"mDNS failed ({exc})"
