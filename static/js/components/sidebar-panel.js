/* Stars Outside — generic sidebar panel (sl-details accordion + slot) */
import { LitElement, html, css } from "lit";
import { store, togglePanel } from "../store.js";

export class SidebarPanel extends LitElement {
  static properties = {
    name: { type: String },
    titleKey: { type: String, attribute: "title-key" },
    _open: { state: true },
    _title: { state: true },
  };

  static styles = css`
    :host {
      display: block;
    }

    sl-details {
      --header-padding: 10px 12px;
    }

    sl-details::part(header) {
      font-size: 0.78em;
      text-transform: uppercase;
      font-weight: bold;
      letter-spacing: 0.03em;
      padding: 10px 12px;
      color: var(--so-text);
      border-bottom: 1px solid var(--so-border-light);
    }

    sl-details::part(header):hover {
      color: var(--so-color-blue);
    }

    sl-details::part(base) {
      border: none;
      border-radius: 0;
      background: none;
    }

    sl-details::part(content) {
      padding: var(--so-space-sm) var(--so-space-md);
    }

    sl-details::part(summary-icon) {
      color: var(--so-text-muted);
    }
  `;

  _syncing = false;

  constructor() {
    super();
    this._open = false;
    this._title = "";
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
    const shouldBeOpen = state.ui.panels[this.name] ?? false;
    this._title = state.ui.strings[this.titleKey] || this.titleKey;
    if (this._open !== shouldBeOpen) {
      this._syncing = true;
      this._open = shouldBeOpen;
      this.updateComplete.then(() => {
        requestAnimationFrame(() => {
          this._syncing = false;
        });
      });
    }
  }

  _onShow(e) {
    if (this._syncing) return;
    e.preventDefault();
    store.dispatch(togglePanel(this.name));
  }

  _onHide(e) {
    if (this._syncing) return;
    e.preventDefault();
    store.dispatch(togglePanel(this.name));
  }

  render() {
    return html`
      <sl-details
        ?open=${this._open}
        @sl-show=${this._onShow}
        @sl-hide=${this._onHide}
      >
        <span slot="summary"
          ><slot name="header-extra"></slot> ${this._title}</span
        >
        <slot></slot>
      </sl-details>
    `;
  }
}

customElements.define("sidebar-panel", SidebarPanel);
