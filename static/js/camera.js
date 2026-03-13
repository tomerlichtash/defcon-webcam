/* Camera control panel module — stream, modes, filters */
var CameraModule = {
  state: {
    hasCamera: true,
    camOn: localStorage.getItem("camOn") === "true",
    camHover: false,
    camLoading: false,
    bright: 58,
    zoom: 100,
    streamStats: "",
    cssGrayscale: localStorage.getItem("filterGrayscale") === "true",
    cssInvert: localStorage.getItem("filterInvert") === "true",
    lastRes: "",
    lastFps: "",
    active: { mode: "", res: "", rotation: "", fps: "" },
    _streamWatchdog: null,
  },

  get _streamHost() {
    return location.hostname || "localhost";
  },

  get osdLine() {
    const parts = [];
    if (this.active.mode) parts.push(this.active.mode);
    if (this.active.res) parts.push(this.active.res);
    if (this.active.fps) parts.push(this.active.fps + "fps");
    if (this.active.rotation && this.active.rotation !== "0")
      parts.push("rot " + this.active.rotation);
    return parts.join(" | ");
  },

  initCamera() {
    const host = this._streamHost;
    const streamEl = document.getElementById("stream");
    this.$watch("camOn", (val) => {
      if (streamEl) streamEl.style.display = val ? "" : "none";
      this.camLoading = false;
      localStorage.setItem("camOn", val);
    });
    if (this.camOn && streamEl) {
      streamEl.src = `http://${host}:8080/?action=stream`;
      streamEl.style.display = "";
    }
    if (streamEl) {
      let staleCount = 0;
      if (this._errorHandler) {
        streamEl.removeEventListener("error", this._errorHandler);
      }
      this._errorHandler = () => {
        if (this.camOn) {
          this.streamStats = "Stream error — reconnecting...";
          setTimeout(() => {
            streamEl.src = `http://${host}:8080/?action=stream&t=${Date.now()}`;
          }, 1000);
        }
      };
      streamEl.addEventListener("error", this._errorHandler);
      if (this._streamWatchdog) clearInterval(this._streamWatchdog);
      this._streamWatchdog = setInterval(() => {
        if (!this.camOn) return;
        if (streamEl.naturalWidth === 0 && streamEl.style.display !== "none") {
          staleCount++;
          this.streamStats = `Stale (${staleCount})`;
          if (staleCount >= 2) {
            this.streamStats = "Reconnecting...";
            streamEl.src = `http://${host}:8080/?action=stream&t=${Date.now()}`;
            staleCount = 0;
          }
        } else {
          staleCount = 0;
          this.streamStats = "";
        }
      }, 5000);
    }
  },
  applyStatus(output) {
    let curRes = "",
      curFps = "";
    output.split("\n").forEach((l) => {
      let m;
      if ((m = l.match(/Mode: (\w+)/))) this.active.mode = m[1];
      if ((m = l.match(/Resolution: (\w+)/))) {
        this.active.res = m[1];
        curRes = m[1];
      }
      if ((m = l.match(/Rotation: (\d+)/))) this.active.rotation = m[1];
      if ((m = l.match(/Brightness: (\d+)/))) this.bright = parseInt(m[1]);
      if ((m = l.match(/FPS: (\d+)/))) {
        this.active.fps = m[1];
        curFps = m[1];
      }
      if ((m = l.match(/Zoom: (\d+)/))) this.zoom = parseInt(m[1]);
    });
    if (
      this.lastRes &&
      this.lastFps &&
      (curRes !== this.lastRes || curFps !== this.lastFps)
    )
      this.countdown(3);
    if (curRes) this.lastRes = curRes;
    if (curFps) this.lastFps = curFps;
  },
  fetchStatus() {
    fetch("/api?cmd=status")
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        this.applyStatus(d.output);
      })
      .catch((e) => {
        console.warn("fetchStatus failed:", e);
      });
  },
  cmd(c) {
    this.status = `Applying: ${c}...`;
    fetch(`/api?cmd=${encodeURIComponent(c)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        this.status = d.output || "Done";
        if (["day", "night", "indoor"].includes(c)) this.active.mode = c;
        let m;
        if ((m = c.match(/^res (\w+)/))) this.active.res = m[1];
        if ((m = c.match(/^rotate (\d+)/))) this.active.rotation = m[1];
        if ((m = c.match(/^fps (\d+)/))) this.active.fps = m[1];
        if (
          c.startsWith("res ") ||
          c.startsWith("rotate ") ||
          c.startsWith("fps ") ||
          c === "day" ||
          c === "night" ||
          c === "indoor"
        )
          this.countdown(5);
      })
      .catch((e) => {
        this.status = "Error: " + e;
      });
  },
  countdown(sec) {
    let left = sec;
    const iv = setInterval(() => {
      this.status = `Refreshing stream in ${left}s...`;
      left--;
      if (left < 0) {
        clearInterval(iv);
        this.status = "Connecting to stream...";
        this.tryLoadStream(0);
      }
    }, 1000);
  },
  tryLoadStream(attempt) {
    const base = `http://${this._streamHost}:8080/`;
    fetch(`${base}?action=snapshot&t=${Date.now()}`, { mode: "no-cors" })
      .then(() => {
        const streamEl = document.getElementById("stream");
        if (streamEl) streamEl.src = `${base}?action=stream&t=${Date.now()}`;
        this.camOn = true;
        this.camLoading = false;
        this.status = "";
      })
      .catch(() => {
        if (attempt < 10)
          setTimeout(() => {
            this.tryLoadStream(attempt + 1);
          }, 2000);
        else {
          this.status = "Stream unavailable";
          this.camLoading = false;
        }
      });
  },
  camCtl(action) {
    this.camLoading = true;
    this.status = `Camera: ${action}...`;
    if (action === "start" || action === "restart")
      this.services["mjpg-streamer"] = "activating";
    else if (action === "stop") this.services["mjpg-streamer"] = "deactivating";
    fetch(`/api?cmd=camctl+${action}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        this.status = d.output || "Done";
        if (action !== "stop") this.countdown(3);
        setTimeout(() => {
          this.loadSysInfo();
        }, 3000);
      })
      .catch((e) => {
        this.status = "Error: " + e;
        this.camLoading = false;
      });
  },
  applyFilters() {
    const el = document.getElementById("stream");
    if (!el) return;
    const f = [];
    if (this.cssGrayscale) f.push("grayscale(1)");
    if (this.cssInvert) f.push("invert(1)");
    el.style.filter = f.length ? f.join(" ") : "none";
  },
  toggleGrayscale() {
    this.cssGrayscale = !this.cssGrayscale;
    localStorage.setItem("filterGrayscale", this.cssGrayscale);
    this.applyFilters();
  },
  toggleInvert() {
    this.cssInvert = !this.cssInvert;
    localStorage.setItem("filterInvert", this.cssInvert);
    this.applyFilters();
  },
};
