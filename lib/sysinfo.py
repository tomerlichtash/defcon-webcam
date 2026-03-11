"""System information gathering for the web UI."""

import os
import subprocess

from lib.state import load_state

DB_PATH = "/tmp/defcon-events.db"


def _human_size(size_bytes):
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_sysinfo():
    """Gather service status, uptime, load, temperature, and DEFCON state."""
    info = {}

    services = {}
    for svc in ["mjpg-alert", "mjpg-streamer"]:
        try:
            r = subprocess.run(["systemctl", "is-active", svc],
                               capture_output=True, text=True, timeout=5)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"


    info["services"] = services

    try:
        r = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        info["uptime"] = r.stdout.strip()
    except Exception:
        pass

    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            info["load"] = str(min(round(float(parts[0]) * 100 / 4), 100)) + "%"
    except Exception:
        pass

    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp_c = int(f.read().strip()) / 1000
            info["temp"] = f"{temp_c:.1f}\u00b0"
    except Exception:
        pass

    try:
        info["db_size"] = _human_size(os.path.getsize(DB_PATH))
        info["db_ok"] = True
    except Exception:
        info["db_size"] = "N/A"
        info["db_ok"] = False

    state = load_state()
    if state == "defcon2":
        info["defcon"] = "DEFCON 2"
    elif state == "defcon4":
        info["defcon"] = "DEFCON 4"
    else:
        info["defcon"] = "DEFCON 5"

    return info
