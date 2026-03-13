/* Stars Outside — event log panel content (Shoelace primitives) */
import { LitElement, html, css, nothing } from "lit";
import {
  store,
  selectAggLog,
  toggleFilter,
  setLoadingMore,
  appendEntries,
  setTotal,
  toggleEntryOpen,
} from "../store.js";

export class EventlogContent extends LitElement {
  static properties = {
    _aggLog: { state: true },
    _filters: { state: true },
    _total: { state: true },
    _entryCount: { state: true },
    _loadingMore: { state: true },
    _strings: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      padding: 0 8px 8px;
    }

    .filters {
      display: flex;
      gap: 4px;
      padding: 6px 0 4px;
    }

    .log-entries {
      max-height: 300px;
      overflow-y: auto;
    }

    .log-entry {
      padding: 0.3em 0;
      border-bottom: 1px solid var(--so-border-light);
      cursor: pointer;
      display: grid;
      grid-template-columns: 4px 1fr;
      align-items: center;
      gap: 0 10px;
      font-size: 0.6em;
      font-weight: 400;
      color: var(--so-text);
    }

    .log-entry:last-child {
      border-bottom: none;
    }

    .log-entry::before {
      content: "";
      width: 4px;
      border-radius: 2px;
      align-self: stretch;
    }

    .log-entry.type-alert::before {
      background: var(--so-color-danger);
    }
    .log-entry.type-scan::before {
      background: var(--so-color-blue);
    }
    .log-entry.type-status::before {
      background: var(--so-color-ok);
    }
    .log-entry.type-system::before {
      background: var(--so-color-warn);
    }

    .log-source {
      color: var(--so-text-muted);
    }

    .log-entry pre {
      margin: 0.3em 0 0;
      font-size: 0.9em;
      white-space: pre-wrap;
      word-break: break-all;
      grid-column: 1 / -1;
      font-family: monospace;
    }

    .load-more {
      text-align: center;
      padding: 8px 0;
    }

    .empty {
      font-size: 0.75em;
      color: var(--so-text-muted);
      padding: 8px 0;
    }
  `;

  constructor() {
    super();
    this._aggLog = [];
    this._filters = {};
    this._total = 0;
    this._entryCount = 0;
    this._loadingMore = false;
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
    const state = store.getState();
    this._aggLog = selectAggLog(state);
    this._filters = state.eventlog.filters;
    this._total = state.eventlog.total;
    this._entryCount = state.eventlog.entries.length;
    this._loadingMore = state.eventlog.loadingMore;
    this._strings = state.ui.strings;
  }

  _t(key) {
    return this._strings[key] || key;
  }

  _toggleFilter(key) {
    store.dispatch(toggleFilter(key));
  }

  _loadMore() {
    store.dispatch(setLoadingMore(true));
    fetch(`/api?cmd=eventlog&offset=${this._entryCount}`)
      .then((r) => r.json())
      .then((d) => {
        store.dispatch(appendEntries(d.log || []));
        store.dispatch(setTotal(d.total || 0));
        store.dispatch(setLoadingMore(false));
      })
      .catch(() => {
        store.dispatch(setLoadingMore(false));
      });
  }

  _toggleEntry(idx) {
    store.dispatch(toggleEntryOpen(idx));
  }

  _badgeVariant(defcon) {
    const s = String(defcon);
    if (s.includes("2")) return "danger";
    if (s.includes("4")) return "success";
    return "primary";
  }

  _renderEntry(e, idx) {
    return html`
      <div
        class="log-entry type-${e._type}"
        @click=${() => this._toggleEntry(idx)}
      >
        <span class="log-content">
          ${e._type === "alert"
            ? html`
                <sl-badge variant=${this._badgeVariant(e.defcon)}>
                  ${typeof e.defcon === "number"
                    ? "DEFCON " + e.defcon
                    : e.defcon}
                </sl-badge>
              `
            : ""}
          ${e._type === "scan"
            ? html`
                <span
                  >${(e.source || "scan") +
                  " (" +
                  (e.result || "clear") +
                  ")"}</span
                >
              `
            : ""}
          ${e._type === "status" ? html`<span>${e.message}</span>` : ""}
          ${e._type === "system"
            ? html` <span><strong>${e.label}</strong> ${e.value}</span> `
            : ""}
          ${e.source && e._type !== "scan"
            ? html` <span class="log-source">${e.source}</span> `
            : ""}
        </span>
        ${e._open && (e.raw || e.data)
          ? html`
              <pre>${e.raw ? JSON.stringify(e.raw, null, 2) : e.data}</pre>
            `
          : nothing}
      </div>
    `;
  }

  render() {
    const filterKeys = ["alerts", "scans", "status", "system"];
    return html`
      <div class="filters">
        <sl-button-group>
          ${filterKeys.map(
            (k) => html`
              <sl-button
                size="small"
                pill
                .variant=${this._filters[k] ? "primary" : "default"}
                @click=${() => this._toggleFilter(k)}
              >
                ${this._t(k)}
              </sl-button>
            `,
          )}
        </sl-button-group>
      </div>
      <div class="log-entries">
        ${this._aggLog.length === 0
          ? html`<p class="empty"><small>No events recorded</small></p>`
          : this._aggLog.map((e, i) => this._renderEntry(e, i))}
      </div>
      ${this._entryCount < this._total
        ? html`
            <div class="load-more">
              <sl-button
                size="small"
                variant="default"
                outline
                @click=${this._loadMore}
                ?loading=${this._loadingMore}
              >
                ${this._loadingMore ? "Loading..." : "Load More"}
              </sl-button>
            </div>
          `
        : nothing}
    `;
  }
}

customElements.define("eventlog-content", EventlogContent);
