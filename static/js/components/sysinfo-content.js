/* Stars Outside — system info panel content (Shoelace primitives) */
import { LitElement, html, css, nothing } from "lit";
import {
  store,
  setStatus,
  setWebRestarting,
  setServiceState,
  resetLog,
} from "../store.js";

export class SysinfoContent extends LitElement {
  static properties = {
    _sys: { state: true },
    _services: { state: true },
    _cpuHistory: { state: true },
    _tempHistory: { state: true },
    _webRestarting: { state: true },
    _noPolling: { state: true },
    _strings: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      padding: 4px 12px 10px;
      user-select: none;
    }

    .section {
      padding: 6px 0;
      border-bottom: 1px solid var(--so-border-light);
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.65em;
      padding: 2px 0;
    }

    .label {
      color: var(--so-text-muted);
      text-transform: uppercase;
      font-size: 0.85em;
    }

    .spark-value {
      display: inline-flex;
      align-items: center;
    }

    .spark-value svg {
      display: block;
    }

    .level-ok {
      color: var(--so-color-ok);
    }
    .level-warn {
      color: var(--so-color-warn);
    }
    .level-danger {
      color: var(--so-color-danger);
    }
    .level-critical {
      color: var(--so-color-red);
    }

    .svc-row {
      display: flex;
      align-items: center;
      padding: 2px 4px;
      margin: 0 -4px;
      border-radius: 4px;
      cursor: default;
      font-size: 0.72em;
      transition: background 0.15s;
    }

    .svc-row:hover {
      background: var(--so-border-subtle);
    }

    .svc-row .label {
      flex: 1;
    }

    .svc-row sl-button {
      opacity: 0;
      transition: opacity 0.15s;
    }

    .svc-row:hover sl-button {
      opacity: 1;
    }

