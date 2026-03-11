/* Toggle active class on button group to highlight selected option */
function setActive(group, val) {
  var grp = document.querySelector('[data-group="' + group + '"]');
  if (!grp) return;
  grp.querySelectorAll('.btn').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-val') === val);
  });
}

var lastRes = '', lastFps = '';

/* Parse camera status output and sync UI controls to current settings */
function applyStatus(output) {
  var lines = output.split('\n');
  var curRes = '', curFps = '';
  lines.forEach(function(l) {
    var m;
    if (m = l.match(/Mode: (\w+)/)) setActive('mode', m[1]);
    if (m = l.match(/Resolution: (\w+)/)) { setActive('res', m[1]); curRes = m[1]; }
    if (m = l.match(/Rotation: (\d+)/)) setActive('rotation', m[1]);
    if (m = l.match(/Brightness: (\d+)/)) {
      document.getElementById('bright').value = m[1];
      sliderUpdate('bright', m[1]);
    }
    if (m = l.match(/FPS: (\d+)/)) { setActive('fps', m[1]); curFps = m[1]; }
    if (m = l.match(/Zoom: (\d+)/)) {
      document.getElementById('zoom').value = m[1];
      sliderUpdate('zoom', m[1]);
    }
  });
  if (lastRes && lastFps && (curRes !== lastRes || curFps !== lastFps)) {
    countdown(3);
  }
  if (curRes) lastRes = curRes;
  if (curFps) lastFps = curFps;
}

/* Map a command string to its button group and value for UI highlighting */
function cmdToGroup(c) {
  if (c === 'day' || c === 'night' || c === 'indoor') return {group: 'mode', val: c};
  var m;
  if (m = c.match(/^res (\w+)/)) return {group: 'res', val: m[1]};
  if (m = c.match(/^rotate (\d+)/)) return {group: 'rotation', val: m[1]};
  if (m = c.match(/^fps (\d+)/)) return {group: 'fps', val: m[1]};
  return null;
}

/* Send a camera control command and refresh stream if pipeline restarts */
function cmd(c) {
  document.getElementById('status').textContent = 'Applying: ' + c + '...';
  fetch('/api?cmd=' + encodeURIComponent(c))
    .then(function(r) { return r.json(); })
    .then(function(d) {
      document.getElementById('status').textContent = d.output || 'Done';
      var g = cmdToGroup(c);
      if (g) setActive(g.group, g.val);
      if (c.startsWith('res ') || c.startsWith('rotate ') || c.startsWith('fps ') || c === 'day' || c === 'night' || c === 'indoor') {
        countdown(5);
      }
    })
    .catch(function(e) { document.getElementById('status').textContent = 'Error: ' + e; });
}

/* Count down before refreshing the stream after a pipeline restart */
function countdown(sec) {
  var el = document.getElementById('status');
  var left = sec;
  var iv = setInterval(function() {
    el.textContent = 'Refreshing stream in ' + left + 's...';
    left--;
    if (left < 0) {
      clearInterval(iv);
      el.textContent = 'Connecting to stream...';
      tryLoadStream(0);
    }
  }, 1000);
}

/* Retry loading the stream image until it succeeds or max attempts reached */
function tryLoadStream(attempt) {
  var img = document.getElementById('stream');
  var newSrc = img.src.split('?')[0] + '?action=stream&t=' + Date.now();
  var test = new Image();
  test.onload = function() {
    img.src = newSrc;
    img.style.display = 'block';
    document.getElementById('stream-empty').style.display = 'none';
    document.getElementById('status').textContent = '';
  };
  test.onerror = function() {
    if (attempt < 10) {
      setTimeout(function() { tryLoadStream(attempt + 1); }, 2000);
    } else {
      document.getElementById('status').textContent = 'Stream unavailable';
    }
  };
  test.src = newSrc;
}

/* Update the displayed value next to a slider */
function sliderUpdate(id, val) {
  document.getElementById(id + '-val').textContent = val;
}

var camOn = false;

/* Sync camera toggle button text and active state */
function updateCamBtn() {
  var btn = document.getElementById('cam-toggle');
  btn.textContent = camOn ? 'On' : 'Off';
  btn.classList.toggle('active', camOn);
}

/* Start, stop, or restart the camera service */
function camCtl(action) {
  document.getElementById('status').textContent = 'Camera: ' + action + '...';
  fetch('/api?cmd=camctl+' + action)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      document.getElementById('status').textContent = d.output || 'Done';
      loadSysInfo();
      if (action !== 'stop') {
        countdown(3);
      }
    })
    .catch(function(e) { document.getElementById('status').textContent = 'Error: ' + e; });
}

/* Restart the web server and reload the page after a delay */
function restartServer() {
  document.getElementById('status').textContent = 'Restarting web server...';
  fetch('/api?cmd=restart-web').catch(function() {});
  setTimeout(function() { location.reload(); }, 3000);
}

/* Toggle camera on or off based on current state */
function camToggle() {
  camCtl(camOn ? 'stop' : 'start');
}

/* Render a colored status dot for a service */
function dot(active) {
  return '<span class="svc-dot ' + (active ? 'up' : 'down') + '"></span>';
}

