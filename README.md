# DefconCam

Camera surveillance system running on a Raspberry Pi with a Logitech BRIO webcam. Streams live video with on-screen overlays, automatically switches between day/night modes, monitors Israeli Home Front Command (Pikud HaOref) missile alerts for Gush Dan, and posts snapshots to Twitter/X and Telegram during alerts.

## Features

- **Live MJPEG stream** on port 8080 via mjpg-streamer + ffmpeg
- **Camera presets**: day (manual exposure), night (auto exposure, high gain), indoor
- **Configurable settings**: resolution (640x480 / 720p / 1080p), rotation (0/90/180/270), FPS, brightness, zoom
- **OSD overlay**: DEFCON status, current settings, timestamp (Exo 2 font)
- **Auto day/night switching** based on calculated sunrise/sunset for Tel Aviv (with configurable offset)
- **Pikud HaOref alert monitoring** with fuzzy city matching for Gush Dan
- **DEFCON states**: DEFCON 5 (idle, blue), DEFCON 4 (preemptive, green), DEFCON 2 (incoming missiles, red)
- **Twitter/X integration**: posts camera snapshots on DEFCON 2 alerts
- **Telegram integration**: sends camera snapshots to a Telegram group on DEFCON 2 alerts
- **Manual publish**: publish snapshots to selected targets (Telegram, Twitter) from the web UI
- **Persistent alert state**: survives service restarts
- **Web control panel** on port 8081 with live system monitoring

## Project Structure

    defcon-cam/
    ├── bin/                    # Executable scripts
    │   ├── mjpg-ctl           # Main control script (presets, launcher generation)
    │   ├── mjpg-rotated.sh    # Auto-generated ffmpeg pipeline + mjpg-streamer
    │   ├── mjpg-auto          # Sunrise/sunset day/night auto-switcher (cron)
    │   ├── mjpg-alert         # Alert monitor orchestrator
    │   └── mjpg-web           # Web control panel server (port 8081)
    ├── lib/                   # Shared Python modules
    │   ├── config.py          # Constants, config file parsing
    │   ├── state.py           # DEFCON state persistence and OSD display
    │   ├── oref.py            # Pikud HaOref API client
    │   ├── camera.py          # Snapshot helpers
    │   ├── twitter.py         # Twitter/X posting
    │   ├── telegram.py        # Telegram Bot API posting
    │   └── sysinfo.py         # System info for web UI
    ├── templates/
    │   └── index.html         # Web UI template
    ├── static/
    │   └── fonts/             # Exo 2 font (used in web UI and OSD)
    ├── tests/
    │   └── test_alert.py      # Unit tests (61 tests)
    ├── systemd/               # Service unit files
    └── config/                # Persisted camera settings

## External Config (not in repo)

- `/etc/mjpg-streamer.conf` - Camera settings (mode, rotation, resolution, brightness, fps, zoom)
- `/etc/mjpg-twitter.conf` - Twitter API credentials
- `/etc/mjpg-telegram.conf` - Telegram bot token and chat ID

## Dependencies

### System packages

- `ffmpeg` - video processing and OSD overlay
- `mjpg-streamer` - MJPEG HTTP streaming (compiled with input_file plugin)
- `v4l2-utils` - camera control (v4l2-ctl)
- `curl` - snapshot capture
- `gitleaks` - pre-commit secret scanning

### Python packages

- `tweepy` - Twitter API client

### Hardware

- Raspberry Pi (tested on aarch64)
- Logitech BRIO webcam (or compatible UVC camera at /dev/video0)

## Setup

1. Install dependencies:

       sudo apt install ffmpeg v4l2-utils curl
       pip3 install tweepy

2. Symlink scripts:

       sudo ln -sf ~/defcon-cam/bin/mjpg-ctl /usr/local/bin/mjpg-ctl
       sudo ln -sf ~/defcon-cam/bin/mjpg-rotated.sh /usr/local/bin/mjpg-rotated.sh
       sudo ln -sf ~/defcon-cam/bin/mjpg-auto /usr/local/bin/mjpg-auto
       sudo ln -sf ~/defcon-cam/bin/mjpg-alert /usr/local/bin/mjpg-alert
       sudo ln -sf ~/defcon-cam/bin/mjpg-web /usr/local/bin/mjpg-web

3. Symlink and enable services:

       sudo ln -sf ~/defcon-cam/systemd/*.service /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable mjpg-streamer mjpg-alert mjpg-web

4. Create Twitter config:

       sudo tee /etc/mjpg-twitter.conf << CONF
       API_KEY="your_key"
       API_SECRET="your_secret"
       ACCESS_TOKEN="your_token"
       ACCESS_SECRET="your_token_secret"
       CONF

5. Create Telegram config:

       sudo tee /etc/mjpg-telegram.conf << CONF
       BOT_TOKEN="your_bot_token"
       CHAT_ID="your_chat_id"
       CONF

6. Set up auto day/night cron:

       crontab -e
       # Add: */15 * * * * /usr/local/bin/mjpg-auto --quiet >> /tmp/mjpg-auto.log 2>&1

7. Generate launcher and start:

       mjpg-ctl day

## Usage

    mjpg-ctl day|night|indoor       # Switch mode
    mjpg-ctl rotate 0|90|180|270    # Set rotation
    mjpg-ctl res low|mid|high       # Set resolution
    mjpg-ctl bright 0-100           # Set brightness
    mjpg-ctl fps 5-30               # Set framerate
    mjpg-ctl zoom 100-500           # Set zoom
    mjpg-ctl status                 # Show current settings

## Testing

    python -m unittest discover -s tests -v

## Alert Monitoring

Watches the Pikud HaOref API for alerts matching Gush Dan cities using fuzzy substring matching:

- גבעתיים (Givatayim)
- רמת גן (Ramat Gan)
- תל אביב (Tel Aviv)
- בני ברק (Bnei Brak)

State transitions:

    DEFCON 5 (idle) ──preemptive──> DEFCON 4 (alert incoming)
    DEFCON 5 (idle) ──actual──────> DEFCON 2 (incoming missiles)
    DEFCON 4 ─────────actual──────> DEFCON 2 (incoming missiles)
    DEFCON 2 ─────────ended───────> DEFCON 5 (idle)
    DEFCON 4 ─────────ended───────> DEFCON 5 (idle)

On DEFCON 2, after a 15-second confirmation delay, snapshots are posted to Twitter and Telegram.

State is persisted to `/tmp/mjpg-alert-state` so restarts don't lose DEFCON status.
