/* Alpine.js application for Stars Outside camera control panel */
const mergeModule = (target, mod) => {
  if (mod.state) Object.assign(target, mod.state);
  Object.getOwnPropertyNames(mod).forEach((key) => {
    if (key === "state") return;
    Object.defineProperty(
      target,
      key,
      Object.getOwnPropertyDescriptor(mod, key),
    );
  });
};

function app() {
  const isAdmin = document.body.dataset.page === "admin";

  const base = {
    /* Reactive state — core only */
    isAdmin,
    status: "",
    defcon: 5,
    defconTime: "",
    _prevDefcon: 5,
    _simulating: false,
    simCount: 100,
    darkMode: localStorage.getItem("theme")
      ? localStorage.getItem("theme") === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches,
    locale: localStorage.getItem("locale") || "he",
    noPolling: new URLSearchParams(location.search).get("polling") === "false",
    webRestarting: false,
    panels: Object.assign(
      {
        sysinfo: true,
        image: false,
        publish: false,
        eventLog: false,
        admin: false,
      },
      JSON.parse(localStorage.getItem("panels") || "{}"),
    ),

    /* Sysinfo defaults — needed on both pages for defcon polling */
    sys: {
      uptime: "...",
      load: "...",
      temp: "...",
      dbSize: "...",
      dbOk: false,
      geoCount: 0,
      geoOk: false,
    },
    services: {},
    cpuHistory: [],
    tempHistory: [],
    hasCamera: false,

    /* Computed — core */
    get siteName() {
      return this._strings.site_name || "Stars Outside";
    },
    get defconLabel() {
      let label;
      if (this.defcon === 2) label = this._strings.defcon2_label || "RED ALERT";
      else if (this.defcon === 4)
        label = this._strings.defcon4_label || "HIGH ALERT";
      else label = this._strings.defcon5_label || "ALL CLEAR";
      if (this.defconTime && this.defcon !== 5)
        label += " - " + this.defconTime;
      return label;
    },

    /* i18n — loaded from /static/i18n/{locale}.json */
    _strings: {},
    async _loadStrings(locale) {
      try {
        const r = await fetch(`/static/i18n/${locale}.json`);
        this._strings = await r.json();
      } catch {
        this._strings = {};
      }
    },
    t(key) {
      return this._strings[key] || key;
    },
    chevron(open) {
      if (open) return "\u25BE";
      return this.locale === "he" ? "\u25C2" : "\u25B8";
    },

    /* UI toggles */
    togglePanel(name) {
      const wasOpen = this.panels[name];
      const keys = Object.keys(this.panels);
      for (let i = 0; i < keys.length; i++) this.panels[keys[i]] = false;
      this.panels[name] = !wasOpen;
    },
    toggleTheme() {
      this.darkMode = !this.darkMode;
      document.documentElement.setAttribute(
        "data-theme",
        this.darkMode ? "dark" : "light",
      );
      localStorage.setItem("theme", this.darkMode ? "dark" : "light");
      if (this.leafletMap && this._tileLayer) {
        this.leafletMap.removeLayer(this._tileLayer);
        const tileUrl = this.darkMode
          ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png";
        this._tileLayer = L.tileLayer(tileUrl, {
          maxZoom: 18,
          keepBuffer: 4,
          loadBuffer: 2,
          updateWhenZooming: false,
          updateWhenIdle: true,
        }).addTo(this.leafletMap);
      }
    },
    async toggleLocale() {
      this.locale = this.locale === "he" ? "en" : "he";
      localStorage.setItem("locale", this.locale);
      document.documentElement.setAttribute(
        "dir",
        this.locale === "he" ? "rtl" : "ltr",
      );
      await this._loadStrings(this.locale);
    },

    /* Initialize */
    async init() {
      document.documentElement.setAttribute(
        "data-theme",
        this.darkMode ? "dark" : "light",
      );
      document.documentElement.setAttribute(
        "dir",
        this.locale === "he" ? "rtl" : "ltr",
      );
      await this._loadStrings(this.locale);
      this.$nextTick(() => {
        const topBar = document.querySelector(".top-bar");
        if (topBar)
          document.documentElement.style.setProperty(
            "--top-bar-height",
            topBar.offsetHeight + "px",
          );
      });
      this.$watch(
        "panels",
        (val) => {
          localStorage.setItem("panels", JSON.stringify(val));
        },
        { deep: true },
      );
      this.$watch("defcon", (val) => {
        this.updateMapMarkers();
        const prev = this._prevDefcon;
        if (prev && prev !== val) {
          if (val === 5) this.fireConfetti();
          if (val === 2) this.showPositiveMessages();
        }
        this._prevDefcon = val;
      });
      setTimeout(() => {
        this.initMap();
        this.locateUser();
      }, 100);

      if (isAdmin) {
        /* Admin: verify session cookie with server */
        this.adminVerifyAndLoad();

        /* Admin: init panel modules */
        if (this.initCamera) this.initCamera();
        if (this.initChannels) this.initChannels();
        if (this.initEventLog) this.initEventLog();
      }

      /* Start polling */
      const noPolling = this.noPolling;
      if (isAdmin) {
        this.loadSysInfo();
        this.loadEventLog();
      } else {
        this.loadDefcon();
      }
      if (!noPolling) {
        setInterval(() => {
          if (!this._simulating) {
            if (isAdmin) {
              this.loadSysInfo();
              this.loadEventLog();
            } else {
              this.loadDefcon();
            }
          }
        }, 5000);
      }
    },

    /* Helpers */
    _addAlertCityMarker(city) {
      if (!this.leafletMap) return false;
      const key = `${city.name}|${city.lat}|${city.lng}`;
      if (this._alertCityKeys[key]) return false;
      this._alertCityKeys[key] = true;
      const marker = L.circleMarker([city.lat, city.lng], {
        radius: 4,
        color: "var(--color-red)",
        weight: 1,
        fillColor: "var(--color-red)",
        fillOpacity: 0.7,
      }).addTo(this.leafletMap);
      marker.bindTooltip(city.name_he || city.name, {
        direction: "right",
        offset: [6, 0],
        className: "city-tooltip defcon2",
      });
      this.alertCityMarkers.push(marker);
      return true;
    },
    _applyDefcon(defcon) {
      if (!defcon) return;
      if (defcon !== this.defcon && defcon !== 5)
        this.defconTime = new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
      this.defcon = defcon;
      document.title = `${this.siteName} - ${this.defconLabel}`;
    },
    _applyAlertCities(defcon, cities) {
      if (defcon === 2 && cities && cities.length > 0) {
        let added = false;
        cities.forEach((city) => {
          if (this._addAlertCityMarker(city)) added = true;
        });
        if (added) this.initialFit();
      } else if (defcon === 5 && this.alertCityMarkers.length > 0) {
        this.clearAlertCities();
      }
    },

    /* Simulation */
    simulate(count) {
      this._simulating = true;
      count = count || 100;
      fetch(`/api?cmd=simulate&count=${count}`)
        .then((r) => r.json())
        .then((d) => {
          this.clearAlertCities();
          (d.alert_cities || []).forEach((city) => {
            this._addAlertCityMarker(city);
          });
          this.defcon = 2;
          this.defconTime = new Date().toLocaleTimeString("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });
          this.updateMapMarkers();
        });
    },

    /* Data loading */
    loadDefcon() {
      fetch("/api?cmd=defcon")
        .then((r) => r.json())
        .then((d) => {
          this._applyDefcon(d.defcon);
          this._applyAlertCities(d.defcon, d.alert_cities);
        })
        .catch((e) => {
          console.warn("loadDefcon failed:", e);
        });
    },
  };

  /* Merge in always-loaded modules */
  mergeModule(base, MapModule);
  mergeModule(base, EffectsModule);

  /* Admin-only modules (loaded via <script> tags on admin page) */
  if (typeof SysinfoModule !== "undefined") mergeModule(base, SysinfoModule);
  if (typeof CameraModule !== "undefined") mergeModule(base, CameraModule);
  if (typeof ChannelsModule !== "undefined") mergeModule(base, ChannelsModule);
  if (typeof EventLogModule !== "undefined") mergeModule(base, EventLogModule);
  if (typeof AdminModule !== "undefined") mergeModule(base, AdminModule);

  return base;
}