    sl-badge {
      margin-right: 6px;
    }
  `;

  _sparkId = 0;

  constructor() {
    super();
    this._sys = {};
    this._services = {};
    this._cpuHistory = [];
    this._tempHistory = [];
    this._webRestarting = false;
    this._noPolling = false;
    this._strings = {};
  }

  connectedCallback() {
    super.connectedCallback();
    this._unsubscribe = store.subscribe(() => this._onStoreChange());
    this._onStoreChange();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._unsubscribe) this._unsubscribe();
  }

  _onStoreChange() {
    const sys = store.getState().system;
    const ui = store.getState().ui;
    this._sys = sys;
    this._services = sys.services;
    this._cpuHistory = [...sys.cpuHistory];
    this._tempHistory = [...sys.tempHistory];
    this._webRestarting = sys.webRestarting;
    this._noPolling = sys.noPolling;
    this._strings = ui.strings;
  }

  _t(key) {
    return this._strings[key] || key;
  }

  _sparkline(data, max) {
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
    return `<svg width="${w}" height="${h}" style="margin-right:6px"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="currentColor" stop-opacity="0.3"/><stop offset="100%" stop-color="currentColor" stop-opacity="0.02"/></linearGradient></defs><path d="${areaD}" fill="url(#${id})"/><path d="${d}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="2" fill="currentColor"/></svg>`;
  }

  _cpuLevel() {
    const pct = parseInt(this._sys.load);
    return pct < 60 ? "ok" : pct < 80 ? "warn" : "danger";
  }

  _tempLevel() {
    const deg = parseFloat(this._sys.temp);
    return deg < 60
      ? "ok"
      : deg < 70
        ? "warn"
        : deg < 80
          ? "danger"
          : "critical";
  }

  _svcBadgeVariant(name) {
    if (name === "__web") {
      if (this._webRestarting) return "danger";
      if (this._noPolling) return "warning";
      return "success";
    }
    const state = this._services[name];
    if (!state) return "danger";
    if (
      state === "activating" ||
      state === "restarting" ||
      state === "deactivating"
    )
      return "warning";
    return state === "active" ? "success" : "danger";
  }

  _svcRestart(name) {
    store.dispatch(setStatus(`Restarting ${name}...`));
    store.dispatch(setServiceState({ name, status: "restarting" }));
    fetch(`/api?cmd=svcctl+restart+${encodeURIComponent(name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        store.dispatch(setStatus(d.output || "Done"));
      })
      .catch((e) => {
        store.dispatch(setStatus("Error: " + e));
      });
  }

  _svcStart(name) {
    store.dispatch(setStatus(`Starting ${name}...`));
    store.dispatch(setServiceState({ name, status: "activating" }));
    fetch(`/api?cmd=svcctl+start+${encodeURIComponent(name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        store.dispatch(setStatus(d.output || "Done"));
      })
      .catch((e) => {
        store.dispatch(setStatus("Error: " + e));
      });
  }

  _dbReset() {
    if (!confirm("Clear all event log history?")) return;
    store.dispatch(setStatus("Resetting event log..."));
    fetch("/api?cmd=dbreset")
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        store.dispatch(setStatus(d.output || "Done"));
        store.dispatch(resetLog());
      })
      .catch((e) => {
        store.dispatch(setStatus("Error: " + e));
      });
  }

  _restartServer() {
    store.dispatch(setStatus("Restarting web server..."));
    store.dispatch(setWebRestarting(true));
    fetch("/api?cmd=restart-web").catch(() => {});
    setTimeout(() => {
      location.reload();
    }, 3000);
  }

  _renderServiceRows() {
    const labels = { alert: "Alert", web: "Web" };
    return Object.keys(this._services).map((name) => {
      const state = this._services[name];
      const isStarting = state === "activating" || state === "restarting";
      const isStopping = state === "deactivating";
      const isDown = state !== "active" && !isStarting && !isStopping;
      const suffix = isStarting
        ? " (starting)"
        : isStopping
          ? " (stopping)"
          : "";
      const label = (labels[name] || name) + suffix;
      return html`
        <div class="svc-row">
          <sl-badge
            variant=${this._svcBadgeVariant(name)}
            pill
            pulse
          ></sl-badge>
          <span class="label">${label}</span>
          ${isDown
            ? html`<sl-button
                size="small"
                variant="primary"
                outline
                @click=${() => this._svcStart(name)}
                >Start</sl-button
              >`
            : html`<sl-button
                size="small"
                variant="danger"
                outline
                @click=${() => this._svcRestart(name)}
                >Restart</sl-button
              >`}
        </div>
      `;
    });
  }

  render() {
    const sys = this._sys;
    const showTemp = sys.temp && sys.temp !== "...";
    return html`
      <div class="section">
        <div class="row">
          <span class="label">${this._t("uptime")}</span>
          <span>${sys.uptime}</span>
        </div>
      </div>
      <div class="section">
        <div class="row">
          <span class="label">${this._t("cpu")}</span>
          <span class="spark-value level-${this._cpuLevel()}">
            <span .innerHTML=${this._sparkline(this._cpuHistory, 100)}></span>
            <span>${sys.load}</span>
          </span>
        </div>
      </div>
      ${showTemp
        ? html`
            <div class="section">
              <div class="row">
                <span class="label">${this._t("temp")}</span>
                <span class="spark-value level-${this._tempLevel()}">
                  <span
                    .innerHTML=${this._sparkline(this._tempHistory, 100)}
                  ></span>
                  <span>${sys.temp}</span>
                </span>
              </div>
            </div>
          `
        : nothing}
      <div class="svc-row" style="margin-top:6px">
        <sl-badge
          variant=${this._svcBadgeVariant("__web")}
          pill
          pulse
        ></sl-badge>
        <span class="label">${this._t("web")}</span>
        <sl-button
          size="small"
          variant="danger"
          outline
          @click=${this._restartServer}
          >${this._t("restart")}</sl-button
        >
      </div>
      <div class="svc-row">
        <sl-badge
          variant=${sys.dbOk ? "success" : "danger"}
          pill
          pulse
        ></sl-badge>
        <span class="label"
          >${this._t("log")}
          <small style="opacity:0.6">(${sys.dbSize})</small></span
        >
        <sl-button size="small" variant="danger" outline @click=${this._dbReset}
          >${this._t("reset")}</sl-button
        >
      </div>
      <div class="svc-row">
        <sl-badge
          variant=${sys.geoOk ? "success" : "danger"}
          pill
          pulse
        ></sl-badge>
        <span class="label"
          >${this._t("geo")}
          <small style="opacity:0.6">(${sys.geoCount})</small></span
        >
      </div>
      ${this._renderServiceRows()}
    `;
  }
}

customElements.define("sysinfo-content", SysinfoContent);
