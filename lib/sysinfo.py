"""System information gathering for the web UI."""

import subprocess

from lib.state import load_state


def get_sysinfo():
    """Gather service status, uptime, load, temperature, and DEFCON state."""
    info = {}

    services = {}
    for svc in ["mjpg-streamer", "mjpg-alert"]:
        try:
            r = subprocess.run(["systemctl", "is-active", svc],
                               capture_output=True, text=True, timeout=5)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"

    try:
        r = subprocess.run(["pgrep", "-c", "ffmpeg"],
                           capture_output=True, text=True, timeout=5)
        services["ffmpeg"] = "active" if r.returncode == 0 else "inactive"
    except Exception:
        services["ffmpeg"] = "unknown"

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

    state = load_state()
    if state == "defcon2":
        info["defcon"] = "DEFCON 2"
    elif state == "defcon4":
        info["defcon"] = "DEFCON 4"
    else:
        info["defcon"] = "DEFCON 5"

    return info
