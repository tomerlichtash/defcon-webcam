"""Shared constants and config file parsing."""

import os
import platform
import tempfile

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Load .env file if present
_env_file = os.path.join(_PROJECT_ROOT, ".env")
if os.path.isfile(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
IS_LINUX = platform.system() == "Linux"
HAS_CAMERA = IS_LINUX

_TMP = tempfile.gettempdir()
ALERT_FILE = os.path.join(_TMP, "mjpg-alert.txt")
IDLE_FILE = os.path.join(_TMP, "mjpg-idle.txt")
DEFCON4_FILE = os.path.join(_TMP, "mjpg-clear.txt")
SNAPSHOT_PATH = os.path.join(_TMP, "mjpg-tweet.jpg")
STATE_FILE = os.path.join(_TMP, "mjpg-alert-state")

if IS_LINUX:
    _CONF_DIR = "/etc"
    TWITTER_CONF = "/etc/mjpg-twitter.conf"
    TELEGRAM_CONF = "/etc/mjpg-telegram.conf"
    STREAMER_CONF = "/etc/mjpg-streamer.conf"
else:
    _CONF_DIR = os.path.join(_PROJECT_ROOT, "config")
    TWITTER_CONF = os.path.join(_CONF_DIR, "mjpg-twitter.conf")
    TELEGRAM_CONF = os.path.join(_CONF_DIR, "mjpg-telegram.conf")
    STREAMER_CONF = os.path.join(_CONF_DIR, "mjpg-streamer.conf")


def _parse_conf(path):
    """Parse a KEY="value" config file into a dict."""
    cfg = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"')
    except FileNotFoundError:
        pass  # expected — config files are optional
    except Exception as e:
        print(f"config parse error ({path}): {e}", flush=True)
    return cfg


def load_admin_config():
    """Load admin auth configuration."""
    return {
        "descope_project_id": os.environ.get("DESCOPE_PROJECT_ID", ""),
    }


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
    return _parse_conf(TWITTER_CONF)


def load_telegram_keys():
    """Parse Telegram bot keys from config file."""
    return _parse_conf(TELEGRAM_CONF)
