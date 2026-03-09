#!/bin/bash
# Ensure OSD text files exist
for f in /tmp/mjpg-idle.txt /tmp/mjpg-alert.txt /tmp/mjpg-clear.txt; do [ -f "$f" ] || echo " " > "$f"; done
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

v4l2-ctl --device=/dev/video0 --set-ctrl=auto_exposure=1 --set-ctrl=exposure_time_absolute=3 --set-ctrl=gain=0 --set-ctrl=brightness=147

ffmpeg -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 24 \
  -i /dev/video0 \
  -vf "drawtext=text='day | mid 1280x720 | rot 0 | 24fps | bright 58 | next night 16.54':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf:fontsize=12:fontcolor=white:borderw=2:bordercolor=black:x=10:y=h-30,drawtext=textfile=/tmp/mjpg-idle.txt:reload=1:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf:fontsize=28:fontcolor=0x4488FF:borderw=2:bordercolor=black:x=10:y=10,drawtext=textfile=/tmp/mjpg-alert.txt:reload=1:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf:fontsize=28:fontcolor=red:borderw=2:bordercolor=black:x=10:y=10,drawtext=textfile=/tmp/mjpg-clear.txt:reload=1:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf:fontsize=28:fontcolor=green:borderw=2:bordercolor=black:x=10:y=10,drawtext=text='%{localtime}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf:fontsize=14:fontcolor=white:borderw=1:bordercolor=black:x=w-tw-10:y=h-30" \
  -update 1 -atomic_writing 1 -q:v 3 \
  "$TMPDIR/snap.jpg" &
FFPID=$!

sleep 2

/usr/local/bin/mjpg_streamer \
  -i "input_file.so -f $TMPDIR -n snap.jpg -d 0" \
  -o "output_http.so -p 8080 -w /usr/local/share/mjpg-streamer/www"

kill $FFPID 2>/dev/null
