/* System info panel module — service control, db reset */
var SysinfoModule = {
  state: {
    sys: {
      uptime: "Uptime: ...",
      load: "...",
      temp: "...",
      dbSize: "...",
      dbOk: false,
      geoCount: "...",
      geoOk: false,
    },
    cpuHistory: [],
    tempHistory: [],
    services: {},
    _sparkId: 0,
  },

  /* Sparkline SVG generator — uses currentColor (inherited from CSS) */
  sparkline(data, max) {
    if (data.length < 2) return "";
    const w = 80,
      h = 24,
      pad = 2;
    const id = "sp" + this._sparkId++;
    const step = (w - pad * 2) / (data.length - 1);
    const pts = data.map((v, i) => ({
      x: pad + i * step,
      y: pad + (h - pad * 2) - (Math.min(v, max) / max) * (h - pad * 2),
    }));
    let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) {
      const cx = (pts[i - 1].x + pts[i].x) / 2;
      d += ` C${cx.toFixed(1)},${pts[i - 1].y.toFixed(1)} ${cx.toFixed(1)},${pts[i].y.toFixed(1)} ${pts[i].x.toFixed(1)},${pts[i].y.toFixed(1)}`;
    }
    const areaD = `${d} L${pts[pts.length - 1].x.toFixed(1)},${h - pad} L${pts[0].x.toFixed(1)},${h - pad} Z`;
    const last = pts[pts.length - 1];
    return (
      `<svg width="${w}" height="${h}" style="margin-right:6px">` +
      `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="currentColor" stop-opacity="0.3"/><stop offset="100%" stop-color="currentColor" stop-opacity="0.02"/></linearGradient></defs>` +
      `<path d="${areaD}" fill="url(#${id})"/>` +
      `<path d="${d}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>` +
      `<circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="2" fill="currentColor"/>` +
      "</svg>"
    );
  },
  get cpuSpark() {
    return this.sparkline(this.cpuHistory, 100);
  },
  get tempSpark() {
    return this.sparkline(this.tempHistory, 100);
  },
  get cpuLevel() {
    const pct = parseInt(this.sys.load);
    return pct < 60 ? "ok" : pct < 80 ? "warn" : "danger";
  },
  get tempLevel() {
    const deg = parseFloat(this.sys.temp);
    return deg < 60
      ? "ok"
      : deg < 70
        ? "warn"
        : deg < 80
          ? "danger"
          : "critical";
  },
  get allServicesUp() {
    const svcs = this.services;
    const keys = Object.keys(svcs);
    if (keys.length === 0) return false;
    return keys.every((k) => svcs[k] === "active");
  },
  _escHtml(s) {
    const el = document.createElement("span");
    el.textContent = s;
    return el.innerHTML;
  },
  get servicesRows() {
    const labels = { "mjpg-alert": "Alert", "mjpg-web": "Web" };
    const keys = Object.keys(this.services);
    return keys
      .map((name) => {
        const state = this.services[name];
        const isStarting = state === "activating" || state === "restarting";
        const isStopping = state === "deactivating";
        const isTransitioning = isStarting || isStopping;
        const cls = isTransitioning
          ? "warn"
          : state === "active"
            ? "up"
            : "down";
        const suffix = isStarting
          ? ' <small style="opacity:0.6">(starting)</small>'
          : isStopping
            ? ' <small style="opacity:0.6">(stopping)</small>'
            : "";
        const safeName = this._escHtml(name);
        const label = (labels[name] || safeName) + suffix;
        const isDown = state !== "active" && !isTransitioning;
        const btnClass = isDown
          ? "outline btn-primary svc-restart-btn"
          : "outline btn-danger svc-restart-btn";
        const btnLabel = isDown ? "Start" : "Restart";
        const action = isDown ? "svcStart" : "svcRestart";
        const attrName = safeName.replace(/'/g, "&#39;");
        return (
          `<div class="svc-row"><span class="svc-dot ${cls}"></span><span class="sysinfo-label">${label}</span>` +
          `<button class="${btnClass}" onclick="document.querySelector('[x-data]')._x_dataStack[0].${action}('${attrName}')">${btnLabel}</button></div>`
        );
      })
      .join("");
  },

  loadSysInfo() {
    fetch("/api?cmd=sysinfo")
      .then((r) => r.json())
      .then((d) => {
        const info = d.sysinfo || {};
        if (info.uptime) this.sys.uptime = info.uptime.replace(/^up\s+/, "");
        if (info.load) {
          this.sys.load = info.load;
          this.cpuHistory.push(parseInt(info.load));
          if (this.cpuHistory.length > 30) this.cpuHistory.shift();
        }
        if (info.temp) {
          this.sys.temp = info.temp;
          this.tempHistory.push(parseFloat(info.temp));
          if (this.tempHistory.length > 30) this.tempHistory.shift();
        }
        if (info.db_size) this.sys.dbSize = info.db_size;
        this.sys.dbOk = info.db_ok !== false;
        if (info.geo_count !== undefined) this.sys.geoCount = info.geo_count;
        this.sys.geoOk = info.geo_ok !== false;
        if (info.has_camera !== undefined) this.hasCamera = info.has_camera;
        if (info.services) this.services = info.services;
        this._applyDefcon(info.defcon);
        this._applyAlertCities(info.defcon, info.alert_cities);
      })
      .catch((e) => {
        console.warn("loadSysInfo failed:", e);
      });
  },

  svcRestart(name) {
    this.status = `Restarting ${name}...`;
    this.services[name] = "restarting";
    fetch(`/api?cmd=svcctl+restart+${encodeURIComponent(name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        this.status = d.output || "Done";
        setTimeout(() => {
          this.loadSysInfo();
        }, 3000);
      })
      .catch((e) => {
        this.status = "Error: " + e;
      });
  },
  svcStart(name) {
    this.status = `Starting ${name}...`;
    this.services[name] = "activating";
    fetch(`/api?cmd=svcctl+start+${encodeURIComponent(name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        this.status = d.output || "Done";
        setTimeout(() => {
          this.loadSysInfo();
        }, 3000);
      })
      .catch((e) => {
        this.status = "Error: " + e;
      });
  },
  dbReset() {
    if (!confirm("Clear all event log history?")) return;
    this.status = "Resetting event log...";
    fetch("/api?cmd=dbreset")
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        this.status = d.output || "Done";
        this.eventLog = [];
        this.eventTotal = 0;
        this.loadEventLog();
      })
      .catch((e) => {
        this.status = "Error: " + e;
      });
  },
  restartServer() {
    this.status = "Restarting web server...";
    this.webRestarting = true;
    fetch("/api?cmd=restart-web").catch(() => {});
    setTimeout(() => {
      location.reload();
    }, 3000);
  },
};
