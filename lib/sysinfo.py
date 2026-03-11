"""System information gathering for the web UI."""

import os
import time

from lib.state import load_state

DB_PATH = "/tmp/defcon-events.db"

# Map systemd ActiveState values to simple labels
_ACTIVE_STATES = {
    "active": "active",
    "activating": "activating",
    "deactivating": "deactivating",
    "reloading": "reloading",
    "inactive": "inactive",
    "failed": "failed",
}


def _human_size(size_bytes):
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _service_state(name):
    """Read service ActiveState from /sys/fs/cgroup or systemd runtime dir."""
    try:
        path = f"/run/systemd/units/invocation:{name}.service"
        if os.path.exists(path):
            # Service has been invoked — read actual state from runtime props
            prop_path = f"/sys/fs/cgroup/system.slice/{name}.service/cgroup.events"
            if os.path.exists(prop_path):
                with open(prop_path) as f:
                    content = f.read()
                    if "populated 1" in content:
                        return "active"
                    return "inactive"
        # Fallback: check if the service's PID file or main PID exists
        pidfile = f"/run/{name}.pid"
        if os.path.exists(pidfile):
            return "active"
        # Last resort: check cgroup for any processes
        procs = f"/sys/fs/cgroup/system.slice/{name}.service/cgroup.procs"
        if os.path.exists(procs):
            with open(procs) as f:
                return "active" if f.read().strip() else "inactive"
        return "inactive"
    except Exception:
        return "unknown"


def _uptime_pretty():
    """Read uptime from /proc/uptime and format it."""
    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if mins:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        return ", ".join(parts) or "0 minutes"
    except Exception:
        return "unknown"


def get_sysinfo():
    """Gather service status, uptime, load, temperature, and DEFCON state."""
    info = {}

    services = {}
    for svc in ["mjpg-alert", "mjpg-streamer"]:
        services[svc] = _service_state(svc)
    info["services"] = services

    info["uptime"] = _uptime_pretty()

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
