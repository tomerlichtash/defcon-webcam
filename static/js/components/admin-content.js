/* Stars Outside — admin panel content (Shoelace primitives) */
import { LitElement, html, css, nothing } from "lit";
import { store, setAdminAuth, setAdminConfig, setSimCount } from "../store.js";

export class AdminContent extends LitElement {
  static properties = {
    _auth: { state: true },
    _simCount: { state: true },
    _simulating: { state: true },
    _defconLevel: { state: true },
    _strings: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      padding: 4px 12px 10px;
    }

    .section-label {
      font-size: 0.65em;
      text-transform: uppercase;
      color: var(--so-text-muted);
      padding: 6px 0 2px;
      border-top: 1px solid var(--so-border-light);
      margin-top: 4px;
      letter-spacing: 0.04em;
    }

    .section-label:first-child {
      border-top: none;
      margin-top: 0;
    }

    .setting-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 0;
      gap: 10px;
      font-size: 0.72em;
    }

    .label {
      color: var(--so-text-muted);
      text-transform: uppercase;
      font-size: 0.85em;
    }

    .inline-controls {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    sl-input {
      width: 70px;
    }

    .logout-btn {
      font-size: 0.65em;
      padding: 0.1em 0.35em;
      margin: 0 0 0 6px;
      color: var(--so-color-danger);
      border: 1px solid var(--so-color-danger);
      border-radius: var(--so-radius);
      background: none;
      cursor: pointer;
      font-family: var(--so-font-family);
    }
    .logout-btn:hover {
      background: var(--so-color-danger);
      color: var(--so-text-on-color);
    }
  `;

  _refreshTimer = null;

  constructor() {
    super();
    this._auth = false;
    this._simCount = 100;
    this._simulating = false;
    this._defconLevel = 5;
    this._strings = {};
  }

  connectedCallback() {
    super.connectedCallback();
    this._unsubscribe = store.subscribe(() => this._onStoreChange());
    this._onStoreChange();
    this._verifyAndLoad();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._unsubscribe) this._unsubscribe();
    if (this._refreshTimer) clearInterval(this._refreshTimer);
  }

  _onStoreChange() {
    const state = store.getState();
    this._auth = state.admin.auth;
    this._simCount = state.ui.simCount;
    this._simulating = state.ui.simulating;
    this._defconLevel = state.defcon.level;
    this._strings = state.ui.strings;
  }

  _t(key) {
    return this._strings[key] || key;
  }

  /* Auth */
  _adminHeaders() {
    return { "Content-Type": "application/json" };
  }

  async _tryRefresh() {
    try {
      const r = await fetch("/admin/api/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      return r.ok;
    } catch {
      return false;
    }
  }

  async _adminFetch(url, opts) {
    opts = opts || {};
    opts.headers = this._adminHeaders();
    const r = await fetch(url, opts);
    if (r.status === 401) {
      const ok = await this._tryRefresh();
      if (!ok) {
        this._logout();
        return null;
      }
      opts.headers = this._adminHeaders();
      const r2 = await fetch(url, opts);
      return r2.ok ? r2.json() : null;
    }
    return r.json();
  }

  async _verifyAndLoad() {
    try {
      const d = await this._adminFetch("/admin/api?cmd=verify");
      if (!d) return;
      store.dispatch(setAdminAuth(true));
      store.dispatch(setAdminConfig(d.admin_config || {}));
      this._startRefreshTimer();
    } catch {
      this._logout();
    }
  }

  _startRefreshTimer() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
    this._refreshTimer = setInterval(() => {
      if (store.getState().admin.auth) this._tryRefresh();
    }, 120000);
  }

  _logout() {
    store.dispatch(setAdminAuth(false));
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
    document.cookie = "admin_session=; path=/; max-age=0";
    document.cookie = "admin_refresh=; path=/; max-age=0";
    window.location.href = "/login";
  }

  /* Simulation */
  _onCountChange(e) {
    store.dispatch(setSimCount(parseInt(e.target.value) || 100));
  }

  _simulate() {
    this.dispatchEvent(
      new CustomEvent("simulate", {
        bubbles: true,
        composed: true,
        detail: { count: this._simCount },
      }),
    );
  }

  _clearSimulation() {
    this.dispatchEvent(
      new CustomEvent("clear-simulation", {
        bubbles: true,
        composed: true,
      }),
    );
  }

  renderLogoutButton() {
    if (!this._auth) return nothing;
    return html`
      <button
        class="logout-btn"
        @click=${(e) => {
          e.stopPropagation();
          this._logout();
        }}
      >
        ${this._t("logout")}
      </button>
    `;
  }

  render() {
    if (!this._auth) return nothing;
    return html`
      <div class="section-label">${this._t("simulate")}</div>
      <div class="setting-row">
        <span class="label">${this._t("cities")}</span>
        <div class="inline-controls">
          <sl-input
            type="number"
            size="small"
            .value=${String(this._simCount)}
            min="1"
            max="1166"
            @sl-change=${this._onCountChange}
          ></sl-input>
          <sl-button
            size="small"
            variant="default"
            outline
            @click=${this._simulate}
            >Go</sl-button
          >
          ${this._simulating && this._defconLevel === 2
            ? html`
                <sl-button
                  size="small"
                  variant="danger"
                  outline
                  @click=${this._clearSimulation}
                  >Clear</sl-button
                >
              `
            : nothing}
        </div>
      </div>
    `;
  }
}

customElements.define("admin-content", AdminContent);
