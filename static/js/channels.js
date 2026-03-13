/* Channels panel module — publish to Telegram/Twitter */
var ChannelsModule = {
  state: {
    pubTelegram: localStorage.getItem("pubTelegram") !== "false",
    pubTwitter: localStorage.getItem("pubTwitter") === "true",
    pubStatus: "",
  },

  initChannels() {
    this.$watch("pubTelegram", (val) => {
      localStorage.setItem("pubTelegram", val);
    });
    this.$watch("pubTwitter", (val) => {
      localStorage.setItem("pubTwitter", val);
    });
  },
  publish() {
    const targets = [];
    if (this.pubTelegram) targets.push("telegram");
    if (this.pubTwitter) targets.push("twitter");
    if (targets.length === 0) {
      this.pubStatus = "Select at least one target";
      return;
    }
    this.pubStatus = `Publishing to ${targets.join(", ")}...`;
    fetch("/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ targets: targets, caption: this.siteName }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then((d) => {
        const results = d.results || {};
        this.pubStatus =
          Object.keys(results)
            .map((k) => `${k}: ${results[k]}`)
            .join(", ") || "Done";
      })
      .catch((e) => {
        this.pubStatus = "Error: " + e;
      });
  },
};