/* Poll system info and camera status, update status bar and stream visibility */
function loadSysInfo() {
  fetch('/api?cmd=status')
    .then(function(r) { return r.json(); })
    .then(function(d) { applyStatus(d.output); });
  fetch('/api?cmd=sysinfo')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var info = d.sysinfo || {};
      if (info.uptime) document.getElementById('sb-uptime').textContent = info.uptime;
      if (info.load) {
        var el = document.getElementById('sb-load');
        el.textContent = 'CPU: ' + info.load;
        var pct = parseInt(info.load);
        el.style.color = pct < 60 ? '#4ecca3' : pct < 80 ? '#f0a500' : '#e94560';
      }
      if (info.temp) {
        var el = document.getElementById('sb-temp');
        el.textContent = 'Temp: ' + info.temp;
        var deg = parseFloat(info.temp);
        el.style.color = deg < 60 ? '#4ecca3' : deg < 70 ? '#f0a500' : deg < 80 ? '#e94560' : '#ff0000';
      }

      var svcs = info.services || {};
      var html = '';
      Object.keys(svcs).forEach(function(name) {
        var active = svcs[name] === 'active';
        var sep = (name === 'mjpg-alert') ? 'margin-right:12px; padding-right:12px; border-right:1px solid #555' : 'margin-right:12px';
        html += '<span style="' + sep + '">' + dot(active) + name + '</span>';
        if (name === 'mjpg-streamer') {
          camOn = active;
          updateCamBtn();
          if (!active) {
            document.getElementById('stream').style.display = 'none';
            document.getElementById('stream-empty').style.display = 'flex';
          } else if (document.getElementById('stream').style.display === 'none') {
            document.getElementById('status').textContent = 'Connecting to stream...';
            tryLoadStream(0);
          }
        }
      });
      document.getElementById('sb-services').innerHTML = html || 'Services: ?';

      if (info.defcon) {
        var ds = document.getElementById('defcon-state');
        ds.textContent = info.defcon;
        ds.style.color = info.defcon === 'DEFCON 2' ? '#ff0000' : info.defcon === 'DEFCON 4' ? '#00cc00' : '#4488ff';
        ds.classList.toggle('siren', info.defcon === 'DEFCON 2');
        document.title = 'Stars Outside - ' + info.defcon;
      }
    })
    .catch(function() {});
}

/* Publish a snapshot to selected targets (Telegram, Twitter) */
function publish() {
  var targets = [];
  if (document.getElementById('pub-telegram').checked) targets.push('telegram');
  if (document.getElementById('pub-twitter').checked) targets.push('twitter');
  if (targets.length === 0) {
    document.getElementById('pub-status').textContent = 'Select at least one target';
    return;
  }
  var statusEl = document.getElementById('pub-status');
  statusEl.textContent = 'Publishing to ' + targets.join(', ') + '...';
  fetch('/api/publish', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({targets: targets, caption: 'Stars Outside'})
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var results = d.results || {};
      var parts = [];
      Object.keys(results).forEach(function(k) {
        parts.push(k + ': ' + results[k]);
      });
      statusEl.textContent = parts.join(', ') || 'Done';
    })
    .catch(function(e) { statusEl.textContent = 'Error: ' + e; });
}


/* Toggle alert log visibility */
function toggleLog() {
  var el = document.getElementById('log-entries');
  var toggle = document.getElementById('log-toggle');
  var hidden = el.style.display === 'none';
  el.style.display = hidden ? 'block' : 'none';
  toggle.innerHTML = hidden ? '&#9650;' : '&#9660;';
  if (hidden) loadAlertLog();
}

/* Fetch and render the alert log */
function loadAlertLog() {
  fetch('/api?cmd=alertlog')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var log = d.log || [];
      var el = document.getElementById('log-entries');
      if (log.length === 0) {
        el.innerHTML = '<div style="color:#555">No events recorded</div>';
        return;
      }
      var html = '';
      log.forEach(function(e) {
        var cls = e.defcon === 'DEFCON 2' ? 'd2' : e.defcon === 'DEFCON 4' ? 'd4' : 'd5';
        html += '<div class="log-entry">';
        html += '<span class="log-time">' + e.time + '</span>';
        html += '<span class="log-defcon ' + cls + '">' + e.defcon + '</span>';
        if (e.raw) {
          html += '<div class="log-raw"><details><summary>Raw data</summary>';
          html += '<pre>' + JSON.stringify(e.raw, null, 2) + '</pre>';
          html += '</details></div>';
        }
        html += '</div>';
      });
      el.innerHTML = html;
    })
    .catch(function() {});
}

/* Initial load: fetch camera status and start polling */
fetch('/api?cmd=status')
  .then(function(r) { return r.json(); })
  .then(function(d) { applyStatus(d.output); });

loadSysInfo();
setInterval(loadSysInfo, 5000);

/* Toggle scanner log visibility */
function toggleScanLog() {
  var el = document.getElementById('scan-entries');
  var toggle = document.getElementById('scan-toggle');
  var hidden = el.style.display === 'none';
  el.style.display = hidden ? 'block' : 'none';
  toggle.innerHTML = hidden ? '&#9650;' : '&#9660;';
  if (hidden) loadScanLog();
}

/* Fetch and render the raw API scanner log */
function loadScanLog() {
  fetch('/api?cmd=scanlog')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var log = d.log || [];
      var el = document.getElementById('scan-entries');
      if (log.length === 0) {
        el.innerHTML = '<div style="color:#555">No scans recorded</div>';
        return;
      }
      var html = '';
      log.forEach(function(e) {
        var cls = e.result === 'actual' ? 'scan-alert' : 'scan-clear';
        html += '<div class="log-entry">';
        html += '<span class="log-time">' + e.time + '</span>';
        html += '<span class="scan-source">' + e.source + '</span>';
        html += '<span class="' + cls + '">' + (e.result || 'clear') + '</span>';
        if (e.data) {
          html += '<div class="log-raw"><details><summary>Raw data</summary>';
          html += '<pre>' + e.data + '</pre>';
          html += '</details></div>';
        }
        html += '</div>';
      });
      el.innerHTML = html;
    })
    .catch(function() {});
}
loadAlertLog();
loadScanLog();
