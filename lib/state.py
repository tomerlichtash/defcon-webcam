"""DEFCON state management — persistence and OSD display."""

import os
import tempfile

from lib import config

state = "idle"


def save_state(s):
    """Persist DEFCON state to disk (atomic write via temp + replace)."""
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(config.STATE_FILE))
        with os.fdopen(fd, "w") as f:
            f.write(s)
        os.replace(tmp, config.STATE_FILE)
    except Exception as e:
        print(f"save_state error: {e}", flush=True)


def load_state():
    """Load persisted DEFCON state, defaulting to idle."""
    try:
        with open(config.STATE_FILE) as f:
            return f.read().strip()
    except Exception:
        return "idle"


def set_display(idle=" ", alert=" ", defcon4=" "):
    """Write OSD text files. Defaults to space (ffmpeg requires non-empty)."""
    for path, text in [
        (config.IDLE_FILE, idle),
        (config.ALERT_FILE, alert),
        (config.DEFCON4_FILE, defcon4),
    ]:
        try:
            with open(path, "w") as f:
                f.write(text)
        except Exception:
            pass
