/* Stars Outside — top bar component */
import { LitElement, html, css } from "lit";
import {
  store,
  selectSiteName,
  selectDefconLabel,
  setTheme,
  setLocale,
  setStrings,
  toggleSidebar,
} from "../store.js";

export class TopBar extends LitElement {
  static properties = {
    admin: { type: Boolean },
    _defconLevel: { state: true },
    _defconLabel: { state: true },
    _siteName: { state: true },
    _status: { state: true },
    _theme: { state: true },
    _locale: { state: true },
    _simulating: { state: true },
    _simCount: { state: true },
    _sidebarOpen: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1100;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      background: var(--so-topbar-bg);
      border-bottom: 1px solid var(--so-topbar-border);
    }

    nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 2px 12px 0;
    }

    .left,
    .right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .site-title {
      text-transform: uppercase;
      font-weight: bold;
    }

    .separator {
      margin: 0 2px;
    }

    .defcon-label {
      display: inline-block;
      font-weight: 300;
      color: var(--so-color-blue);
    }

    .defcon-label.defcon4 {
      color: var(--so-color-green);
    }

    .defcon-label.siren {
      color: var(--so-color-red);
      animation: siren-glow 1.5s ease-in-out infinite alternate;
      filter: drop-shadow(0 0 5px var(--so-color-red));
    }

    @keyframes siren-glow {
      from {
        filter: drop-shadow(0 0 5px var(--so-color-red));
        opacity: 1;
      }
      to {
        filter: drop-shadow(0 0 20px var(--so-color-red))
          drop-shadow(0 0 40px var(--so-color-red));
        opacity: 0.85;
      }
    }

    .status-bar {
      font-size: var(--so-font-size-xs);
      font-weight: normal;
      color: var(--so-text-muted);
      margin-left: 10px;
    }

    /* Shoelace overrides for compact top-bar sizing */
    sl-button::part(base) {
      font-size: var(--so-font-size-sm);
      height: auto;
      min-height: 0;
      padding: 2px 8px;
      line-height: 1.4;
    }

    sl-button-group sl-button::part(base) {
      padding: 2px 6px;
    }

    sl-switch {
      --sl-toggle-size-small: 14px;
    }

    sl-switch::part(label) {
      font-size: var(--so-font-size-sm);
      padding-inline-start: 4px;
    }

    .menu-btn {
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border: none;
      background: none;
      color: var(--so-text);
      border-radius: var(--so-radius);
      transition: background 0.15s;
    }

    .menu-btn:hover {
      background: var(--so-border-light);
    }

    .menu-btn svg {
      width: 18px;
      height: 18px;
    }
  `;

  constructor() {
    super();
    this.admin = false;
    this._defconLevel = 5;
    this._defconLabel = "ALL CLEAR";
    this._siteName = "Stars Outside";
    this._status = "";
    this._theme = "dark";
    this._locale = "he";
    this._simulating = false;
    this._simCount = 100;
    this._sidebarOpen = false;
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
    const state = store.getState();
    this._defconLevel = state.defcon.level;
    this._defconLabel = selectDefconLabel(state);
    this._siteName = selectSiteName(state);
    this._status = state.ui.status;
    this._theme = state.ui.theme;
    this._locale = state.ui.locale;
    this._simulating = state.ui.simulating;
    this._simCount = state.ui.simCount;
    this._sidebarOpen = state.ui.sidebarOpen;
  }

  _onThemeSwitch(e) {
    const newTheme = e.target.checked ? "dark" : "light";
    store.dispatch(setTheme(newTheme));
    document.documentElement.setAttribute("data-theme", newTheme);
  }

  async _setLocale(locale) {
    if (locale === this._locale) return;
    store.dispatch(setLocale(locale));
    document.documentElement.setAttribute(
      "dir",
      locale === "he" ? "rtl" : "ltr",
    );
    try {
      const r = await fetch(`/static/i18n/${locale}.json`);
      const strings = await r.json();
      store.dispatch(setStrings(strings));
    } catch {
      /* fallback: keep current strings */
    }
  }

  _toggleSidebar() {
    store.dispatch(toggleSidebar());
  }

  _simulate() {
    /* Dispatch event for app.js to handle (it has MapManager reference) */
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

  _defconClass() {
    if (this._defconLevel === 2) return "defcon-label siren";
    if (this._defconLevel === 4) return "defcon-label defcon4";
    return "defcon-label";
  }

  render() {
    const strings = store.getState().ui.strings;
    return html`
      <nav>
        <div class="left">
          ${this.admin
            ? html`
                <button
                  class="menu-btn"
                  @click=${this._toggleSidebar}
                  title="Toggle sidebar"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                  >
                    <line x1="3" y1="6" x2="21" y2="6" />
                    <line x1="3" y1="12" x2="21" y2="12" />
                    <line x1="3" y1="18" x2="21" y2="18" />
                  </svg>
                </button>
              `
            : ""}
          <strong class="site-title">${this._siteName}</strong>
          <span class="separator">&nbsp;|&nbsp;</span>
          <span class=${this._defconClass()}>${this._defconLabel}</span>
          ${this._status
            ? html`<span class="status-bar">${this._status}</span>`
            : ""}
        </div>
        <div class="right">
          ${this.admin
            ? html`
                <sl-button
                  size="small"
                  @click=${this._simulate}
                  style=${this._defconLevel === 2 ? "display:none" : ""}
                >
                  ${strings.simulate || "Simulate"}
                </sl-button>
                ${this._simulating && this._defconLevel === 2
                  ? html`
                      <sl-button
                        size="small"
                        variant="danger"
                        @click=${this._clearSimulation}
                        >Clear</sl-button
                      >
                    `
                  : ""}
              `
            : ""}
          <sl-button-group>
            <sl-button
              size="small"
              variant=${this._locale === "he" ? "primary" : "default"}
              @click=${() => this._setLocale("he")}
              >עב</sl-button
            >
            <sl-button
              size="small"
              variant=${this._locale === "en" ? "primary" : "default"}
              @click=${() => this._setLocale("en")}
              >EN</sl-button
            >
          </sl-button-group>
          <sl-switch
            size="small"
            ?checked=${this._theme === "dark"}
            @sl-change=${this._onThemeSwitch}
          >
            ${this._theme === "dark" ? "🌙" : "☀️"}
          </sl-switch>
        </div>
      </nav>
    `;
  }
}

customElements.define("top-bar", TopBar);
