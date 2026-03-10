# AGENTS.md

Instructions for AI coding agents working on this project.

## Project Overview

DefconCam is a Raspberry Pi camera surveillance system with missile alert monitoring. It runs on a Pi (tomer@10.0.0.238, hostname "pi-hole") with a Logitech BRIO webcam, streaming via mjpg-streamer + ffmpeg with OSD overlays.

## Architecture

    bin/mjpg-ctl (bash, control script)
      ├── generates → mjpg-rotated.sh (auto-generated launcher, gitignored)
      ├── calls → v4l2-ctl (camera hardware controls)
      └── restarts → mjpg-streamer.service

    bin/mjpg-alert (Python, alert monitor orchestrator)
      ├── imports → lib/oref (Pikud HaOref API client)
      ├── imports → lib/state (DEFCON state + OSD display)
      ├── imports → lib/twitter (tweet posting)
      ├── imports → lib/telegram (Telegram posting)
      └── imports → lib/config (shared constants)

    bin/mjpg-auto (Python, cron every 15min)
      ├── imports → lib/config (get_current_mode)
      └── calls → mjpg-ctl day/night

    bin/mjpg-web (Python HTTP server, port 8081)
      ├── imports → lib/sysinfo (system status)
      ├── imports → lib/camera (take_snapshot for publish)
      ├── imports → lib/telegram (send_telegram for publish)
      ├── imports → lib/twitter (send_tweet for publish)
      └── calls → mjpg-ctl via subprocess (camera controls)

## Module Structure (lib/)

- `config.py` — Shared constants, config file parsers (Twitter, Telegram, streamer)
- `state.py` — DEFCON state persistence and OSD text file management
- `oref.py` — Pikud HaOref API client with cache busting, UTF-16-LE handling, history fallback
- `camera.py` — `take_snapshot()` (simple grab) and `take_alert_snapshot(mode)` (with night exposure)
- `twitter.py` — `send_tweet(text)` (uses existing snapshot) and `post_tweet(text, mode)` (takes snapshot + posts)
- `telegram.py` — `send_telegram(text)` (uses existing snapshot) and `post_telegram(text, mode)` (takes snapshot + posts)
- `sysinfo.py` — System info gathering (services, uptime, CPU%, temp, DEFCON state) for web UI

### Import Pattern
Scripts in `bin/` use `os.path.realpath(__file__)` to resolve symlinks back to the repo, then `sys.path.insert(0, _root)` to enable `from lib import ...`.

**Critical**: Modules that need testable config paths must use `from lib import config` and access `config.CONSTANT` at call time — NOT `from lib.config import CONSTANT` which captures the value at import time and breaks test overrides.

All scripts in `bin/` are symlinked to `/usr/local/bin/`. Do not edit files in `/usr/local/bin/` directly — edit the repo source.

## Critical Rules

### Publishing Policy
- **Automatic** (alert-triggered): On DEFCON 2, after a 15-second confirmation delay, post to both Twitter and Telegram via `post_tweet()`/`post_telegram()` which use `take_alert_snapshot()`.
- **Manual** (web UI publish button): Takes a simple snapshot via `take_snapshot()` (no exposure changes) then calls `send_telegram()`/`send_tweet()`. Does not disrupt the live stream.
- Never tweet/post on DEFCON 5 or DEFCON 4 automatically.

### State Machine
- States: idle (DEFCON 5) → preemptive (DEFCON 4) → actual (DEFCON 2) → idle
- DEFCON 4: preemptive alert received for watched cities
- DEFCON 2: actual missile alert. Can transition from idle or DEFCON 4.
- Only transition back to idle on explicit "האירוע הסתיים" from the API. Empty API response does NOT clear the alert.
- State is persisted to `/tmp/mjpg-alert-state`. Always read it on startup to survive restarts.

### OSD Text Files
- Files: `/tmp/mjpg-idle.txt`, `/tmp/mjpg-alert.txt`, `/tmp/mjpg-clear.txt`, `/tmp/mjpg-osd.txt`
- These MUST exist before ffmpeg starts or it will crash.
- Write a space `" "` to clear a file, never write empty string `""` — ffmpeg's textfile reload ignores empty files.
- `mjpg-rotated.sh` creates these on startup as a safety net.

### ffmpeg Filter Gotchas
- Uses `textfile` with `reload=1` for dynamic OSD content — colons in the text file content are fine.
- Static `text=` values in the filter chain (like `%{localtime}`) DO need colon escaping.
- Always use `-atomic_writing 1` to prevent race conditions between ffmpeg writing and mjpg-streamer reading.
- Font: Exo 2 Bold from `static/fonts/Exo2-Bold.ttf` (used in both OSD and web UI).

### mjpg-rotated.sh is Auto-Generated
- `mjpg-ctl`'s `apply()` function generates `bin/mjpg-rotated.sh`. Do not hand-edit it.
- It is gitignored. Any fix must go into `mjpg-ctl`'s `apply()` function or it will be overwritten.
- Changes to the ffmpeg filter chain, v4l2 settings, or OSD layout must be made in `mjpg-ctl`.

### Service Ordering
- `mjpg-alert.service` must start before `mjpg-streamer.service` (configured via `After=` in systemd unit).
- This ensures OSD text files exist before ffmpeg needs them.

### Camera Hardware (Logitech BRIO)
- Device: `/dev/video0`
- Day mode: `auto_exposure=1` (manual), `exposure_time_absolute=3` (minimum), `gain=0`, `backlight_compensation=1`, `contrast=80`
- Night mode: `auto_exposure=3` (auto), `gain=255`
- Indoor mode: `auto_exposure=3` (auto), `gain=128`
- Focus: `focus_automatic_continuous=1` (auto). Refocus by toggling off/on with 1s delay.
- Rotation: only 0/90/180/270 via ffmpeg transpose.
- Sweet spot: 720p@24fps. 1080p@30fps overloads the Pi CPU (~240%).

## Secrets
- Twitter API keys: `/etc/mjpg-twitter.conf` (not in repo)
- Telegram bot keys: `/etc/mjpg-telegram.conf` (not in repo)
- Format: `KEY="value"` (one per line, `#` comments supported)
- Pre-commit hook runs gitleaks to prevent accidental secret commits.
- Never hardcode credentials. Always read from config files at runtime.

## Testing

    python -m unittest discover -s tests -v

- Tests mock `tweepy` via `sys.modules["tweepy"] = MagicMock()` before imports.
- Tests override config paths (e.g., `config.STATE_FILE = tmpfile`) — this only works because modules use call-time access (`config.X`) not import-time capture.
- Mock `builtins.print` when testing functions that print error messages to avoid noisy output.

## File Locations

### In Repo (~/defcon-cam/)
- `bin/` — executable scripts (mjpg-ctl, mjpg-alert, mjpg-auto, mjpg-web)
- `lib/` — shared Python modules
- `templates/index.html` — web UI template
- `static/fonts/` — Exo 2 font files
- `tests/test_alert.py` — unit tests
- `config/mjpg-streamer.conf` — persisted camera settings
- `systemd/*.service` — systemd unit files

### External (not in repo)
- `/etc/mjpg-twitter.conf` — Twitter API credentials
- `/etc/mjpg-telegram.conf` — Telegram bot token and chat ID
- `/etc/mjpg-streamer.conf` — camera mode/settings (symlinked from config/)
- `/etc/mjpg-next-switch` — next day/night switch time
- `/tmp/mjpg-alert-state` — persisted DEFCON state
- `/tmp/mjpg-*.txt` — OSD text files
