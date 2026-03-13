/* Stars Outside — EffectsManager (confetti + quote trivia) */
import { store } from "./store.js";

export class EffectsManager {
  constructor() {
    this._positiveMsgTimer = null;
    this._lastLevel = store.getState().defcon.level;

    store.subscribe(() => {
      const level = store.getState().defcon.level;
      if (level !== this._lastLevel) {
        const prev = this._lastLevel;
        this._lastLevel = level;
        if (prev && prev !== level) {
          if (level === 5) this.fireConfetti();
          if (level === 2) this.showPositiveMessages();
          if (level !== 2) this.stopPositiveMessages();
        }
      }
    });
  }

  fireConfetti() {
    if (typeof ConfettiGenerator === "undefined") return;
    this.stopPositiveMessages();
    document.querySelectorAll(".positive-msg-el").forEach((el) => el.remove());

    const canvas = document.createElement("canvas");
    canvas.style.cssText =
      "position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;";
    document.body.appendChild(canvas);
    const confetti = new ConfettiGenerator({
      target: canvas,
      max: 150,
      animate: true,
      clock: 30,
      rotate: true,
      colors: [
        [255, 215, 0],
        [0, 200, 100],
        [70, 130, 255],
        [255, 80, 80],
        [255, 255, 255],
      ],
    });
    confetti.render();
    setTimeout(() => {
      confetti.clear();
      canvas.remove();
    }, 6000);
  }

  showPositiveMessages() {
    this.stopPositiveMessages();
    document.querySelectorAll(".positive-msg-el").forEach((el) => el.remove());
    this._showNextQuote();
  }

  _showNextQuote() {
    const level = store.getState().defcon.level;
    if (level !== 2) {
      this._positiveMsgTimer = null;
      return;
    }
    const locale = store.getState().ui.locale;
    const lang = locale === "he" ? "he" : "en";
    fetch(`/api?cmd=quote&lang=${lang}`)
      .then((r) => r.json())
      .then((d) => {
        if (!d.quote) return;
        document
          .querySelectorAll(".positive-msg-el")
          .forEach((el) => el.remove());

        const el = document.createElement("div");
        el.className = "positive-msg-el";
        const x = 10 + Math.random() * 70;
        const y = 20 + Math.random() * 50;
        el.style.cssText = `position:fixed;left:${x}%;top:${y}%;z-index:99999;color:#fff;font-size:1.4em;font-weight:bold;background:rgba(0,0,0,0.6);padding:12px 20px;border-radius:10px;cursor:pointer;max-width:420px;text-align:center;line-height:1.4;`;

        const quoteEl = document.createElement("div");
        quoteEl.textContent = "\u201c" + d.quote + "\u201d";
        el.appendChild(quoteEl);

        const sourceEl = document.createElement("div");
        sourceEl.style.cssText =
          "margin-top:8px;font-size:0.7em;opacity:0;transition:opacity 0.3s;color:#ffd700;";
        el.appendChild(sourceEl);

        const tapHint = document.createElement("div");
        tapHint.textContent =
          locale === "he"
            ? "\u05dc\u05d7\u05e6\u05d5 \u05dc\u05d2\u05dc\u05d5\u05ea"
            : "tap to reveal";
        tapHint.style.cssText =
          "margin-top:6px;font-size:0.55em;opacity:0.5;font-weight:normal;";
        el.appendChild(tapHint);

        el.addEventListener("click", () => {
          if (sourceEl.style.opacity === "1") return;
          fetch(`/api?cmd=reveal&lang=${lang}&id=${d.id}`)
            .then((r) => r.json())
            .then((rv) => {
              if (rv.source) {
                sourceEl.textContent = "\u2014 " + rv.source;
                sourceEl.style.opacity = "1";
                tapHint.style.display = "none";
              }
            });
        });

        const slideFrom = locale === "he" ? "30px" : "-30px";
        el.animate(
          [
            { opacity: 0, transform: `translateX(${slideFrom})` },
            { opacity: 1, transform: "translateX(0)", offset: 0.03 },
            { opacity: 1, transform: "translateX(0)", offset: 0.97 },
            { opacity: 0, transform: "translateX(0)" },
          ],
          { duration: 10000, fill: "forwards", easing: "ease-out" },
        );

        document.body.appendChild(el);
        this._positiveMsgTimer = setTimeout(() => this._showNextQuote(), 11000);
      })
      .catch(() => {
        this._positiveMsgTimer = setTimeout(() => this._showNextQuote(), 11000);
      });
  }

  stopPositiveMessages() {
    if (this._positiveMsgTimer) {
      clearTimeout(this._positiveMsgTimer);
      this._positiveMsgTimer = null;
    }
  }
}
