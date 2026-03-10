"""Camera snapshot helpers."""

import subprocess
import time

from lib.config import SNAPSHOT_PATH


def take_alert_snapshot(mode):
    """Take a snapshot, adjusting exposure for night mode."""
    if mode == "night":
        subprocess.run(["v4l2-ctl", "--device=/dev/video0",
            "--set-ctrl=auto_exposure=1",
            "--set-ctrl=exposure_time_absolute=2047",
            "--set-ctrl=gain=0"], timeout=5)
        time.sleep(3)

    subprocess.run(["curl", "-s", "-o", SNAPSHOT_PATH, "--max-time", "10",
        "http://localhost:8080/?action=snapshot"], timeout=15)

    if mode == "night":
        subprocess.run(["v4l2-ctl", "--device=/dev/video0",
            "--set-ctrl=auto_exposure=3",
            "--set-ctrl=gain=255"], timeout=5)
