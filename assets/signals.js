/* Client-side signals: same indicators & scoring as scripts/signals.py (keep in sync).
   Candles: Coinbase Exchange REST (BTC/XRP/XLM/HBAR/AXL), Kraken OHLC (ZBCN); CoinGecko market_chart fallback. */
(() => {
  "use strict";
  const COINS = [
    ["bitcoin", "BTC", "coinbase", "BTC-USD"], ["hedera-hashgraph", "HBAR", "coinbase", "HBAR-USD"],
    ["stellar", "XLM", "coinbase", "XLM-USD"], ["ripple", "XRP", "coinbase", "XRP-USD"],
    ["zebec-network", "ZBCN", "kraken", "ZBCNUSD"], ["axelar", "AXL", "coinbase", "AXL-USD"],
  ];
  const TF_WEIGHTS = { "1h": 0.25, "4h": 0.35, "1d": 0.4 };
  const REFRESH_MS = 3 * 60000;
  const label = (s) => (s == null ? "n/a" : s >= 0.5 ? "Strong Buy" : s >= 0.15 ? "Buy" : s > -0.15 ? "Neutral" : s > -0.5 ? "Sell" : "Strong Sell");

  const getJ = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(`${r.status} ${u}`); return r.json(); };
  const coinbase = async (p, g) => (await getJ(`https://api.exchange.coinbase.com/products/${p}/candles?granularity=${g}`)).map((r) => [r[0], r[3], r[2], r[1], r[4], r[5]]).sort((a, b) => a[0] - b[0]);
  async function kraken(pair, iv) {
    const d = await getJ(`https://api.kraken.com/0/public/OHLC?pair=${pair}&interval=${iv}`);
    if (d.error && d.error.length) throw new Error(d.error.join());
    const k = Object.keys(d.result).find((x) => x !== "last");
    return d.result[k].map((r) => [r[0], +r[1], +r[2], +r[3], +r[4], +r[6]]);
  }
  async function coingecko(id, days) {
    const d = await getJ(`https://api.coingecko.com/api/v3/coins/${id}/market_chart?vs_currency=usd&days=${days}`);
    return d.prices.map(([t, p]) => [Math.floor(t / 1000), p, p, p, p, null]);
  }
  function resample(c, secs) {
    const m = new Map();
    for (const [t, o, h, l, cl, v] of c) {
      const k = t - (t % secs);
      const b = m.get(k);
      if (!b) m.set(k, [k, o, h, l, cl, v]);
      else { b[2] = Math.max(b[2], h); b[3] = Math.min(b[3], l); b[4] = cl; b[5] = v == null || b[5] == null ? null : b[5] + v; }
    }
    let rows = [...m.values()].sort((a, b) => a[0] - b[0]);
    if (rows.length > 1 && c.length && c[0][0] % secs) rows = rows.slice(1);
    return rows;
  }
  async function fetchCoin([id, sym, src, prod]) {
    try {
      if (src === "coinbase") { const h1 = await coinbase(prod, 3600); return { source: "Coinbase", tfs: { "1h": h1, "4h": resample(h1, 14400), "1d": await coinbase(prod, 86400) } }; }
      const [a, b, c] = await Promise.all([kraken(prod, 60), kraken(prod, 240), kraken(prod, 1440)]);
      return { source: "Kraken", tfs: { "1h": a, "4h": b, "1d": c } };
    } catch (e) {
      const h = await coingecko(id, 30);
      return { source: "CoinGecko (fallback, no volume)", tfs: { "1h": resample(h, 3600), "4h": resample(h, 14400), "1d": resample(await coingecko(id, 365), 86400) } };
    }
  }

  // ---------- indicators ----------
  function emaS(v, n) {
    const out = Array(v.length).fill(null);
    if (v.length < n) return out;
    const k = 2 / (n + 1);
    let e = v.slice(0, n).reduce((a, b) => a + b, 0) / n;
    out[n - 1] = e;
    for (let i = n; i < v.length; i++) { e = v[i] * k + e * (1 - k); out[i] = e; }
    return out;
  }
  function rsiS(v, n = 14) {
    const out = Array(v.length).fill(null);
    if (v.length <= n) return out;
    const g = [], l = [];
    for (let i = 1; i < v.length; i++) { g.push(Math.max(v[i] - v[i - 1], 0)); l.push(Math.max(v[i - 1] - v[i], 0)); }
    let ag = g.slice(0, n).reduce((a, b) => a + b, 0) / n, al = l.slice(0, n).reduce((a, b) => a + b, 0) / n;
    out[n] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
    for (let i = n + 1; i < v.length; i++) {
      ag = (ag * (n - 1) + g[i - 1]) / n; al = (al * (n - 1) + l[i - 1]) / n;
      out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
    }
    return out;
  }
  const last = (a) => a[a.length - 1];

  function analyze(c, tf) {
    const closes = c.map((x) => x[4]);
    const price = last(closes);
    const res = {}; let pts = 0, mx = 0;
    const rs = rsiS(closes);
    const v = last(rs);
    if (v != null) {
      const p = v <= 30 ? 1 : v >= 70 ? -1 : v >= 50 ? 0.5 : -0.5;
      res.rsi = { value: v, state: v <= 30 ? "oversold" : v >= 70 ? "overbought" : v >= 50 ? "bullish momentum" : "bearish momentum", points: p };
      pts += p; mx += 1;
    }
    const e12 = emaS(closes, 12), e26 = emaS(closes, 26);
    const valid = closes.map((_, i) => (e12[i] != null && e26[i] != null ? e12[i] - e26[i] : null)).filter((x) => x != null);
    if (valid.length >= 12) {
      const sg = emaS(valid, 9);
      const hist = valid.map((m, i) => (sg[i] != null ? m - sg[i] : null));
      const h = last(hist);
      let cross = null;
      for (let i = 1; i <= 3; i++) {
        const a = hist[hist.length - i - 1], b = hist[hist.length - i];
        if (a != null && b != null && ((a <= 0 && b > 0) || (a >= 0 && b < 0))) { cross = b > 0 ? "bullish" : "bearish"; break; }
      }
      const p = (h > 0 ? 1 : -1) + (cross === "bullish" ? 0.5 : cross === "bearish" ? -0.5 : 0);
      res.macd = { value: last(valid), signal: last(sg), hist: h, cross, points: p,
        state: cross === "bullish" ? "fresh bullish cross" : cross === "bearish" ? "fresh bearish cross" : h > 0 ? "above signal" : "below signal" };
      pts += p; mx += 1.5;
    }
    const e20 = last(emaS(closes, 20)), e50 = last(emaS(closes, 50));
    if (e20 != null && e50 != null) {
      let p, st;
      if (price > e20 && e20 > e50) { p = 1; st = "price > EMA20 > EMA50 (uptrend)"; }
      else if (price < e20 && e20 < e50) { p = -1; st = "price < EMA20 < EMA50 (downtrend)"; }
      else if (price > e50) { p = 0.5; st = "mixed, above EMA50"; } else { p = -0.5; st = "mixed, below EMA50"; }
      res.ema = { ema20: e20, ema50: e50, state: st, points: p }; pts += p; mx += 1;
    }
    if (tf === "1d") {
      const e200 = last(emaS(closes, 200));
      if (e200 != null) { const p = price > e200 ? 1 : -1; res.ema200 = { ema200: e200, state: p > 0 ? "above EMA200" : "below EMA200", points: p }; pts += p; mx += 1; }
    }
    if (closes.length >= 20) {
      const bbAt = (end) => { const w = closes.slice(end - 20, end); const m = w.reduce((a, b) => a + b, 0) / 20; const sd = Math.sqrt(w.reduce((a, x) => a + (x - m) ** 2, 0) / 20); return [m, sd]; };
      const [m, sd] = bbAt(closes.length);
      const up = m + 2 * sd, lo = m - 2 * sd;
      const pb = up > lo ? (price - lo) / (up - lo) : 0.5;
      const bw = m ? (up - lo) / m : 0;
      const hb = [];
      for (let end = Math.max(20, closes.length - 120); end <= closes.length; end++) { const [mm, ss] = bbAt(end); hb.push(mm ? (4 * ss) / mm : 0); }
      const sorted = [...hb].sort((a, b) => a - b);
      const squeeze = hb.length >= 40 && bw <= sorted[Math.floor(hb.length * 0.2)];
      const p = pb > 1 ? -0.5 : pb < 0 ? 0.5 : 0;
      res.bb = { pct_b: pb, bandwidth_pct: bw * 100, upper: up, lower: lo, squeeze, points: p,
        state: (pb > 1 ? "above upper band (stretched)" : pb < 0 ? "below lower band (stretched)" : pb >= 0.5 ? "upper half" : "lower half") + (squeeze ? " · squeeze" : "") };
      pts += p; mx += 0.5;
    }
    const rv = rs.filter((x) => x != null);
    if (rv.length >= 20) {
      const raw = [];
      for (let i = 13; i < rv.length; i++) { const w = rv.slice(i - 13, i + 1); const lo = Math.min(...w), hi = Math.max(...w); raw.push(hi === lo ? 0.5 : (rv[i] - lo) / (hi - lo)); }
      const k = []; for (let i = 2; i < raw.length; i++) k.push((raw[i] + raw[i - 1] + raw[i - 2]) / 3);
      const d = []; for (let i = 2; i < k.length; i++) d.push((k[i] + k[i - 1] + k[i - 2]) / 3);
      const K = last(k) * 100, D = last(d) * 100;
      const p = K < 20 && K > D ? 0.5 : K > 80 && K < D ? -0.5 : 0;
      res.stochrsi = { k: K, d: D, points: p, state: p > 0 ? "oversold, turning up" : p < 0 ? "overbought, turning down" : K < 20 ? "oversold" : K > 80 ? "overbought" : "neutral" };
      pts += p; mx += 0.5;
    }
    const vols = c.slice(0, -1).map((x) => x[5]);
    if (vols.length >= 21 && vols.slice(-21).every((x) => x != null)) {
      const avg = vols.slice(-21, -1).reduce((a, b) => a + b, 0) / 20;
      const lc = c[c.length - 2];
      const ratio = avg ? last(vols) / avg : null;
      if (ratio != null) {
        const upc = lc[4] >= lc[1];
        const p = ratio >= 1.5 ? (upc ? 0.5 : -0.5) : 0;
        res.volume = { ratio, points: p, state: ratio >= 1.5 ? `high volume on ${upc ? "green" : "red"} candle` : ratio < 0.6 ? "low volume" : "normal volume" };
        pts += p; mx += 0.5;
      }
    }
    const score = mx ? pts / mx : 0;
    return { price, candle_time: new Date(last(c)[0] * 1000).toISOString(), bars: c.length, indicators: res, points: pts, max_points: mx, score, label: label(score) };
  }

  async function computeAll() {
    const out = {};
    await Promise.all(COINS.map(async (coin) => {
      const [id, sym] = coin;
      try {
        const { source, tfs } = await fetchCoin(coin);
        const t = {}; let tot = 0, ws = 0;
        for (const [tf, w] of Object.entries(TF_WEIGHTS)) {
          const c = tfs[tf] || [];
          if (c.length < 35) continue;
          t[tf] = analyze(c, tf); tot += t[tf].score * w; ws += w;
        }
        const sc = ws ? tot / ws : null;
        out[id] = { symbol: sym, source, price: t["1h"]?.price, score: sc, label: label(sc), timeframes: t };
      } catch (e) { out[id] = { symbol: sym, error: String(e) }; }
    }));
    return { generated_utc: new Date().toISOString(), computed: "browser", coins: out };
  }

  // ---------- rendering ----------
  const TIPS = {
    rsi: "RSI(14): momentum oscillator 0–100. ≥70 = overbought (stretched up, pullback risk), ≤30 = oversold. 50–70 = bullish momentum, 30–50 = bearish.",
    macd: "MACD(12,26,9): trend/momentum. Histogram > 0 means the MACD line is above its signal (bullish). A ‘fresh cross’ happened in the last 3 candles.",
    ema: "EMA 20/50 stack: price > EMA20 > EMA50 is a clean uptrend; the reverse is a downtrend. Anything else is mixed.",
    ema200: "EMA200 (daily only): the classic long-term trend line. Above = long-term uptrend, below = long-term downtrend.",
    bb: "Bollinger Bands(20,2): %B shows where price sits in the band (0 = lower, 1 = upper). Outside the bands = stretched. ‘Squeeze’ = bands unusually narrow (bottom 20% of the last ~120 bars) — often precedes a big move, direction unknown.",
    stochrsi: "Stochastic RSI(14,14,3,3): RSI of RSI, 0–100. <20 oversold, >80 overbought; a %K/%D turn in those zones is the signal.",
    volume: "Volume vs its 20-period average (last closed candle). ≥1.5× on a green candle adds conviction to buyers, on a red candle to sellers.",
  };
  const NAMES = { rsi: "RSI 14", macd: "MACD", ema: "EMA 20/50", ema200: "EMA 200", bb: "Bollinger", stochrsi: "Stoch RSI", volume: "Volume" };
  const fmt = (x, d = 1) => (x == null || isNaN(x) ? "—" : Number(x).toFixed(d));
  function reading(k, i) {
    if (!i) return "—";
    switch (k) {
      case "rsi": return fmt(i.value);
      case "macd": return i.cross ? (i.cross === "bullish" ? "× bull" : "× bear") : i.hist > 0 ? "hist +" : "hist −";
      case "ema": return i.points >= 1 ? "up" : i.points <= -1 ? "down" : i.points > 0 ? "mixed+" : "mixed−";
      case "ema200": return i.points > 0 ? "above" : "below";
      case "bb": return `${fmt(i.pct_b, 2)}${i.squeeze ? " sq" : ""}`;
      case "stochrsi": return fmt(i.k, 0);
      case "volume": return `${fmt(i.ratio, 2)}×`;
    }
    return "—";
  }
  const cls = (p) => (p == null ? "" : p > 0 ? "pos" : p < 0 ? "neg" : "neu");
  const lblCls = (l) => ({ "Strong Buy": "sb", Buy: "b", Neutral: "n", Sell: "s", "Strong Sell": "ss" }[l] || "n");

  function render(doc, origin) {
    const D = window.Dash; const esc = D.esc;
    const el = document.getElementById("signals-grid"); if (!el) return;
    const ids = COINS.map((c) => c[0]);
    el.innerHTML = ids.map((id) => {
      const s = doc.coins?.[id];
      if (!s) return "";
      if (s.error) return `<div class="sig-card"><div class="sig-head"><b>${esc(s.symbol)}</b><span class="sig-label n">n/a</span></div><p class="meta">Could not compute: ${esc(s.error)}</p></div>`;
      const tfs = Object.keys(TF_WEIGHTS);
      const rows = Object.keys(NAMES).map((k) => {
        if (!tfs.some((tf) => s.timeframes[tf]?.indicators?.[k])) return "";
        return `<tr><th scope="row"><span class="tip" tabindex="0" data-tip="${esc(TIPS[k])}">${NAMES[k]}</span></th>${tfs.map((tf) => {
          const i = s.timeframes[tf]?.indicators?.[k];
          return `<td class="${i ? cls(i.points) : ""}" title="${i ? esc(`${tf}: ${i.state} (${i.points > 0 ? "+" : ""}${i.points} pts)`) : ""}">${reading(k, i)}</td>`;
        }).join("")}</tr>`;
      }).join("");
      const pos = s.score == null ? 50 : ((s.score + 1) / 2) * 100;
      return `<div class="sig-card">
        <div class="sig-head"><div><b>${esc(s.symbol)}</b> <small class="muted">${esc(s.source || "")}</small></div><span class="sig-label ${lblCls(s.label)}">${esc(s.label)}</span></div>
        <div class="gauge" title="Composite score ${fmt(s.score, 2)} (−1 … +1)"><span class="gauge-fill" style="left:${Math.min(pos, 50)}%;width:${Math.abs(pos - 50)}%"></span><span class="gauge-mid"></span><span class="gauge-dot" style="left:${pos}%"></span></div>
        <div class="sig-score mono">score ${s.score > 0 ? "+" : ""}${fmt(s.score, 2)}</div>
        <table class="sig-table"><thead><tr><th></th>${tfs.map((tf) => `<th>${tf}</th>`).join("")}</tr></thead><tbody>${rows}
          <tr class="tf-score"><th scope="row">TF score</th>${tfs.map((tf) => { const t = s.timeframes[tf]; return `<td class="${t ? cls(t.score) : ""}" title="${t ? esc(t.label) : ""}">${t ? (t.score > 0 ? "+" : "") + fmt(t.score, 2) : "—"}</td>`; }).join("")}</tr>
        </tbody></table></div>`;
    }).join("");
    const meta = document.getElementById("signals-meta");
    if (meta) meta.textContent = origin === "browser" ? `Computed in your browser ${D.ct(doc.generated_utc)} · refreshes every 3 min` : `Snapshot from the scheduled run ${D.ct(doc.generated_utc)} · live computation pending…`;
    window.Signals.latest = doc;
    document.dispatchEvent(new CustomEvent("signals:update", { detail: doc }));
  }

  async function refresh() {
    try { const doc = await computeAll(); render(doc, "browser"); window.Signals.computedAt = Date.now(); }
    catch (e) { console.warn("signals refresh failed", e); }
  }
  window.Signals = { analyze, computeAll, label, TF_WEIGHTS, latest: null,
    start(snapshot) { if (snapshot && snapshot.coins) render(snapshot, "snapshot"); refresh(); setInterval(refresh, REFRESH_MS); } };
})();
