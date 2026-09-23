"""Launch MineVision Guardian command dashboard."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import uvicorn

from minevision import config
from minevision.netinfo import dashboard_urls


def _boost_pi3() -> None:
    """Run the Pi 3 at its performance governor. Ignore failures if not root."""
    try:
        os.nice(-15)
    except OSError:
        pass
    for gov in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"):
        try:
            gov.write_text("performance")
        except OSError:
            pass


def main() -> None:
    _boost_pi3()
    print("MineVision Guardian — SIH 26007")
    print(f"  mode: {config.MODE}")
    for url in dashboard_urls(config.PORT):
        print(f"  dashboard: {url}")
    print(f"  api docs:  http://127.0.0.1:{config.PORT}/docs")
    uvicorn.run(
        "minevision.api:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
