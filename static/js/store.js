/* Stars Outside — Redux Toolkit store */
import { configureStore, createSlice } from "@reduxjs/toolkit";

/* ---- Defcon slice ---- */

const defconSlice = createSlice({
  name: "defcon",
  initialState: {
    level: 5,
    time: "",
    alertCities: [],
  },
  reducers: {
    setDefcon(state, action) {
      const newLevel = action.payload;
      if (newLevel !== state.level && newLevel !== 5) {
        state.time = new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
      }
      state.level = newLevel;
    },
    applyDefcon(state, action) {
      const { defcon, alertCities } = action.payload;
      if (defcon != null) {
        if (defcon !== state.level && defcon !== 5) {
          state.time = new Date().toLocaleTimeString("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });
        }
        state.level = defcon;
      }
      if (defcon === 2 && alertCities && alertCities.length > 0) {
        const existing = new Set(
          state.alertCities.map((c) => `${c.name}|${c.lat}|${c.lng}`),
        );
        for (const city of alertCities) {
          const key = `${city.name}|${city.lat}|${city.lng}`;
          if (!existing.has(key)) {
            state.alertCities.push(city);
          }
        }
      } else if (defcon === 5) {
        state.alertCities = [];
      }
    },
    setAlertCities(state, action) {
      state.alertCities = action.payload;
    },
    clearAlertCities(state) {
      state.alertCities = [];
    },
    simulateDefcon(state, action) {
      /* Atomic: replace cities + set level 2 in one dispatch */
      state.alertCities = action.payload.alertCities || [];
      state.level = 2;
      state.time = new Date().toLocaleTimeString("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    },
    clearSimulation(state) {
      /* Atomic: clear cities + set level 5 in one dispatch */
      state.alertCities = [];
      state.level = 5;
    },
  },
});

/* ---- UI slice ---- */

const savedPanels = JSON.parse(localStorage.getItem("panels") || "{}");

const uiSlice = createSlice({
  name: "ui",
  initialState: {
    theme:
      localStorage.getItem("theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"),
    locale: localStorage.getItem("locale") || "he",
    strings: {},
    sidebarOpen: localStorage.getItem("sidebarOpen") === "true",
    panels: {
      sysinfo: true,
      image: false,
      publish: false,
      eventLog: false,
      admin: false,
      ...savedPanels,
    },
    status: "",
    simulating: false,
    simCount: 100,
  },
  reducers: {
    setTheme(state, action) {
      state.theme = action.payload;
      localStorage.setItem("theme", action.payload);
    },
    setLocale(state, action) {
      state.locale = action.payload;
      localStorage.setItem("locale", action.payload);
    },
    setStrings(state, action) {
      state.strings = action.payload;
    },
    togglePanel(state, action) {
      const name = action.payload;
      const wasOpen = state.panels[name];
      for (const key of Object.keys(state.panels)) {
        state.panels[key] = false;
      }
      state.panels[name] = !wasOpen;
      localStorage.setItem("panels", JSON.stringify(state.panels));
    },
    setSidebarOpen(state, action) {
      state.sidebarOpen = action.payload;
      localStorage.setItem("sidebarOpen", action.payload);
    },
    toggleSidebar(state) {
      state.sidebarOpen = !state.sidebarOpen;
      localStorage.setItem("sidebarOpen", state.sidebarOpen);
    },
    setStatus(state, action) {
      state.status = action.payload;
    },
    setSimulating(state, action) {
      state.simulating = action.payload;
    },
    setSimCount(state, action) {
      state.simCount = action.payload;
    },
  },
});

/* ---- System slice ---- */

const systemSlice = createSlice({
  name: "system",
  initialState: {
    uptime: "...",
    load: "...",
    temp: "...",
    dbOk: false,
    dbSize: "...",
    geoOk: false,
    geoCount: 0,
    services: {},
    webRestarting: false,
    noPolling: new URLSearchParams(location.search).get("polling") === "false",
    hasCamera: false,
    cpuHistory: [],
    tempHistory: [],
  },
  reducers: {
    updateSystem(state, action) {
      const info = action.payload;
      if (info.uptime) state.uptime = info.uptime.replace(/^up\s+/, "");
      if (info.load) {
        state.load = info.load;
        state.cpuHistory.push(parseInt(info.load));
        if (state.cpuHistory.length > 30) state.cpuHistory.shift();
      }
      if (info.temp) {
        state.temp = info.temp;
        state.tempHistory.push(parseFloat(info.temp));
        if (state.tempHistory.length > 30) state.tempHistory.shift();
      }
      if (info.db_size) state.dbSize = info.db_size;
      state.dbOk = info.db_ok !== false;
      if (info.geo_count !== undefined) state.geoCount = info.geo_count;
      state.geoOk = info.geo_ok !== false;
      if (info.has_camera !== undefined) state.hasCamera = info.has_camera;
      if (info.services) state.services = info.services;
    },
    setServices(state, action) {
      state.services = action.payload;
    },
    setServiceState(state, action) {
      const { name, status } = action.payload;
      state.services[name] = status;
    },
    setWebRestarting(state, action) {
      state.webRestarting = action.payload;
    },
    setHasCamera(state, action) {
      state.hasCamera = action.payload;
    },
  },
});

/* ---- Camera slice ---- */

const cameraSlice = createSlice({
  name: "camera",
  initialState: {
    camOn: localStorage.getItem("camOn") === "true",
    camLoading: false,
    active: { mode: "", res: "", fps: "", rotation: "0" },
    bright: 58,
    zoom: 100,
    cssGrayscale: localStorage.getItem("filterGrayscale") === "true",
    cssInvert: localStorage.getItem("filterInvert") === "true",
    streamStats: "",
    lastRes: "",
    lastFps: "",
  },
  reducers: {
    setCamOn(state, action) {
      state.camOn = action.payload;
      localStorage.setItem("camOn", action.payload);
    },
    setCamLoading(state, action) {
      state.camLoading = action.payload;
    },
    setActive(state, action) {
      Object.assign(state.active, action.payload);
    },
    applyStatus(state, action) {
      const output = action.payload;
      let curRes = "",
        curFps = "";
      output.split("\n").forEach((l) => {
        let m;
        if ((m = l.match(/Mode: (\w+)/))) state.active.mode = m[1];
        if ((m = l.match(/Resolution: (\w+)/))) {
          state.active.res = m[1];
          curRes = m[1];
        }
        if ((m = l.match(/Rotation: (\d+)/))) state.active.rotation = m[1];
        if ((m = l.match(/Brightness: (\d+)/))) state.bright = parseInt(m[1]);
        if ((m = l.match(/FPS: (\d+)/))) {
          state.active.fps = m[1];
          curFps = m[1];
        }
        if ((m = l.match(/Zoom: (\d+)/))) state.zoom = parseInt(m[1]);
      });
      if (
        state.lastRes &&
        state.lastFps &&
        (curRes !== state.lastRes || curFps !== state.lastFps)
      ) {
        state._needCountdown = 3;
      }
      if (curRes) state.lastRes = curRes;
      if (curFps) state.lastFps = curFps;
    },
    setBright(state, action) {
      state.bright = action.payload;
    },
    setZoom(state, action) {
      state.zoom = action.payload;
    },
    setCssGrayscale(state, action) {
      state.cssGrayscale = action.payload;
      localStorage.setItem("filterGrayscale", action.payload);
    },
    setCssInvert(state, action) {
      state.cssInvert = action.payload;
      localStorage.setItem("filterInvert", action.payload);
    },
    setStreamStats(state, action) {
      state.streamStats = action.payload;
    },
  },
});

/* ---- Event Log slice ---- */

const savedFilters = JSON.parse(
  localStorage.getItem("filters") ||
    '{"alerts":true,"scans":true,"status":true,"system":true}',
);

const eventlogSlice = createSlice({
  name: "eventlog",
  initialState: {
    entries: [],
    total: 0,
    filters: savedFilters,
    loadingMore: false,
  },
  reducers: {
    setEntries(state, action) {
      state.entries = action.payload;
    },
    prependEntries(state, action) {
      state.entries = action.payload.concat(state.entries);
    },
    appendEntries(state, action) {
      state.entries = state.entries.concat(action.payload);
    },
    setTotal(state, action) {
      state.total = action.payload;
    },
    toggleFilter(state, action) {
      const key = action.payload;
      state.filters[key] = !state.filters[key];
      localStorage.setItem("filters", JSON.stringify(state.filters));
    },
    setLoadingMore(state, action) {
      state.loadingMore = action.payload;
    },
    resetLog(state) {
      state.entries = [];
      state.total = 0;
    },
    toggleEntryOpen(state, action) {
      const idx = action.payload;
      if (state.entries[idx]) {
        state.entries[idx]._open = !state.entries[idx]._open;
      }
    },
  },
});

/* ---- Admin slice ---- */

const adminSlice = createSlice({
  name: "admin",
  initialState: {
    auth: false,
    authError: "",
    config: {},
    refreshTimer: null,
  },
  reducers: {
    setAdminAuth(state, action) {
      state.auth = action.payload;
    },
    setAdminConfig(state, action) {
      state.config = action.payload;
    },
    setAdminAuthError(state, action) {
      state.authError = action.payload;
    },
  },
});

/* ---- Store ---- */

export const store = configureStore({
  reducer: {
    defcon: defconSlice.reducer,
    ui: uiSlice.reducer,
    system: systemSlice.reducer,
    camera: cameraSlice.reducer,
    eventlog: eventlogSlice.reducer,
    admin: adminSlice.reducer,
  },
  middleware: (getDefault) => getDefault({ serializableCheck: false }),
});

/* ---- Exports ---- */

export const {
  setDefcon,
  applyDefcon,
  setAlertCities,
  clearAlertCities,
  simulateDefcon,
  clearSimulation,
} = defconSlice.actions;

export const {
  setTheme,
  setLocale,
  setStrings,
  setSidebarOpen,
  toggleSidebar,
  togglePanel,
  setStatus,
  setSimulating,
  setSimCount,
} = uiSlice.actions;

export const {
  updateSystem,
  setServices,
  setServiceState,
  setWebRestarting,
  setHasCamera,
} = systemSlice.actions;

export const {
  setCamOn,
  setCamLoading,
  setActive,
  applyStatus,
  setBright,
  setZoom,
  setCssGrayscale,
  setCssInvert,
  setStreamStats,
} = cameraSlice.actions;

export const {
  setEntries,
  prependEntries,
  appendEntries,
  setTotal,
  toggleFilter,
  setLoadingMore,
  resetLog,
  toggleEntryOpen,
} = eventlogSlice.actions;

export const { setAdminAuth, setAdminConfig, setAdminAuthError } =
  adminSlice.actions;

/* ---- Selectors ---- */

export const selectDefcon = (state) => state.defcon;
export const selectUI = (state) => state.ui;
export const selectSystem = (state) => state.system;
export const selectCamera = (state) => state.camera;
export const selectEventlog = (state) => state.eventlog;
export const selectAdmin = (state) => state.admin;

export const selectSiteName = (state) =>
  state.ui.strings.site_name || "Stars Outside";
export const selectDefconLabel = (state) => {
  const { level, time } = state.defcon;
  const s = state.ui.strings;
  let label;
  if (level === 2) label = s.defcon2_label || "RED ALERT";
  else if (level === 4) label = s.defcon4_label || "HIGH ALERT";
  else label = s.defcon5_label || "ALL CLEAR";
  if (time && level !== 5) label += " - " + time;
  return label;
};

export const selectAggLog = (state) => {
  const { entries, filters } = state.eventlog;
  const typeMap = {
    alerts: "alert",
    scans: "scan",
    status: "status",
    system: "system",
  };
  const activeTypes = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v) activeTypes[typeMap[k]] = true;
  }
  return entries.filter((e) => activeTypes[e._type]).slice(0, 200);
};
