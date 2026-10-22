/* Scrolling price ticker (main dashboard, coin pages, /trades/). Restored from the classic view's ticker strip.
   Markup: <div class="ticker lt-ticker" ...><div class="ticker-track" id="ticker"></div></div>, placed right under the header.
   Data: data/prices.json snapshot (+ data/coins.json for the live feeds), then live ticks from assets/live.js
   (Coinbase / Kraken websockets, CoinGecko 60s fallback), the same source the classic ticker uses.
   Coin-page links: #coin-pages a[data-coin] (main page) or data-pages="coinid:slug,..." on the ticker element.
   prefers-reduced-motion: no animation, no duplicated items; the strip scrolls by hand instead. */
(() => {
  "use strict";
  const me = document.currentScript;
  const ROOT = me && me.src ? new URL("../", me.src).href : (document.documentElement.dataset.root ?? "");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const SPEED = 42; // px per second
  const reduced = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fmtPrice(p) {
    if (p == null || isNaN(p)) return "—";
    const a = Math.abs(p);
    const d = a >= 1000 ? 0 : a >= 1 ? 3 : a >= 0.1 ? 4 : a >= 0.01 ? 5 : 6;
    return "$" + Number(p).toLocaleString("en-US", { minimumFractionDigits: Math.min(d, 2), maximumFractionDigits: d });
  }
  function chg(v) {
    const ok = v != null && !isNaN(v);
    const cls = !ok ? "flat" : v > 0 ? "up" : v < 0 ? "down" : "flat";
    const arrow = cls === "up" ? "▲" : cls === "down" ? "▼" : "•";
    return `<span class="tk-chg ${cls}"><i aria-hidden="true">${arrow}</i>${ok ? `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%` : "n/a"}</span>`;
  }
  function spark(history) {
    const pts = (history || []).slice(-168).map((p) => p[1]).filter((v) => v != null);
    if (pts.length < 2) return "";
    const step = Math.max(1, Math.floor(pts.length / 40));
    const ys = pts.filter((_, i) => i % step === 0 || i === pts.length - 1);
    const w = 46, h = 16, lo = Math.min(...ys), hi = Math.max(...ys), rng = hi - lo || 1;
    const d = ys.map((v, i) => `${i ? "L" : "M"}${((i / (ys.length - 1)) * w).toFixed(1)} ${(h - 2 - ((v - lo) / rng) * (h - 4)).toFixed(1)}`).join("");
    return `<svg class="tk-spark ${ys[ys.length - 1] >= ys[0] ? "up" : "down"}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><path d="${d}"/></svg>`;
  }
  const get = (n) => fetch(`${ROOT}data/${n}?t=${Math.floor(Date.now() / 6e4)}`, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(n + ": " + r.status); return r.json(); });

  function pageMap(box) {
    const m = {};
    document.querySelectorAll("#coin-pages a[data-coin]").forEach((a) => (m[a.dataset.coin] = a.getAttribute("href")));
    (box.dataset.pages || "").split(",").forEach((x) => { const [id, slug] = x.split(":"); if (id && slug && !m[id]) m[id] = ROOT + slug + "/"; });
    return m;
  }

  async function init() {
    const track = document.getElementById("ticker");
    const box = track && track.closest(".lt-ticker");
    if (!box) return;
    let prices, coincfg;
    try { [prices, coincfg] = await Promise.all([get("prices.json"), get("coins.json").catch(() => null)]); }
    catch (e) { box.hidden = true; return; }
    const order = (prices.groups && prices.groups.length ? prices.groups.flatMap((g) => g.coins) : prices.coins || []).concat(prices.coins || []);
    const ids = [...new Set(order)].filter((id) => prices.assets[id]);
    if (!ids.length) { box.hidden = true; return; }
    const pages = pageMap(box);
    const item = (id, dup) => {
      const a = prices.assets[id], href = pages[id];
      const tag = href ? "a" : "span";
      const attrs = (href ? ` href="${esc(href)}"` : "") + (dup ? ' aria-hidden="true" tabindex="-1"' : "") +
        (href && !dup ? ` aria-label="${esc(a.symbol)} analysis"` : "");
      return `<${tag} class="tk${dup ? " dup" : ""}"${attrs}><span class="s">${esc(a.symbol)}</span><span class="p" data-tp="${esc(id)}">${fmtPrice(a.price)}</span><span data-tc="${esc(id)}">${chg(a.change_24h)}</span>${spark(a.history)}</${tag}>`;
    };
    const half = ids.map((i) => item(i, false)).join("");
    track.innerHTML = reduced() ? half : half + ids.map((i) => item(i, true)).join("");
    const setDur = () => { const w = track.scrollWidth / (reduced() ? 1 : 2); track.style.setProperty("--tk-dur", Math.max(20, Math.round(w / SPEED)) + "s"); };
    setDur();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(setDur);
    let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(setDur, 250); });
    box.classList.add("ready");

    // live ticks (same feeds as the classic view)
    if (window.Live && !Live.started) {
      const feeds = (coincfg && coincfg.coins || []).filter((c) => prices.assets[c.id]);
      if (feeds.length) Live.configure(feeds);
      const lastDom = {}, prev = {};
      Live.on((t) => {
        if (!prices.assets[t.id]) return;
        const now = performance.now();
        if (lastDom[t.id] && now - lastDom[t.id] < 400) return;
        lastDom[t.id] = now;
        const old = prev[t.id] ?? prices.assets[t.id].price; prev[t.id] = t.price;
        const dir = t.price > old ? "tk-up" : t.price < old ? "tk-down" : "";
        track.querySelectorAll(`[data-tp="${t.id}"]`).forEach((e) => {
          e.textContent = fmtPrice(t.price);
          if (dir && !reduced()) { e.classList.remove("tk-up", "tk-down"); void e.offsetWidth; e.classList.add(dir); }
        });
        if (t.change24 != null) track.querySelectorAll(`[data-tc="${t.id}"]`).forEach((e) => (e.innerHTML = chg(t.change24)));
      });
      Live.start();
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
