"""DEFCON state management — persistence and OSD display."""

from lib import config

state = "idle"


def save_state(s):
    """Persist DEFCON state to disk."""
    try:
        with open(config.STATE_FILE, "w") as f:
            f.write(s)
    except Exception:
        pass


def load_state():
    """Load persisted DEFCON state, defaulting to idle."""
    try:
        with open(config.STATE_FILE) as f:
            return f.read().strip()
    except Exception:
        return "idle"


def set_display(idle=" ", alert=" ", defcon4=" "):
    """Write OSD text files. Defaults to space (ffmpeg requires non-empty)."""
    for path, text in [(config.IDLE_FILE, idle), (config.ALERT_FILE, alert), (config.DEFCON4_FILE, defcon4)]:
        try:
            with open(path, "w") as f:
                f.write(text)
        except Exception:
            pass
