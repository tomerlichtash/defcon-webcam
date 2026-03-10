"""Shared constants and config file parsing."""

# File paths
ALERT_FILE = "/tmp/mjpg-alert.txt"
IDLE_FILE = "/tmp/mjpg-idle.txt"
DEFCON4_FILE = "/tmp/mjpg-clear.txt"
SNAPSHOT_PATH = "/tmp/mjpg-tweet.jpg"
TWITTER_CONF = "/etc/mjpg-twitter.conf"
STREAMER_CONF = "/etc/mjpg-streamer.conf"
STATE_FILE = "/tmp/mjpg-alert-state"
CHECK_INTERVAL = 3

# Alert matching
WATCH_TERMS = ["גבעתיים", "רמת גן", "תל אביב", "בני ברק"]
TITLE_PREEMPTIVE = "בדקות הקרובות צפויות להתקבל התרעות באזורך"
TITLE_ACTUAL = "ירי רקטות וטילים"
TITLE_ENDED = "האירוע הסתיים"


def get_current_mode():
    """Read current camera mode from streamer config."""
    try:
        with open(STREAMER_CONF) as f:
            for line in f:
                if line.startswith("MODE="):
                    return line.strip().split("=")[1].strip('"')
    except Exception:
        pass
    return "day"


def load_twitter_keys():
    """Parse Twitter API keys from config file."""
    keys = {}
    try:
        with open(TWITTER_CONF) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip().strip('"')
    except Exception as e:
        print("Failed to load Twitter config: " + str(e), flush=True)
    return keys
