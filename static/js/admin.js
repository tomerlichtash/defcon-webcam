/* Admin panel module — cookie-based auth (backend OAuth) */
var AdminModule = {
  state: {
    adminAuth: false,
    adminAuthError: "",
    adminConfig: {},
  },

  adminAuthHeaders() {
    return { "Content-Type": "application/json" };
  },

  adminVerifyAndLoad() {
    this.adminFetch("/admin/api?cmd=verify")
      .then((d) => {
        if (!d) return;
        this.adminAuth = true;
        this.adminConfig = d.admin_config || {};
        this.adminStartRefreshTimer();
      })
      .catch(() => {
        this.adminLogout();
      });
  },

  async adminTryRefresh() {
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
  },

  /* Wrapper: fetch admin API with auto-refresh on 401 */
  async adminFetch(url, opts) {
    opts = opts || {};
    opts.headers = this.adminAuthHeaders();
    const r = await fetch(url, opts);
    if (r.status === 401) {
      const ok = await this.adminTryRefresh();
      if (!ok) {
        this.adminLogout();
        return null;
      }
      opts.headers = this.adminAuthHeaders();
      const r2 = await fetch(url, opts);
      return r2.ok ? r2.json() : null;
    }
    return r.json();
  },

  adminStartRefreshTimer() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
    this._refreshTimer = setInterval(() => {
      if (this.adminAuth) this.adminTryRefresh();
    }, 120000);
  },

  adminLogout() {
    this.adminAuth = false;
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
    document.cookie = "admin_session=; path=/; max-age=0";
    document.cookie = "admin_refresh=; path=/; max-age=0";
    window.location.href = "/login";
  },
};
