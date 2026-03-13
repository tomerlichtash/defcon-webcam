/* Stars Outside — application bootstrap (no Alpine) */
import {
  store,
  setStrings,
  applyDefcon,
  simulateDefcon,
  clearSimulation,
  setSimulating,
  setSidebarOpen,
  updateSystem,
  setEntries,
  prependEntries,
  setTotal,
} from "./store.js";
import { MapManager } from "./map.js";
import { EffectsManager } from "./effects.js";

/* ---- Component imports (registers custom elements) ---- */
import "./components/top-bar.js";
import "./components/sidebar-panel.js";
import "./components/sysinfo-content.js";
import "./components/camera-content.js";
import "./components/eventlog-content.js";
import "./components/admin-content.js";

/* ---- Init ---- */

const isAdmin = document.body.dataset.page === "admin";
const noPolling = store.getState().system.noPolling;

/* Apply initial theme + locale */
const initTheme = store.getState().ui.theme;
document.documentElement.setAttribute("data-theme", initTheme);
const initLocale = store.getState().ui.locale;
document.documentElement.setAttribute(
  "dir",
  initLocale === "he" ? "rtl" : "ltr",
);

/* Load i18n strings */
async function loadStrings(locale) {
  try {
    const r = await fetch(`/static/i18n/${locale}.json`);
    const strings = await r.json();
    store.dispatch(setStrings(strings));
  } catch {
    store.dispatch(setStrings({}));
  }
}

await loadStrings(initLocale);

/* Update data-i18n labels in light DOM when strings change */
function updateI18nLabels() {
  const strings = store.getState().ui.strings;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (strings[key]) el.textContent = strings[key];
  });
}
store.subscribe(updateI18nLabels);
updateI18nLabels();

/* Measure top bar height for CSS */
requestAnimationFrame(() => {
  const topBar = document.querySelector("top-bar");
  if (topBar) {
    document.documentElement.style.setProperty(
      "--top-bar-height",
      topBar.offsetHeight + "px",
    );
  }
});

/* ---- Sidebar drawer (admin only) ---- */

if (isAdmin) {
  const drawer = document.getElementById("sidebar-drawer");
  if (drawer) {
    let syncing = false;

    const syncDrawer = () => {
      const shouldBeOpen = store.getState().ui.sidebarOpen;
      if (drawer.open === shouldBeOpen) return;
      syncing = true;
      if (shouldBeOpen) drawer.show();
      else drawer.hide();
    };

    store.subscribe(syncDrawer);

    drawer.addEventListener("sl-after-hide", () => {
      if (!syncing) store.dispatch(setSidebarOpen(false));
      syncing = false;
    });
    drawer.addEventListener("sl-after-show", () => {
      syncing = false;
    });

    /* Wait for upgrade, then apply initial state */
    await customElements.whenDefined("sl-drawer");
    syncDrawer();
  }
}

/* ---- MapManager + EffectsManager ---- */

const mapManager = new MapManager();
const effectsManager = new EffectsManager();

setTimeout(() => {
  mapManager.initMap();
  mapManager.locateUser();
}, 100);

/* ---- Channels (simple localStorage wiring for slotted switches) ---- */

if (isAdmin) {
  const initChannels = () => {
    const tgSwitch = document.getElementById("pub-telegram");
    const twSwitch = document.getElementById("pub-twitter");
    if (tgSwitch) {
      tgSwitch.checked = localStorage.getItem("pubTelegram") !== "false";
      tgSwitch.addEventListener("sl-change", () => {
        localStorage.setItem("pubTelegram", tgSwitch.checked);
      });
    }
    if (twSwitch) {
      twSwitch.checked = localStorage.getItem("pubTwitter") === "true";
      twSwitch.addEventListener("sl-change", () => {
        localStorage.setItem("pubTwitter", twSwitch.checked);
      });
    }
  };
  /* Wait for Shoelace elements to register */
  if (customElements.get("sl-switch")) {
    initChannels();
  } else {
    customElements.whenDefined("sl-switch").then(initChannels);
  }
}

/* ---- Data loading ---- */

function loadDefcon() {
  fetch("/api?cmd=defcon")
    .then((r) => r.json())
    .then((d) => {
      store.dispatch(
        applyDefcon({ defcon: d.defcon, alertCities: d.alert_cities }),
      );
    })
    .catch((e) => console.warn("loadDefcon failed:", e));
}

function loadSysInfo() {
  fetch("/api?cmd=sysinfo")
    .then((r) => r.json())
    .then((d) => {
      const info = d.sysinfo || {};
      store.dispatch(updateSystem(info));
      store.dispatch(
        applyDefcon({ defcon: info.defcon, alertCities: info.alert_cities }),
      );
    })
    .catch((e) => console.warn("loadSysInfo failed:", e));
}

function loadEventLog() {
  const entries = store.getState().eventlog.entries;
  let url = "/api?cmd=eventlog";
  if (entries.length > 0)
    url += "&since=" + encodeURIComponent(entries[0].time);
  fetch(url)
    .then((r) => r.json())
    .then((d) => {
      const newEvents = d.log || [];
      store.dispatch(setTotal(d.total || 0));
      store.dispatch(
        applyDefcon({ defcon: d.defcon, alertCities: d.alert_cities }),
      );
      if (entries.length === 0) store.dispatch(setEntries(newEvents));
      else if (newEvents.length > 0) store.dispatch(prependEntries(newEvents));
    })
    .catch((e) => console.warn("loadEventLog failed:", e));
}

/* Initial load */
if (isAdmin) {
  loadSysInfo();
  loadEventLog();
} else {
  loadDefcon();
}

/* Polling loop */
if (!noPolling) {
  setInterval(() => {
    if (store.getState().ui.simulating) return;
    if (isAdmin) {
      loadSysInfo();
      loadEventLog();
    } else {
      loadDefcon();
    }
  }, 5000);
}

/* ---- Simulation (event delegation from top-bar / admin-content) ---- */

document.addEventListener("simulate", (e) => {
  const count = e.detail?.count || 100;
  store.dispatch(setSimulating(true));
  fetch(`/api?cmd=simulate&count=${count}`)
    .then((r) => r.json())
    .then((d) => {
      store.dispatch(simulateDefcon({ alertCities: d.alert_cities || [] }));
    });
});

document.addEventListener("clear-simulation", () => {
  store.dispatch(clearSimulation());
  store.dispatch(setSimulating(false));
  effectsManager.fireConfetti();
});
