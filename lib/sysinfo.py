"""System information gathering for the web UI."""

import os
import re
import subprocess
import tempfile
import time

from lib.config import IS_LINUX, HAS_CAMERA
from lib.geocode import GEO_DB_PATH, city_count, lookup_many
from lib.alert_log import load_log
from lib.state import load_state

DB_PATH = os.path.join(tempfile.gettempdir(), "defcon-events.db")


def _human_size(size_bytes):
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _service_state_linux(name):
    """Read service ActiveState from /sys/fs/cgroup or systemd runtime dir."""
    try:
        path = f"/run/systemd/units/invocation:{name}.service"
        if os.path.exists(path):
            prop_path = f"/sys/fs/cgroup/system.slice/{name}.service/cgroup.events"
            if os.path.exists(prop_path):
                with open(prop_path) as f:
                    content = f.read()
                    if "populated 1" in content:
                        return "active"
                    return "inactive"
        pidfile = f"/run/{name}.pid"
        if os.path.exists(pidfile):
            return "active"
        procs = f"/sys/fs/cgroup/system.slice/{name}.service/cgroup.procs"
        if os.path.exists(procs):
            with open(procs) as f:
                return "active" if f.read().strip() else "inactive"
        return "inactive"
    except Exception:
        return "unknown"


def _service_state_mac(name):
    """Check if a process matching name is running (macOS)."""
    try:
        r = subprocess.run(
            ["pgrep", "-f", name], capture_output=True, text=True, timeout=5
        )
        return "active" if r.returncode == 0 else "inactive"
    except Exception:
        return "unknown"


def _uptime_pretty():
    """Read uptime and format it."""
    if IS_LINUX:
        try:
            with open("/proc/uptime") as f:
                secs = int(float(f.read().split()[0]))
        except Exception:
            return "unknown"
    else:
        try:
            r = subprocess.run(
                ["sysctl", "-n", "kern.boottime"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Output: "{ sec = 1710000000, usec = 0 } ..."
            m = re.search(r"sec\s*=\s*(\d+)", r.stdout)
            if not m:
                return "unknown"
            secs = int(time.time()) - int(m.group(1))
        except Exception:
            return "unknown"
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


def _defcon_from_state(state):
    """Convert state string to defcon level."""
    if state == "defcon2":
        return 2
    if state == "defcon4":
        return 4
    return 5


def _alert_cities():
    """Geocode city names from the latest alert log entry, if any."""
    try:
        alerts = load_log()
        if alerts:
            raw = alerts[0].get("raw")
            if raw and isinstance(raw, dict):
                city_names = raw.get("data", [])
                if isinstance(city_names, str):
                    city_names = [city_names]
                if city_names:
                    return lookup_many(city_names)
    except Exception:
        pass
    return None


def get_sysinfo():
    """Gather service status, uptime, load, temperature, and DEFCON state."""
    info = {}

    services = {}
    svc_names = ["mjpg-alert"]
    for svc in svc_names:
        services[svc] = (
            _service_state_linux(svc) if IS_LINUX else _service_state_mac(svc)
        )
    info["services"] = services
    info["has_camera"] = HAS_CAMERA

    info["uptime"] = _uptime_pretty()

    try:
        if IS_LINUX:
            with open("/proc/loadavg") as f:
                parts = f.read().split()
                info["load"] = str(min(round(float(parts[0]) * 100 / 4), 100)) + "%"
        else:
            load1 = os.getloadavg()[0]
            ncpu = os.cpu_count() or 1
            info["load"] = str(min(round(load1 * 100 / ncpu), 100)) + "%"
    except Exception:
        pass

    if IS_LINUX:
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

    try:
        geo_count = city_count()
        info["geo_size"] = _human_size(os.path.getsize(GEO_DB_PATH))
        info["geo_count"] = geo_count
        info["geo_ok"] = geo_count > 0
    except Exception:
        info["geo_size"] = "N/A"
        info["geo_count"] = 0
        info["geo_ok"] = False

    state = load_state()
    info["defcon"] = _defcon_from_state(state)

    if state in ("defcon2", "defcon4"):
        cities = _alert_cities()
        if cities:
            info["alert_cities"] = cities

    return info


def get_defcon():
    """Lightweight defcon status + alert cities (no sysinfo overhead)."""
    state = load_state()
    result = {"defcon": _defcon_from_state(state)}

    if state in ("defcon2", "defcon4"):
        cities = _alert_cities()
        if cities:
            result["alert_cities"] = cities

    return result
