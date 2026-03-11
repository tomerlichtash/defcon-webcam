/* Alpine.js application for Stars Outside camera control panel */
function app() {
  return {
    /* Reactive state */
    status: '',
    defcon: 'DEFCON 5',
    defconTime: '',
    camOn: localStorage.getItem('camOn') === 'true',
    camHover: false,
    camLoading: false,
    bright: 58,
    zoom: 100,
    pubTelegram: localStorage.getItem('pubTelegram') !== 'false',
    pubTwitter: localStorage.getItem('pubTwitter') === 'true',
    pubStatus: '',
    filters: JSON.parse(localStorage.getItem('filters') || '{"alerts":true,"scans":true,"status":true,"system":true}'),
    eventLog: [],
    eventTotal: 0,
    loadingMore: false,
    noPolling: new URLSearchParams(location.search).get('polling') === 'false',
    webRestarting: false,
    panels: Object.assign({"publish":false,"image":true,"advanced":false,"alertLog":false,"scanLog":false,"sysinfo":false,"services":false,"debug":false,"eventLog":true}, JSON.parse(localStorage.getItem('panels') || '{}')),
    sys: { uptime: 'Uptime: ...', load: '...', temp: '...', dbSize: '...', dbOk: false },
    cpuHistory: [],
    tempHistory: [],
    services: {},
    active: { mode: '', res: '', rotation: '', fps: '', grayscale: localStorage.getItem('filterGrayscale') === 'true', invert: localStorage.getItem('filterInvert') === 'true' },
    lastRes: '',
    lastFps: '',

    /* Sparkline SVG generator */
    _sparkId: 0,
    sparkline(data, color, max) {
      if (data.length < 2) return '';
      var w = 80, h = 24, pad = 2;
      var id = 'sp' + (this._sparkId++);
      var step = (w - pad * 2) / (data.length - 1);
      var pts = data.map(function(v, i) {
        return { x: pad + i * step, y: pad + (h - pad * 2) - (Math.min(v, max) / max) * (h - pad * 2) };
      });
      /* Smooth cubic bezier path */
      var d = 'M' + pts[0].x.toFixed(1) + ',' + pts[0].y.toFixed(1);
      for (var i = 1; i < pts.length; i++) {
        var cx = (pts[i - 1].x + pts[i].x) / 2;
        d += ' C' + cx.toFixed(1) + ',' + pts[i - 1].y.toFixed(1) + ' ' + cx.toFixed(1) + ',' + pts[i].y.toFixed(1) + ' ' + pts[i].x.toFixed(1) + ',' + pts[i].y.toFixed(1);
      }
      /* Area fill path */
      var areaD = d + ' L' + pts[pts.length - 1].x.toFixed(1) + ',' + (h - pad) + ' L' + pts[0].x.toFixed(1) + ',' + (h - pad) + ' Z';
      var last = pts[pts.length - 1];
      return '<svg width="' + w + '" height="' + h + '" style="margin-right:6px">'
        + '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="' + color + '" stop-opacity="0.3"/><stop offset="100%" stop-color="' + color + '" stop-opacity="0.02"/></linearGradient></defs>'
        + '<path d="' + areaD + '" fill="url(#' + id + ')"/>'
        + '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        + '<circle cx="' + last.x.toFixed(1) + '" cy="' + last.y.toFixed(1) + '" r="2" fill="' + color + '"/>'
        + '</svg>';
    },
    get cpuSpark() { return this.sparkline(this.cpuHistory, this.cpuColor, 100); },
    get tempSpark() { return this.sparkline(this.tempHistory, this.tempColor, 100); },

    /* Computed colors */
    get cpuColor() {
      var pct = parseInt(this.sys.load);
      return pct < 60 ? '#4ecca3' : pct < 80 ? '#f0a500' : '#e94560';
    },
    get tempColor() {
      var deg = parseFloat(this.sys.temp);
      return deg < 60 ? '#4ecca3' : deg < 70 ? '#f0a500' : deg < 80 ? '#e94560' : '#ff0000';
    },
    get defconColor() {
      return this.defcon === 'DEFCON 2' ? '#ff0000' : this.defcon === 'DEFCON 4' ? '#00cc00' : '#4488ff';
    },
    get defconLabel() {
      if (this.defcon === 'DEFCON 2') return 'INCOMING MISSILES - ' + this.defconTime + ' [DEFCON 2]';
      if (this.defcon === 'DEFCON 4') return 'INCOMING ALERT - ' + this.defconTime + ' [DEFCON 4]';
      return 'CLEAR SKIES [DEFCON 5]';
    },
    get osdLine() {
      var parts = [];
      if (this.active.mode) parts.push(this.active.mode);
      if (this.active.res) parts.push(this.active.res);
      if (this.active.fps) parts.push(this.active.fps + 'fps');
      if (this.active.rotation && this.active.rotation !== '0') parts.push('rot ' + this.active.rotation);
      return parts.join(' | ');
    },
    get allServicesUp() {
      var svcs = this.services;
      var keys = Object.keys(svcs);
      if (keys.length === 0) return false;
      return keys.every(function(k) { return svcs[k] === 'active'; });
    },
    get servicesRows() {
      var self = this;
      var labels = {'mjpg-alert': 'Alert', 'mjpg-streamer': 'Streamer'};
      var keys = Object.keys(this.services);
      return keys.map(function(name) {
        var state = self.services[name];
        var isStarting = state === 'activating' || state === 'restarting';
        var isStopping = state === 'deactivating';
        var isTransitioning = isStarting || isStopping;
        var cls = isTransitioning ? 'warn' : state === 'active' ? 'up' : 'down';
        var suffix = isStarting ? ' <small style="opacity:0.6">(starting)</small>' : isStopping ? ' <small style="opacity:0.6">(stopping)</small>' : '';
        var label = (labels[name] || name) + suffix;
        var isDown = state !== 'active' && !isTransitioning;
        var btnClass = isDown ? 'outline btn-primary svc-restart-btn' : 'outline btn-danger svc-restart-btn';
        var btnLabel = isDown ? 'Start' : 'Restart';
        var action = isDown ? 'svcStart' : 'svcRestart';
        return '<div class="svc-row"><span class="svc-dot ' + cls + '"></span><span class="sysinfo-label">' + label + '</span>'
             + '<button class="' + btnClass + '" onclick="document.querySelector(\'[x-data]\')._x_dataStack[0].' + action + '(\'' + name + '\')">' + btnLabel + '</button></div>';
      }).join('');
    },

    get aggLog() {
      var self = this;
      var typeMap = { alerts: 'alert', scans: 'scan', status: 'status', system: 'system' };
      var activeTypes = {};
      Object.keys(self.filters).forEach(function(k) {
        if (self.filters[k]) activeTypes[typeMap[k]] = true;
      });
      return self.eventLog.filter(function(e) { return activeTypes[e._type]; }).slice(0, 200);
    },

    /* Initialize: set stream src, fetch status, start polling */
    init() {
      var self = this;
      this.$watch('panels', function(val) {
        localStorage.setItem('panels', JSON.stringify(val));
      }, { deep: true });
      this.$watch('filters', function(val) {
        localStorage.setItem('filters', JSON.stringify(val));
      }, { deep: true });
      this.$watch('pubTelegram', function(val) { localStorage.setItem('pubTelegram', val); });
      this.$watch('pubTwitter', function(val) { localStorage.setItem('pubTwitter', val); });
      this.$watch('camOn', function(val) {
        var el = document.getElementById('stream');
        if (el) el.style.display = val ? '' : 'none';
        self.camLoading = false;
        localStorage.setItem('camOn', val);
      });
      var host = location.hostname || '10.0.0.238';
      var streamEl = document.getElementById('stream');
      if (this.camOn && streamEl) {
        streamEl.src = 'http://' + host + ':8080/?action=stream';
        streamEl.style.display = '';
      }
      this.applyFilters();
      var noPolling = new URLSearchParams(location.search).get('polling') === 'false';
      this.fetchStatus();
      this.loadSysInfo();
      this.loadEventLog();
      if (!noPolling) {
        setInterval(() => {
          this.loadSysInfo();
          this.loadEventLog();
        }, 5000);
      }
    },

    /* Apply CSS filters to stream image */
    applyFilters() {
      var el = document.getElementById('stream');
      if (!el) return;
      var f = [];
      if (this.active.grayscale) f.push('grayscale(1)');
      if (this.active.invert) f.push('invert(1)');
      el.style.filter = f.length ? f.join(' ') : '';
    },

    toggleGrayscale() {
      this.active.grayscale = !this.active.grayscale;
      localStorage.setItem('filterGrayscale', this.active.grayscale);
      this.applyFilters();
    },

    toggleInvert() {
      this.active.invert = !this.active.invert;
      localStorage.setItem('filterInvert', this.active.invert);
      this.applyFilters();
    },

    /* Parse camera status output and sync active button states */
    applyStatus(output) {
      var self = this;
      var curRes = '', curFps = '';
      output.split('\n').forEach(function(l) {
        var m;
        if (m = l.match(/Mode: (\w+)/)) self.active.mode = m[1];
        if (m = l.match(/Resolution: (\w+)/)) { self.active.res = m[1]; curRes = m[1]; }
        if (m = l.match(/Rotation: (\d+)/)) self.active.rotation = m[1];
        if (m = l.match(/Brightness: (\d+)/)) self.bright = parseInt(m[1]);
        if (m = l.match(/FPS: (\d+)/)) { self.active.fps = m[1]; curFps = m[1]; }
        if (m = l.match(/Zoom: (\d+)/)) self.zoom = parseInt(m[1]);
      });
      if (self.lastRes && self.lastFps && (curRes !== self.lastRes || curFps !== self.lastFps)) {
        self.countdown(3);
      }
      if (curRes) self.lastRes = curRes;
      if (curFps) self.lastFps = curFps;
    },

    /* Fetch initial camera status */
    fetchStatus() {
      fetch('/api?cmd=status')
        .then(r => r.json())
        .then(d => this.applyStatus(d.output));
    },

    /* Send a camera control command */
    cmd(c) {
      this.status = 'Applying: ' + c + '...';
      fetch('/api?cmd=' + encodeURIComponent(c))
        .then(r => r.json())
        .then(d => {
          this.status = d.output || 'Done';
          /* Update active state immediately */
          if (['day','night','indoor'].includes(c)) this.active.mode = c;
          var m;
          if (m = c.match(/^res (\w+)/)) this.active.res = m[1];
          if (m = c.match(/^rotate (\d+)/)) this.active.rotation = m[1];
          if (m = c.match(/^fps (\d+)/)) this.active.fps = m[1];
          /* Trigger stream refresh for pipeline-restarting commands */
          if (c.startsWith('res ') || c.startsWith('rotate ') || c.startsWith('fps ')
              || c === 'day' || c === 'night' || c === 'indoor') {
            this.countdown(5);
          }
        })
        .catch(e => { this.status = 'Error: ' + e; });
    },

    /* Count down before refreshing the stream */
    countdown(sec) {
      var self = this;
      var left = sec;
      var iv = setInterval(function() {
        self.status = 'Refreshing stream in ' + left + 's...';
        left--;
        if (left < 0) {
          clearInterval(iv);
          self.status = 'Connecting to stream...';
          self.tryLoadStream(0);
        }
      }, 1000);
    },

    /* Retry loading the stream image */
    tryLoadStream(attempt) {
      var self = this;
      var host = location.hostname || '10.0.0.238';
      var base = 'http://' + host + ':8080/';
      fetch(base + '?action=snapshot&t=' + Date.now(), { mode: 'no-cors' })
        .then(function() {
          var streamEl = document.getElementById('stream');
          if (streamEl) streamEl.src = base + '?action=stream&t=' + Date.now();
          self.camOn = true;
          self.camLoading = false;
          self.status = '';
        })
        .catch(function() {
          if (attempt < 10) {
            setTimeout(function() { self.tryLoadStream(attempt + 1); }, 2000);
          } else {
            self.status = 'Stream unavailable';
            self.camLoading = false;
          }
        });
    },

    /* Start, stop, or restart the camera service */
    camCtl(action) {
      this.camLoading = true;
      this.status = 'Camera: ' + action + '...';
      if (action === 'start' || action === 'restart') {
        this.services['mjpg-streamer'] = 'activating';

      } else if (action === 'stop') {
        this.services['mjpg-streamer'] = 'deactivating';

      }
      var self = this;
      fetch('/api?cmd=camctl+' + action)
        .then(r => r.json())
        .then(d => {
          self.status = d.output || 'Done';
          if (action !== 'stop') self.countdown(3);
          /* For stop, clear loading after sysinfo confirms */
          /* Delay sysinfo poll to let services fully start */
          setTimeout(function() { self.loadSysInfo(); }, 3000);
        })
        .catch(e => { self.status = 'Error: ' + e; self.camLoading = false; });
    },

    /* Restart the web server and reload */
    restartServer() {
      this.status = 'Restarting web server...';
      this.webRestarting = true;
      fetch('/api?cmd=restart-web').catch(function() {});
      setTimeout(function() { location.reload(); }, 3000);
    },

    /* Poll system info and update status bar */
    loadSysInfo() {
      var self = this;
      fetch('/api?cmd=status')
        .then(r => r.json())
        .then(d => self.applyStatus(d.output));

      fetch('/api?cmd=sysinfo')
        .then(r => r.json())
        .then(d => {
          var info = d.sysinfo || {};
          if (info.uptime) self.sys.uptime = info.uptime.replace(/^up\s+/, '');
          if (info.load) {
            self.sys.load = info.load;
            self.cpuHistory.push(parseInt(info.load));
            if (self.cpuHistory.length > 30) self.cpuHistory.shift();
          }
          if (info.temp) {
            self.sys.temp = info.temp;
            self.tempHistory.push(parseFloat(info.temp));
            if (self.tempHistory.length > 30) self.tempHistory.shift();
          }
          if (info.db_size) self.sys.dbSize = info.db_size;
          self.sys.dbOk = info.db_ok !== false;

          if (info.services) {
            self.services = info.services;
            var streamerActive = info.services['mjpg-streamer'] === 'active';
            if (streamerActive !== self.camOn) {
              if (!streamerActive) {
                self.camOn = false;
              } else {
                self.status = 'Connecting to stream...';
                self.tryLoadStream(0);
              }
            }
          }

          if (info.defcon) {
            if (info.defcon !== self.defcon && info.defcon !== 'DEFCON 5') {
              self.defconTime = new Date().toLocaleTimeString('en-GB', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
            }
            self.defcon = info.defcon;
            document.title = 'Stars Outside - ' + self.defconLabel;
          }
        })
        .catch(function() {});
    },

    /* Publish a snapshot to selected targets */
    publish() {
      var targets = [];
      if (this.pubTelegram) targets.push('telegram');
      if (this.pubTwitter) targets.push('twitter');
      if (targets.length === 0) {
        this.pubStatus = 'Select at least one target';
        return;
      }
      this.pubStatus = 'Publishing to ' + targets.join(', ') + '...';
      fetch('/api/publish', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({targets: targets, caption: 'Stars Outside'})
      })
        .then(r => r.json())
        .then(d => {
          var results = d.results || {};
          this.pubStatus = Object.keys(results).map(k => k + ': ' + results[k]).join(', ') || 'Done';
        })
        .catch(e => { this.pubStatus = 'Error: ' + e; });
    },

    /* Restart a systemd service */
    svcRestart(name) {
      var self = this;
      self.status = 'Restarting ' + name + '...';
      self.services[name] = 'restarting';
      fetch('/api?cmd=svcctl+restart+' + encodeURIComponent(name))
        .then(r => r.json())
        .then(d => { self.status = d.output || 'Done'; setTimeout(function() { self.loadSysInfo(); }, 3000); })
        .catch(e => { self.status = 'Error: ' + e; });
    },

    /* Start a stopped service */
    svcStart(name) {
      var self = this;
      self.status = 'Starting ' + name + '...';
      self.services[name] = 'activating';
      fetch('/api?cmd=svcctl+start+' + encodeURIComponent(name))
        .then(r => r.json())
        .then(d => { self.status = d.output || 'Done'; setTimeout(function() { self.loadSysInfo(); }, 3000); })
        .catch(e => { self.status = 'Error: ' + e; });
    },

    /* Reset event log database */
    dbReset() {
      if (!confirm('Clear all event log history?')) return;
      this.status = 'Resetting event log...';
      var self = this;
      fetch('/api?cmd=dbreset')
        .then(function(r) { return r.json(); })
        .then(function(d) {
          self.status = d.output || 'Done';
          self.eventLog = [];
          self.eventTotal = 0;
          self.loadEventLog();
        })
        .catch(function(e) { self.status = 'Error: ' + e; });
    },

    /* Fetch unified event log from server */
    loadEventLog() {
      var self = this;
      /* Incremental: if we have events, fetch only newer ones */
      var url = '/api?cmd=eventlog';
      if (self.eventLog.length > 0) {
        url += '&since=' + encodeURIComponent(self.eventLog[0].time);
      }
      fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(d) {
          var newEvents = d.log || [];
          self.eventTotal = d.total || 0;
          if (d.defcon) {
            if (d.defcon !== self.defcon && d.defcon !== 'DEFCON 5') {
              self.defconTime = new Date().toLocaleTimeString('en-GB', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
            }
            self.defcon = d.defcon;
            document.title = 'Stars Outside - ' + self.defconLabel;
          }
          if (self.eventLog.length === 0) {
            /* Initial load */
            self.eventLog = newEvents;
          } else if (newEvents.length > 0) {
            /* Prepend new events (they come newest-first) */
            self.eventLog = newEvents.concat(self.eventLog);
          }
        })
        .catch(function() {});
    },

    /* Load older events for pagination */
    loadMore() {
      var self = this;
      self.loadingMore = true;
      var offset = self.eventLog.length;
      fetch('/api?cmd=eventlog&offset=' + offset)
        .then(function(r) { return r.json(); })
        .then(function(d) {
          var older = d.log || [];
          self.eventTotal = d.total || 0;
          self.eventLog = self.eventLog.concat(older);
          self.loadingMore = false;
        })
        .catch(function() { self.loadingMore = false; });
    }
  };
}
