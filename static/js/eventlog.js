/* Event log panel module — load more, filtering */
var EventLogModule = {
  state: {
    eventLog: [],
    eventTotal: 0,
    loadingMore: false,
    filters: JSON.parse(
      localStorage.getItem("filters") ||
        '{"alerts":true,"scans":true,"status":true,"system":true}',
    ),
  },

  get aggLog() {
    const typeMap = {
      alerts: "alert",
      scans: "scan",
      status: "status",
      system: "system",
    };
    const activeTypes = {};
    Object.keys(this.filters).forEach((k) => {
      if (this.filters[k]) activeTypes[typeMap[k]] = true;
    });
    return this.eventLog.filter((e) => activeTypes[e._type]).slice(0, 200);
  },

  initEventLog() {
    this.$watch(
      "filters",
      (val) => {
        localStorage.setItem("filters", JSON.stringify(val));
      },
      { deep: true },
    );
  },

  loadEventLog() {
    let url = "/api?cmd=eventlog";
    if (this.eventLog.length > 0)
      url += "&since=" + encodeURIComponent(this.eventLog[0].time);
    fetch(url)
      .then((r) => r.json())
      .then((d) => {
        const newEvents = d.log || [];
        this.eventTotal = d.total || 0;
        this._applyDefcon(d.defcon);
        if (this.eventLog.length === 0) this.eventLog = newEvents;
        else if (newEvents.length > 0)
          this.eventLog = newEvents.concat(this.eventLog);
      })
      .catch((e) => {
        console.warn("loadEventLog failed:", e);
      });
  },

  loadMore() {
    this.loadingMore = true;
    fetch(`/api?cmd=eventlog&offset=${this.eventLog.length}`)
      .then((r) => r.json())
      .then((d) => {
        this.eventLog = this.eventLog.concat(d.log || []);
        this.eventTotal = d.total || 0;
        this.loadingMore = false;
      })
      .catch(() => {
        this.loadingMore = false;
      });
  },
};
