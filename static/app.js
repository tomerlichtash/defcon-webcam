/* Alpine.js application for Stars Outside camera control panel */
function app() {
  return {
    /* Reactive state */
    status: '',
    defcon: 'DEFCON 5',
    camOn: false,
    bright: 58,
    zoom: 100,
    pubTelegram: true,
    pubTwitter: false,
    pubStatus: '',
    filters: JSON.parse(localStorage.getItem('filters') || '{"alerts":true,"scans":true,"status":true,"system":true}'),
    eventLog: [],
    eventTotal: 0,
    loadingMore: false,
    noPolling: new URLSearchParams(location.search).get('polling') === 'false',
    webRestarting: false,
    panels: JSON.parse(localStorage.getItem('panels') || '{"publish":false,"image":true,"advanced":false,"alertLog":false,"scanLog":false,"sysinfo":false,"services":false,"debug":false}'),
    streamSrc: '',
    sys: { uptime: 'Uptime: ...', load: '...', temp: '...', dbSize: '...', dbOk: false },
    services: {},
    active: { mode: '', res: '', rotation: '', fps: '' },
    lastRes: '',
    lastFps: '',

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
    get allServicesUp() {
      var svcs = this.services;
      var keys = Object.keys(svcs);
      if (keys.length === 0) return false;
      return keys.every(function(k) { return svcs[k] === 'active'; });
    },
    get servicesRows() {
      var self = this;
      var labels = {'mjpg-alert': 'Alert', 'mjpg-streamer': 'Streamer', 'ffmpeg': 'FFmpeg'};
      var keys = Object.keys(this.services);
      return keys.map(function(name) {
        var state = self.services[name];
        var cls = state === 'active' ? 'up' : 'down';
        var label = labels[name] || name;
        var isDown = state !== 'active';
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
      var host = location.hostname || '10.0.0.238';
      this.streamSrc = 'http://' + host + ':8080/?action=stream';
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
          self.streamSrc = base + '?action=stream&t=' + Date.now();
          self.camOn = true;
          self.status = '';
        })
        .catch(function() {
          if (attempt < 10) {
            setTimeout(function() { self.tryLoadStream(attempt + 1); }, 2000);
          } else {
            self.status = 'Stream unavailable';
          }
        });
    },

    /* Start, stop, or restart the camera service */
    camCtl(action) {
      this.status = 'Camera: ' + action + '...';
      fetch('/api?cmd=camctl+' + action)
        .then(r => r.json())
        .then(d => {
          this.status = d.output || 'Done';
          this.loadSysInfo();
          if (action !== 'stop') this.countdown(3);
        })
        .catch(e => { this.status = 'Error: ' + e; });
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
          if (info.load) self.sys.load = info.load;
          if (info.temp) self.sys.temp = info.temp;
          if (info.db_size) self.sys.dbSize = info.db_size;
          self.sys.dbOk = info.db_ok !== false;

          if (info.services) {
            self.services = info.services;
            var streamerActive = info.services['mjpg-streamer'] === 'active';
            if (!streamerActive) {
              self.camOn = false;
            } else if (!self.camOn) {
              self.status = 'Connecting to stream...';
              self.tryLoadStream(0);
            }
            self.camOn = streamerActive;
          }

          if (info.defcon) {
            self.defcon = info.defcon;
            document.title = 'Stars Outside - ' + info.defcon;
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
      this.status = 'Restarting ' + name + '...';
      this.services[name] = 'restarting';
      fetch('/api?cmd=svcctl+restart+' + encodeURIComponent(name))
        .then(r => r.json())
        .then(d => { this.status = d.output || 'Done'; this.loadSysInfo(); })
        .catch(e => { this.status = 'Error: ' + e; });
    },

    /* Start a stopped service */
    svcStart(name) {
      this.status = 'Starting ' + name + '...';
      fetch('/api?cmd=svcctl+start+' + encodeURIComponent(name))
        .then(r => r.json())
        .then(d => { this.status = d.output || 'Done'; this.loadSysInfo(); })
        .catch(e => { this.status = 'Error: ' + e; });
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
            self.defcon = d.defcon;
            document.title = 'Stars Outside - ' + d.defcon;
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
