/* Stars Outside — camera controls panel content (Shoelace primitives) */
import { LitElement, html, css } from "lit";
import {
  store,
  setCamOn,
  setCamLoading,
  setActive,
  setBright,
  setZoom,
  setCssGrayscale,
  setCssInvert,
  setStreamStats,
  setStatus,
  setServiceState,
} from "../store.js";

export class CameraContent extends LitElement {
  static properties = {
    _camOn: { state: true },
    _camLoading: { state: true },
    _hasCamera: { state: true },
    _active: { state: true },
    _bright: { state: true },
    _zoom: { state: true },
    _cssGrayscale: { state: true },
    _cssInvert: { state: true },
    _strings: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      padding: 4px 12px 10px;
    }

    .controls-disabled {
      opacity: 0.4;
      pointer-events: none;
    }

    .setting-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 0;
      border-bottom: 1px solid var(--so-border-light);
      gap: 10px;
      font-size: 0.72em;
    }

    .setting-row:last-child {
      border-bottom: none;
    }

    .label {
      color: var(--so-text-muted);
      text-transform: uppercase;
      font-size: 0.85em;
      flex-shrink: 0;
      white-space: nowrap;
    }

    .label small {
      opacity: 0.6;
      margin-left: 4px;
    }

    sl-button-group {
      direction: ltr;
      flex-shrink: 0;
    }

    sl-range {
      flex: 1;
      min-width: 60px;
      --track-height: 4px;
      --thumb-size: 14px;
    }

    .cam-toggle {
      font-size: 0.6em;
      padding: 0.1em 0.5em;
      margin: 0 8px 0 0;
      min-width: 32px;
      cursor: pointer;
      border: 1px solid;
      border-radius: var(--so-radius);
      background: none;
      font-family: var(--so-font-family);
    }
    .cam-toggle.on {
      color: var(--so-color-ok);
      border-color: var(--so-color-ok);
    }
    .cam-toggle.off {
      color: var(--so-color-danger);
      border-color: var(--so-color-danger);
    }
    .cam-toggle.offline {
      color: var(--so-text-muted);
      border-color: var(--so-border);
      opacity: 0.5;
      cursor: not-allowed;
    }
  `;

  _streamWatchdog = null;

  constructor() {
    super();
    this._camOn = false;
    this._camLoading = false;
    this._hasCamera = false;
    this._active = { mode: "", res: "", fps: "", rotation: "0" };
    this._bright = 58;
    this._zoom = 100;
    this._cssGrayscale = false;
    this._cssInvert = false;
    this._strings = {};
  }

  connectedCallback() {
    super.connectedCallback();
    this._unsubscribe = store.subscribe(() => this._onStoreChange());
    this._onStoreChange();
    this._initStream();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._unsubscribe) this._unsubscribe();
    if (this._streamWatchdog) clearInterval(this._streamWatchdog);
  }

  _onStoreChange() {
    const cam = store.getState().camera;
    const sys = store.getState().system;
    const ui = store.getState().ui;
    this._camOn = cam.camOn;
    this._camLoading = cam.camLoading;
    this._hasCamera = sys.hasCamera;
    this._active = cam.active;
    this._bright = cam.bright;
    this._zoom = cam.zoom;
    this._cssGrayscale = cam.cssGrayscale;
    this._cssInvert = cam.cssInvert;
    this._strings = ui.strings;
  }

  _t(key) {
    return this._strings[key] || key;
  }

  get _streamHost() {
    return location.hostname || "localhost";
  }

  _initStream() {
    const streamEl = document.getElementById("stream");
    if (!streamEl) return;
    const host = this._streamHost;
    if (this._camOn) {
      streamEl.src = `http://${host}:8080/?action=stream`;
      streamEl.style.display = "";
    }
    streamEl.addEventListener("error", () => {
      if (store.getState().camera.camOn) {
        store.dispatch(setStreamStats("Stream error — reconnecting..."));
        setTimeout(() => {
          streamEl.src = `http://${host}:8080/?action=stream&t=${Date.now()}`;
        }, 1000);
      }
    });
    let staleCount = 0;
    this._streamWatchdog = setInterval(() => {
      if (!store.getState().camera.camOn) return;
      if (streamEl.naturalWidth === 0 && streamEl.style.display !== "none") {
        staleCount++;
        if (staleCount >= 2) {
          streamEl.src = `http://${host}:8080/?action=stream&t=${Date.now()}`;
          staleCount = 0;
        }
      } else {
        staleCount = 0;
      }
    }, 5000);
    this._applyFilters();
  }

  _camCtl(action) {
    store.dispatch(setCamLoading(true));
    store.dispatch(setStatus(`Camera: ${action}...`));
    if (action === "start" || action === "restart")
      store.dispatch(
        setServiceState({ name: "mjpg-streamer", status: "activating" }),
      );
    else if (action === "stop")
      store.dispatch(
        setServiceState({ name: "mjpg-streamer", status: "deactivating" }),
      );
    fetch(`/api?cmd=camctl+${action}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        store.dispatch(setStatus(d.output || "Done"));
        if (action === "stop") {
          store.dispatch(setCamOn(false));
          store.dispatch(setCamLoading(false));
          const el = document.getElementById("stream");
          if (el) el.style.display = "none";
        } else {
          this._countdown(3);
        }
      })
      .catch((e) => {
        store.dispatch(setStatus("Error: " + e));
        store.dispatch(setCamLoading(false));
      });
  }

  _cmd(c) {
    store.dispatch(setStatus(`Applying: ${c}...`));
    fetch(`/api?cmd=${encodeURIComponent(c)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        store.dispatch(setStatus(d.output || "Done"));
        if (["day", "night", "indoor"].includes(c))
          store.dispatch(setActive({ mode: c }));
        let m;
        if ((m = c.match(/^res (\w+)/)))
          store.dispatch(setActive({ res: m[1] }));
        if ((m = c.match(/^rotate (\d+)/)))
          store.dispatch(setActive({ rotation: m[1] }));
        if ((m = c.match(/^fps (\d+)/)))
          store.dispatch(setActive({ fps: m[1] }));
        if (
          c.startsWith("res ") ||
          c.startsWith("rotate ") ||
          c.startsWith("fps ") ||
          c === "day" ||
          c === "night" ||
          c === "indoor"
        )
          this._countdown(5);
      })
      .catch((e) => {
        store.dispatch(setStatus("Error: " + e));
      });
  }

  _countdown(sec) {
    let left = sec;
    const iv = setInterval(() => {
      store.dispatch(setStatus(`Refreshing stream in ${left}s...`));
      left--;
      if (left < 0) {
        clearInterval(iv);
        store.dispatch(setStatus("Connecting to stream..."));
        this._tryLoadStream(0);
      }
    }, 1000);
  }

  _tryLoadStream(attempt) {
    const base = `http://${this._streamHost}:8080/`;
    fetch(`${base}?action=snapshot&t=${Date.now()}`, { mode: "no-cors" })
      .then(() => {
        const el = document.getElementById("stream");
        if (el) el.src = `${base}?action=stream&t=${Date.now()}`;
        store.dispatch(setCamOn(true));
        store.dispatch(setCamLoading(false));
        store.dispatch(setStatus(""));
      })
      .catch(() => {
        if (attempt < 10)
          setTimeout(() => this._tryLoadStream(attempt + 1), 2000);
        else {
          store.dispatch(setStatus("Stream unavailable"));
          store.dispatch(setCamLoading(false));
        }
      });
  }

  _onBrightChange(e) {
    const val = parseInt(e.target.value);
    store.dispatch(setBright(val));
    this._cmd("bright " + val);
  }

  _onZoomChange(e) {
    const val = parseInt(e.target.value);
    store.dispatch(setZoom(val));
    this._cmd("zoom " + val);
  }

  _toggleGrayscale() {
    store.dispatch(setCssGrayscale(!this._cssGrayscale));
    setTimeout(() => this._applyFilters(), 0);
  }

  _toggleInvert() {
    store.dispatch(setCssInvert(!this._cssInvert));
    setTimeout(() => this._applyFilters(), 0);
  }

  _applyFilters() {
    const el = document.getElementById("stream");
    if (!el) return;
    const cam = store.getState().camera;
    const f = [];
    if (cam.cssGrayscale) f.push("grayscale(1)");
    if (cam.cssInvert) f.push("invert(1)");
    el.style.filter = f.length ? f.join(" ") : "none";
  }

  _camToggleLabel() {
    if (!this._hasCamera) return this._t("offline");
    if (this._camLoading) return "...";
    return this._camOn ? this._t("on") : this._t("off");
  }

  _camToggleClass() {
    if (!this._hasCamera) return "cam-toggle offline";
    return this._camOn ? "cam-toggle on" : "cam-toggle off";
  }

  renderHeaderToggle() {
    return html`
      <button
        class=${this._camToggleClass()}
        @click=${(e) => {
          e.stopPropagation();
          if (this._hasCamera) this._camCtl(this._camOn ? "stop" : "start");
        }}
        ?disabled=${this._camLoading || !this._hasCamera}
      >
        ${this._camToggleLabel()}
      </button>
    `;
  }

  render() {
    return html`
      <div class=${this._camOn ? "" : "controls-disabled"}>
        <div class="setting-row">
          <span class="label">${this._t("mode")}</span>
          <sl-button-group>
            ${["day", "night"].map(
              (m) => html`
                <sl-button
                  size="small"
                  .variant=${this._active.mode === m ? "primary" : "default"}
                  @click=${() => this._cmd(m)}
                >
                  ${m[0].toUpperCase() + m.slice(1)}
                </sl-button>
              `,
            )}
          </sl-button-group>
        </div>
        <div class="setting-row">
          <span class="label">${this._t("resolution")}</span>
          <sl-button-group>
            ${[
              { val: "low", label: "480p" },
              { val: "mid", label: "720p" },
              { val: "high", label: "1080p" },
            ].map(
              (r) => html`
                <sl-button
                  size="small"
                  .variant=${this._active.res === r.val ? "primary" : "default"}
                  @click=${() => this._cmd("res " + r.val)}
                >
                  ${r.label}
                </sl-button>
              `,
            )}
          </sl-button-group>
        </div>
        <div class="setting-row">
          <span class="label">${this._t("fps")}</span>
          <sl-button-group>
            ${["5", "10", "15", "24", "30"].map(
              (f) => html`
                <sl-button
                  size="small"
                  .variant=${this._active.fps === f ? "primary" : "default"}
                  @click=${() => this._cmd("fps " + f)}
                >
                  ${f}
                </sl-button>
              `,
            )}
          </sl-button-group>
        </div>
        <div class="setting-row">
          <span class="label"
            >${this._t("brightness")} <small>${this._bright}</small></span
          >
          <sl-range
            min="0"
            max="100"
            .value=${this._bright}
            @sl-change=${this._onBrightChange}
          ></sl-range>
        </div>
        <div class="setting-row">
          <span class="label">${this._t("rotation")}</span>
          <sl-button-group>
            ${["0", "90", "180", "270"].map(
              (r) => html`
                <sl-button
                  size="small"
                  .variant=${this._active.rotation === r
                    ? "primary"
                    : "default"}
                  @click=${() => this._cmd("rotate " + r)}
                >
                  ${r}&deg;
                </sl-button>
              `,
            )}
          </sl-button-group>
        </div>
        <div class="setting-row">
          <span class="label"
            >${this._t("zoom")} <small>${this._zoom}</small></span
          >
          <sl-range
            min="100"
            max="500"
            step="10"
            .value=${this._zoom}
            @sl-change=${this._onZoomChange}
          ></sl-range>
        </div>
        <div class="setting-row">
          <span class="label">${this._t("filters")}</span>
          <sl-button-group>
            <sl-button
              size="small"
              .variant=${this._cssGrayscale ? "primary" : "default"}
              @click=${this._toggleGrayscale}
            >
              ${this._t("grayscale")}
            </sl-button>
            <sl-button
              size="small"
              .variant=${this._cssInvert ? "primary" : "default"}
              @click=${this._toggleInvert}
            >
              ${this._t("invert")}
            </sl-button>
          </sl-button-group>
        </div>
      </div>
    `;
  }
}

customElements.define("camera-content", CameraContent);
