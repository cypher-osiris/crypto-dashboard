/* Main dashboard (/, visual-first; was the /preview/ page). Reads data/*.json and draws everything with small inline
 * SVG/HTML (no chart library). The detailed classic dashboard lives at /classic/ (app.js etc.).
 * <html data-root="..."> = path prefix to the site root ("" at /, "../" one level down). */
(() => {
  "use strict";
  const TZ = "America/Chicago";
  const ROOT = document.documentElement.dataset.root ?? "";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtPrice = (p) => {
    if (p == null || isNaN(p)) return "—";
    const a = Math.abs(p), d = a >= 1000 ? 0 : a >= 1 ? 3 : a >= 0.1 ? 4 : a >= 0.01 ? 5 : 6;
    return "$" + Number(p).toLocaleString("en-US", { minimumFractionDigits: Math.min(d, 2), maximumFractionDigits: d });
  };
  const num = (p) => fmtPrice(p).replace("$", "");
  const sgn = (v, d = 1) => (v > 0 ? "+" : "") + Number(v).toFixed(d) + "%";
  const pctSpan = (v, d = 1) => v == null || isNaN(v) ? '<span class="muted">n/a</span>' : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${sgn(v, d)}</span>`;
  const big = (v) => v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`;
  const ct = (ts, o) => new Date(ts).toLocaleString("en-US", Object.assign({ timeZone: TZ, month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }, o || {}));
  const ctDate = (ts) => new Date(ts).toLocaleDateString("en-US", { timeZone: TZ, month: "short", day: "numeric" });
  const ctToday = () => new Date().toLocaleDateString("en-CA", { timeZone: TZ });
  const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);
  const lev = (t) => +t.leverage || 1; // per-idea leverage (1x-10x by conviction); every record carries it

  const ICON = {
    up: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 4 4 13h5v7h6v-7h5z"/></svg>',
    down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 20 4 11h5V4h6v7h5z"/></svg>',
    cal: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 2h2v2h6V2h2v2h3v18H4V4h3zm-1 8v10h12V10z"/></svg>',
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 10.4 3.5 2.1-1 1.7L11 13V6h2z"/></svg>',
    arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M13 5l7 7-7 7-1.4-1.4 4.6-4.6H4v-2h12.2l-4.6-4.6z"/></svg>',
  };
  const SIG = { Buy: ["bull", "Bullish"], "Strong Buy": ["bull", "Bullish"], Sell: ["bear", "Bearish"], "Strong Sell": ["bear", "Bearish"], Neutral: ["neu", "Neutral"] };
  const sigBadge = (label) => { const [c, t] = SIG[label] || ["neu", label || "n/a"]; return `<span class="pv-sig ${c}">${t}</span>`; };

  /* ---------- tiny SVG helpers ---------- */
  function spark(pts, w, h, opts = {}) {
    if (!pts || pts.length < 2) return "";
    const ys = pts.map((p) => p[1]), lo = Math.min(...ys), hi = Math.max(...ys), r = hi - lo || 1;
    const x = (i) => (i / (pts.length - 1)) * w, y = (v) => h - 2 - ((v - lo) / r) * (h - 4);
    const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
    const up = ys[ys.length - 1] >= ys[0], col = up ? "var(--pv-up)" : "var(--pv-down)";
    const gid = "g" + Math.random().toString(36).slice(2, 8);
    return `<svg class="pv-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity=".28"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>
      ${opts.area !== false ? `<path d="${d}L${w},${h}L0,${h}Z" fill="url(#${gid})"/>` : ""}
      <path d="${d}" fill="none" stroke="${col}" stroke-width="${opts.sw || 1.6}" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;
  }
  const lastHours = (hist, hours) => { if (!hist || !hist.length) return []; const cut = hist[hist.length - 1][0] - hours * 3600e3; return hist.filter((p) => p[0] >= cut); };

  function gauge(v) {
    // semicircle 0..100, needle at v
    const R = 80, cx = 100, cy = 92, a = Math.PI * (1 - v / 100);
    const nx = cx + (R - 14) * Math.cos(a), ny = cy - (R - 14) * Math.sin(a);
    const seg = (f0, f1, col) => {
      const a0 = Math.PI * (1 - f0), a1 = Math.PI * (1 - f1);
      return `<path d="M${cx + R * Math.cos(a0)},${cy - R * Math.sin(a0)} A${R},${R} 0 0 1 ${cx + R * Math.cos(a1)},${cy - R * Math.sin(a1)}" stroke="${col}" stroke-width="14" fill="none"/>`;
    };
    return `<svg class="pv-gauge" viewBox="0 0 200 108" role="img" aria-label="Market mood ${v} out of 100">
      ${seg(0, 0.25, "#f43f5e")}${seg(0.255, 0.45, "#fb923c")}${seg(0.455, 0.545, "#94a3b8")}${seg(0.55, 0.75, "#4ade80")}${seg(0.755, 1, "#22c55e")}
      <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="#e7ecf3" stroke-width="4" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="7" fill="#e7ecf3"/></svg>`;
  }
  const moodWord = (v) => v < 25 ? "Fearful" : v < 45 ? "Cautious" : v <= 55 ? "Neutral" : v < 75 ? "Upbeat" : "Euphoric";

  /* ---------- data ---------- */
  const get = (n) => fetch(`${ROOT}data/${n}?t=${Math.floor(Date.now() / 6e4)}`, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(`${n}: HTTP ${r.status}`); return r.json(); });
  async function pages() {
    try {
      const x = await fetch(`${ROOT}sitemap.xml`, { cache: "no-store" }).then((r) => r.text());
      return new Set([...x.matchAll(/<loc>https:\/\/lumitrades\.io\/([a-z0-9-]+)\/<\/loc>/g)].map((m) => m[1]));
    } catch (e) { return new Set(); }
  }

  /* ---------- 1. market at a glance ---------- */
  function renderGlance(D) {
    const { prices, signals, context, analysis, ids } = D;
    const btc = prices.assets.bitcoin, bs = (signals.coins || {}).bitcoin || {};
    const up = ids.filter((id) => (prices.assets[id].change_24h || 0) > 0).length;
    const pctUp = (up / ids.length) * 100;
    const fg = context.fear_greed || {};
    const parts = [pctUp];
    if (fg.value != null) parts.push(+fg.value);
    if (bs.score != null) parts.push(((+bs.score + 1) / 2) * 100);
    const mood = Math.round(parts.reduce((a, b) => a + b, 0) / parts.length);
    const tfs = bs.timeframes || {};
    const tfRow = ["1h", "4h", "1d"].filter((k) => tfs[k]).map((k) => `<span><small>${k}</small>${sigBadge(tfs[k].label)}</span>`).join("");
    // next key event: earliest upcoming "event" catalyst across coins
    const today = ctToday(), ev = [];
    Object.entries(analysis.coins || {}).forEach(([id, c]) => (c.catalysts || []).forEach((x) => { if (x.kind === "event" && x.date >= today) ev.push({ id, ...x }); }));
    ev.sort((a, b) => a.date.localeCompare(b.date));
    const sym = (id) => (prices.assets[id] || {}).symbol || id;
    const days = (d) => Math.round((Date.parse(d + "T12:00:00Z") - Date.parse(today + "T12:00:00Z")) / 864e5);
    const evChip = (e) => `<li><span class="pv-ev-date">${new Date(e.date + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}<small>${days(e.date) === 0 ? "today" : days(e.date) === 1 ? "tomorrow" : "in " + days(e.date) + "d"}</small></span><span title="${esc(e.text)}"><b>${esc(sym(e.id))}</b> ${esc(e.text.length > 120 ? e.text.slice(0, 117).replace(/\s+\S*$/, "") + "…" : e.text)}${e.url ? ` <a href="${esc(e.url)}" target="_blank" rel="noopener">source</a>` : ""}</span></li>`;
    const g = context.global || {}, dv = context.derivatives || {};
    $("pv-glance").innerHTML = `
      <article class="pv-card pv-btc">
        <div class="pv-card-top"><span class="pv-kicker">Bitcoin</span>${sigBadge(bs.label)}</div>
        <div class="pv-btc-price"><b class="mono">${fmtPrice(btc.price)}</b>${pctSpan(btc.change_24h, 2)}<small class="muted">24h</small></div>
        <div class="pv-btc-chart">${spark(lastHours(btc.history, 24 * 30), 300, 70)}<span class="pv-chart-cap">30 days · ${pctSpan(btc.change_30d)}</span></div>
        <div class="pv-btc-foot"><span>7d ${pctSpan(btc.change_7d)}</span><span class="pv-tfs">${tfRow}</span></div>
      </article>
      <article class="pv-card pv-mood">
        <div class="pv-card-top"><span class="pv-kicker">Market mood</span><span class="pv-mood-val"><b>${mood}</b>/100</span></div>
        ${gauge(mood)}
        <p class="pv-mood-word">${moodWord(mood)}</p>
        <ul class="pv-mood-parts">
          <li><b>${up}/${ids.length}</b> tracked coins up 24h</li>
          ${fg.value != null ? `<li>Fear &amp; Greed <b>${esc(fg.value)}</b> (${esc(fg.classification || "")})</li>` : ""}
          ${bs.score != null ? `<li>BTC signal <b>${esc(bs.label)}</b> (${bs.score > 0 ? "+" : ""}${(+bs.score).toFixed(2)})</li>` : ""}
        </ul>
      </article>
      <article class="pv-card pv-events">
        <div class="pv-card-top"><span class="pv-kicker">${ICON.cal} Coming up</span></div>
        ${ev.length ? `<ul class="pv-ev">${ev.slice(0, 3).map(evChip).join("")}</ul>` : `<p class="muted">No dated events in Lumi's catalyst list right now.</p>`}
        <div class="pv-stats">
          ${g.total_mcap_usd ? `<span><small>Total mcap</small>${big(g.total_mcap_usd)} ${pctSpan(g.mcap_change_24h_pct)}</span>` : ""}
          ${g.btc_dominance_pct ? `<span><small>BTC dominance</small>${g.btc_dominance_pct.toFixed(1)}%</span>` : ""}
          ${dv.funding_rate_pct != null ? `<span><small>BTC funding</small>${dv.funding_rate_pct.toFixed(4)}%</span>` : ""}
        </div>
      </article>`;
  }

  /* ---------- 2. heat-map tiles ---------- */
  function tileHref(id, sym) { return D.pages.has(sym.toLowerCase()) ? `${ROOT}${sym.toLowerCase()}/` : `${ROOT}classic/#coins`; }
  function renderTiles(D) {
    const { prices, signals, trades } = D;
    const active = new Set((trades.trades || []).filter((t) => ["pending", "open"].includes(t.status)).map((t) => t.coin));
    const groups = (D.coins.groups || []).map((g) => ({ ...g, ids: D.ids.filter((id) => (prices.assets[id].group || "") === g.id) }));
    $("pv-tiles").innerHTML = groups.filter((g) => g.ids.length).map((g) => `<h3 class="pv-group">${esc(g.label)}</h3><div class="pv-tile-grid">` + g.ids.map((id) => {
      const a = prices.assets[id], c = a.change_24h || 0, k = Math.min(Math.abs(c) / 8, 1);
      const rgb = c >= 0 ? "34,197,94" : "244,63,94";
      const s = (signals.coins || {})[id] || {};
      return `<a class="pv-tile" href="${tileHref(id, a.symbol)}" style="--heat:rgba(${rgb},${(0.07 + k * 0.38).toFixed(3)});--edge:rgba(${rgb},${(0.2 + k * 0.5).toFixed(3)})" aria-label="${esc(a.name)} ${fmtPrice(a.price)}, ${sgn(c)} in 24 hours, signal ${esc(s.label || "n/a")}">
        <div class="pv-tile-top"><b>${esc(a.symbol)}</b>${sigBadge(s.label)}</div>
        <div class="pv-tile-price mono">${fmtPrice(a.price)}</div>
        <div class="pv-tile-chg ${c >= 0 ? "up" : "down"}">${c >= 0 ? ICON.up : ICON.down}${sgn(c)}</div>
        <div class="pv-tile-spark">${spark(lastHours(a.history, 24 * 7), 120, 34, { sw: 1.4 })}</div>
        <div class="pv-tile-foot"><small class="muted">${esc(a.name)}</small>${active.has(id) ? '<span class="pv-idea" title="Active paper-trade idea">idea</span>' : ""}</div>
      </a>`;
    }).join("") + `</div>`).join("");
  }

  /* ---------- 3. visual trade cards ---------- */
  const zoneOf = (t) => t.entry_zone ? { lo: +t.entry_zone.low, hi: +t.entry_zone.high } : { lo: +t.entry, hi: +t.entry };
  function statusOf(t) {
    if (t.status === "pending") return ["pending", "Pending"];
    if (t.status === "open") return (t.targets_hit || []).some(Boolean) ? ["hit", "T1 hit · open"] : ["open", "Open"];
    if (t.status === "won" || t.status === "target") return ["hit", "Hit target"];
    if (t.status === "stopped" || t.status === "lost") return ["stopped", "Stopped"];
    return ["closed", cap(t.status)];
  }
  function ladder(t, price) {
    // HTML ladder (labels stay real-size text at any width); positions are % of the price range
    const { lo, hi } = zoneOf(t), stop = +(t.current_stop ?? t.stop), tg = (t.targets || []).map(Number);
    const open = t.status === "open" && t.entry;
    const vals = [lo, hi, stop, ...tg, price].filter((v) => v != null && !isNaN(v));
    if (open) vals.push(+t.entry);
    let mn = Math.min(...vals), mx = Math.max(...vals); const pad = (mx - mn) * 0.04 || mn * 0.01; mn -= pad; mx += pad;
    const X = (v) => ((v - mn) / (mx - mn)) * 100;
    const long = t.direction !== "short";
    const ref = open ? +t.entry : long ? lo : hi, far = tg.length ? tg[tg.length - 1] : ref;
    const marks = [{ v: stop, k: "stop", l: "Stop" }, ...tg.map((v, i) => ({ v, k: (t.targets_hit || [])[i] ? "tg hit" : "tg", l: `T${i + 1}${(t.targets_hit || [])[i] ? " ✓" : ""}` }))];
    marks.push(open ? { v: +t.entry, k: "fill", l: "Fill" } : { v: (lo + hi) / 2, k: "zone", l: "Entry", txt: lo === hi ? num(lo) : `${num(lo)}–${num(hi)}` });
    // greedy rows: a label goes on the first row where it doesn't crowd the previous label (~22% apart)
    // label width as % of a ~310px-wide ladder (the narrowest case: a 390px phone)
    const wid = (m) => (((m.txt || num(m.v)).length * 7.4 + 10) / 310) * 100;
    const rows = []; marks.slice().sort((a, b) => a.v - b.v).forEach((m) => {
      const x = X(m.v), w = wid(m); let r = 0;
      while (rows[r] && x - w / 2 < rows[r] + 1.5) r++;
      m.row = r; rows[r] = x + w / 2;
    });
    const nRows = Math.max(1, rows.length);
    const pos = (x) => `left:${x.toFixed(2)}%;--tx:${x < 10 ? "0" : x > 90 ? "-100%" : "-50%"}`;
    const seg = (a, b, cls) => `<span class="${cls}" style="left:${Math.min(X(a), X(b)).toFixed(2)}%;width:${Math.abs(X(b) - X(a)).toFixed(2)}%"></span>`;
    return `<div class="pv-ladder" style="--rows:${nRows}" role="img" aria-label="Price ladder: stop ${num(stop)}, entry ${num(lo)} to ${num(hi)}${open ? `, filled ${num(t.entry)}` : ""}, targets ${tg.map(num).join(", ")}, price now ${num(price)}">
      <div class="pv-lad-now" style="${pos(X(price))}"><b>now ${num(price)}</b></div>
      <div class="pv-lad-track">${seg(stop, ref, "risk")}${seg(ref, far, "rew")}${seg(lo, hi, "zone")}
        ${marks.filter((m) => m.k !== "zone").map((m) => `<i class="tick ${m.k}" style="left:${X(m.v).toFixed(2)}%"></i>`).join("")}
        <i class="cur" style="left:${X(price).toFixed(2)}%"></i></div>
      <div class="pv-lad-lbls">${marks.map((m) => `<span class="${m.k}" style="${pos(X(m.v))};top:${m.row * 30}px"><small>${m.l}</small>${m.txt || num(m.v)}</span>`).join("")}</div>
    </div>`;
  }
  function rrBar(t) {
    const { lo, hi } = zoneOf(t), stop = +(t.current_stop ?? t.stop), tg = (t.targets || []).map(Number);
    const long = t.direction !== "short";
    const ref = t.status === "open" && t.entry ? +t.entry : (lo + hi) / 2;
    const risk = Math.abs(ref - stop); if (!risk || !tg.length) return "";
    const rr = tg.map((x) => Math.abs(x - ref) / risk), tot = 1 + rr[rr.length - 1];
    const L = lev(t), mv = (x) => ((long ? x - ref : ref - x) / ref) * 100 * L;
    return `<div class="pv-rr" title="Risk vs reward from ${t.status === "open" ? "the fill" : "the middle of the entry zone"}">
      <div class="pv-rr-bar"><span class="r" style="width:${(100 / tot).toFixed(1)}%"></span>${rr.map((v, i) => `<span class="g${i}" style="width:${(((v - (i ? rr[i - 1] : 0)) / tot) * 100).toFixed(1)}%"></span>`).join("")}</div>
      <div class="pv-rr-txt"><span class="down">risk ${mv(stop).toFixed(1)}%</span><span>R:R ${rr.map((v, i) => `<b>${v.toFixed(1)}</b><small>T${i + 1}</small>`).join(" · ")}</span><span class="up">T${tg.length} +${mv(tg[tg.length - 1]).toFixed(1)}%</span></div>
      <small class="muted">${L === 1 ? "spot, no leverage" : L + "x paper leverage"} · % moves include leverage</small></div>`;
  }
  function missedHtml(t) {
    const p = t.missed_plan, mi = t.missed_it; let h = "";
    if (mi) h += `<p><b>Missed it?</b> ${mi.max_entry != null ? `Max entry <span class="mono">${num(mi.max_entry)}</span>. ` : ""}${esc(mi.note || "")}</p>`;
    if (p && p.type !== "none") {
      const z = p.entry_zone || {};
      h += `<p><b>Plan B (${esc(p.type)})${p.status ? ` · ${esc(p.status)}` : ""}:</b> ${esc(p.trigger || "")}</p>
        <p class="mono pv-mp">entry ${num(z.low)}–${num(z.high)} · stop ${num(p.stop)} · target ${num(p.target)} · ${(+p.leverage || lev(t)) === 1 ? "spot" : (+p.leverage || lev(t)) + "x"}</p>${p.reasoning ? `<p>${esc(p.reasoning)}</p>` : ""}`;
    } else if (p && p.type === "none") h += `<p><b>Plan B:</b> no good chase. ${esc(p.reasoning || "")}</p>`;
    return h;
  }
  // "5x · High conviction" (leverage is picked per idea, 1x-10x, by conviction; 1x = spot)
  function levBadge(t) {
    const L = lev(t), c = String(t.conviction || "").toLowerCase();
    return `<div class="pv-lev c-${esc(c || "na")}" title="${esc(t.leverage_reason || "Leverage set per idea (1x-10x) by conviction")}">
      <b>${L === 1 ? "Spot · 1x" : L + "x"}</b>${c ? `<span>${esc(cap(c))} conviction</span>` : ""}
      <i class="pv-lev-meter" aria-hidden="true">${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => `<u class="${n <= L ? "on" : ""}"></u>`).join("")}</i></div>`;
  }
  function tradeCard(t) {
    const a = D.prices.assets[t.coin], an = (D.analysis.coins || {})[t.coin] || {};
    const [cls, lbl] = statusOf(t), long = t.direction !== "short", L = lev(t);
    const page = D.pages.has(a.symbol.toLowerCase()) ? `<a class="pv-more-link" href="${ROOT}${a.symbol.toLowerCase()}/">${esc(a.symbol)} analysis &amp; levels ${ICON.arrow}</a>` : "";
    let live = "";
    if (t.status === "open" && t.unrealized_pnl_pct != null) live = `<span class="pv-pnl">P&amp;L ${pctSpan(t.unrealized_pnl_pct)}<small> (${t.last_checked ? ct(t.last_checked, { month: undefined, day: undefined }) : "tracker"})</small></span>`;
    else if (t.status === "pending" && t.expiry) live = `<span class="muted pv-exp">${ICON.clock} expires ${ct(t.expiry)}</span>`;
    return `<article class="slate-card pv-trade ${esc(t.status)}" data-slate="${esc(t.id)}" data-coin="${esc(t.coin)}" data-sym="${esc(a.symbol)}" data-lev="${L}" data-dir="${esc(t.direction)}" data-cb="${esc(D.cb[t.coin] || "")}">
      <div class="pv-trade-top">
        <span class="pv-dir ${long ? "long" : "short"}" title="${long ? "Long" : "Short"}">${long ? ICON.up : ICON.down}</span>
        <div class="pv-trade-id"><b>${esc(a.symbol)}</b> <span class="muted">${long ? "Long" : "Short"}</span></div>
        <span class="pv-status ${cls}">${lbl}</span>
      </div>
      ${levBadge(t)}
      <div class="pv-tags"><span class="pv-tag">${esc(cap(t.timeframe || "short-term"))}</span>${t.plan_type ? `<span class="pv-tag">${esc(t.plan_type)} plan</span>` : ""}<span class="pv-tag mono">${esc(t.id)}</span>${live}</div>
      <p class="pv-thesis">${esc(cap(an.bias || (t.trigger || "")))}</p>
      ${ladder(t, a.price)}
      ${rrBar(t)}
      ${t.parent_id ? `<p class="pv-linked">Follow-up of ${esc(t.parent_id)}${t.trigger ? `: ${esc(t.trigger)}` : ""}</p>` : ""}
      <details class="why"><summary>Read more: reasoning &amp; "missed it?"</summary>
        ${t.leverage_reason ? `<p class="pv-levwhy"><b>Why ${L === 1 ? "spot (1x)" : L + "x"}${t.conviction ? ` · ${esc(cap(t.conviction))} conviction` : ""}:</b> ${esc(t.leverage_reason)}</p>` : ""}
        <p>${esc(t.reasoning || "")}</p>${missedHtml(t)}${t.size_note ? `<p>${esc(t.size_note)}</p>` : ""}${t.leverage_note ? `<p class="muted">${esc(t.leverage_note)}</p>` : ""}
      </details>
      ${page}
    </article>`;
  }
  function renderSlate(D) {
    const all = D.trades.trades || [], sl = (D.trades.slate || {}).coins || {};
    const act = all.filter((t) => ["pending", "open"].includes(t.status)).sort((a, b) => (a.status === "open" ? 0 : 1) - (b.status === "open" ? 0 : 1));
    $("slate-grid").innerHTML = act.length ? act.map(tradeCard).join("") : `<p class="muted">No active ideas right now. That's a valid call too.</p>`;
    const none = Object.entries(sl).filter(([id, e]) => !e.trade_id && D.prices.assets[id]);
    $("pv-nosetup").innerHTML = none.length ? `<details class="pv-fold"><summary>${none.length} coin${none.length > 1 ? "s" : ""} with no setup right now: ${none.map(([id]) => esc(D.prices.assets[id].symbol)).join(", ")}</summary>
      <ul class="pv-nosetup">${none.map(([id, e]) => `<li><b>${esc(D.prices.assets[id].symbol)}</b> ${esc(e.note || "")}</li>`).join("")}</ul></details>` : "";
    if (D.trades.slate && D.trades.slate.as_of) {
      const s = $("slate-sched"); let m = s.querySelector(".pv-asof"); if (!m) { m = document.createElement("span"); m.className = "pv-asof"; s.appendChild(m); }
      m.textContent = ` · Slate as of ${ct(D.trades.slate.as_of)}`;
    }
  }


  /* ---------- signals (indicator reads per coin) ---------- */
  const READ = (l) => ({ "Strong Buy": ["sb", "Strong Buy", 2], Buy: ["b", "Buy", 1], Neutral: ["n", "Neutral", 0], Sell: ["s", "Sell", -1], "Strong Sell": ["ss", "Strong Sell", -2] }[l] || ["n", l || "n/a", 0]);
  const ARROW = { sb: "M12 3l8 8-1.8 1.8L12 6.6l-6.2 6.2L4 11zm0 7l8 8-1.8 1.8-6.2-6.2-6.2 6.2L4 18z", b: "M12 4 4 13h5v7h6v-7h5z",
    n: "M4 11h11V7l5 5-5 5v-4H4z", s: "M12 20 4 11h5V4h6v7h5z", ss: "M12 21l-8-8 1.8-1.8 6.2 6.2 6.2-6.2L20 13zm0-7L4 6l1.8-1.8L12 10.4l6.2-6.2L20 6z" };
  const arrowSvg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="${ARROW[k] || ARROW.n}"/></svg>`;
  const IND = [["rsi", "RSI"], ["macd", "MACD"], ["ema", "EMA trend"], ["ema200", "EMA200"], ["bb", "Bollinger"], ["stochrsi", "StochRSI"], ["volume", "Volume"]];
  const TFS = ["1h", "4h", "1d"];
  const dirOf = (pts) => (pts > 0 ? "up" : pts < 0 ? "down" : "flat");
  const tri = { up: '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 1 9.5 9h-9z" fill="currentColor"/></svg>', down: '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 9 .5 1h9z" fill="currentColor"/></svg>', flat: '<svg viewBox="0 0 10 10" aria-hidden="true"><rect x="1" y="4" width="8" height="2" rx="1" fill="currentColor"/></svg>' };
  function sigLine(c) {
    const tf = c.timeframes || {}, reads = TFS.filter((k) => tf[k]).map((k) => READ(tf[k].label)[2]);
    const bull = reads.filter((v) => v > 0).length, bear = reads.filter((v) => v < 0).length, n = reads.length;
    const head = bull === n ? `All ${n} timeframes bullish` : bear === n ? `All ${n} timeframes bearish`
      : bull > bear ? `${bull} of ${n} timeframes bullish` : bear > bull ? `${bear} of ${n} timeframes bearish`
      : bull ? `Mixed: ${bull} bullish, ${bear} bearish` : `No clear lean on any timeframe`;
    const r = tf["1d"] && tf["1d"].indicators && tf["1d"].indicators.rsi, rv = r && r.value != null ? Math.round(r.value) : null;
    const rsi = rv == null ? "" : `; daily RSI ${rv}, ${rv >= 70 ? "overbought" : rv <= 30 ? "oversold" : rv >= 60 ? "strong, not overbought" : rv <= 40 ? "weak, not oversold" : "mid-range"}`;
    const e = tf["1d"] && tf["1d"].indicators && tf["1d"].indicators.ema;
    const trend = e ? (e.points >= 1 ? "; daily uptrend" : e.points <= -1 ? "; daily downtrend" : "") : "";
    return head + rsi + trend + ".";
  }
  function signalCard(id) {
    const c = (D.signals.coins || {})[id], a = D.prices.assets[id];
    const [k, lbl] = READ(c.label), sc = +c.score || 0, tf = c.timeframes || {};
    const pos = ((Math.max(-1, Math.min(1, sc)) + 1) / 2) * 100;
    const chips = IND.filter(([key]) => TFS.some((t) => tf[t] && tf[t].indicators && tf[t].indicators[key])).map(([key, name]) => {
      const per = TFS.map((t) => { const x = tf[t] && tf[t].indicators && tf[t].indicators[key]; return x ? { t, d: dirOf(+x.points || 0), st: x.state, v: x.value } : null; }).filter(Boolean);
      const net = per.reduce((s2, x) => s2 + (x.d === "up" ? 1 : x.d === "down" ? -1 : 0), 0);
      const tip = per.map((x) => `${x.t}: ${x.st}${x.v != null && key === "rsi" ? ` (${(+x.v).toFixed(0)})` : ""}`).join(" · ");
      return `<span class="sg-chip ${net > 0 ? "up" : net < 0 ? "down" : "flat"}" title="${esc(name + " — " + tip)}"><b>${name}</b>${per.map((x) => `<i class="${x.d}" aria-label="${x.t} ${x.d}">${tri[x.d]}</i>`).join("")}</span>`;
    }).join("");
    return `<article class="sg-card k-${k}" aria-label="${esc(a.symbol)} signal ${esc(lbl)}, score ${sc.toFixed(2)}">
      <div class="sg-top"><a href="${tileHref(id, a.symbol)}"><b>${esc(a.symbol)}</b></a><span class="mono muted">${fmtPrice(a.price)}</span></div>
      <div class="sg-read"><span class="sg-arrow">${arrowSvg(k)}</span><b>${esc(lbl)}</b></div>
      <div class="sg-meter" title="Composite score ${sc > 0 ? "+" : ""}${sc.toFixed(2)} (−1 to +1)"><span class="sg-track"><i style="left:${pos.toFixed(1)}%"></i></span><span class="sg-score mono">${sc > 0 ? "+" : ""}${sc.toFixed(2)}</span></div>
      <div class="sg-tfs">${TFS.filter((t) => tf[t]).map((t) => { const [tk, tl] = READ(tf[t].label); return `<span class="sg-tf k-${tk}"><small>${t}</small>${esc(tl)}</span>`; }).join("")}</div>
      <p class="sg-line">${esc(sigLine(c))}</p>
      <div class="sg-chips">${chips}</div>
    </article>`;
  }
  let sigSort = "strong";
  function renderSignals(D) {
    const box = $("sg-grid"); if (!box) return;
    const ids = D.ids.filter((id) => (D.signals.coins || {})[id]);
    const sc = (id) => +D.signals.coins[id].score || 0;
    const order = { strong: (a, b) => Math.abs(sc(b)) - Math.abs(sc(a)), bull: (a, b) => sc(b) - sc(a), bear: (a, b) => sc(a) - sc(b), list: () => 0 }[sigSort];
    box.innerHTML = ids.slice().sort(order).map(signalCard).join("");
    const counts = ids.reduce((m, id) => { const k = READ(D.signals.coins[id].label)[2]; m[k > 0 ? 0 : k < 0 ? 2 : 1]++; return m; }, [0, 0, 0]);
    $("sg-sum").innerHTML = `<span class="up">${counts[0]} buy</span> · <span>${counts[1]} neutral</span> · <span class="down">${counts[2]} sell</span>` +
      (D.signals.generated_utc ? ` <span class="muted">· computed ${ct(D.signals.generated_utc)}</span>` : "");
  }
  function wireSignalSort() {
    document.querySelectorAll("[data-sgsort]").forEach((b) => b.addEventListener("click", () => {
      sigSort = b.dataset.sgsort;
      document.querySelectorAll("[data-sgsort]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      if (D) renderSignals(D);
    }));
  }

  /* ---------- 4. scorecard ---------- */
  function donut(parts) {
    const tot = parts.reduce((a, p) => a + p.n, 0) || 1, R = 42, C = 2 * Math.PI * R; let off = 0;
    return `<svg class="pv-donut" viewBox="0 0 120 120" role="img" aria-label="${parts.map((p) => `${p.n} ${p.l}`).join(", ")}">
      <circle cx="60" cy="60" r="${R}" fill="none" stroke="rgba(148,163,184,.12)" stroke-width="16"/>
      ${parts.filter((p) => p.n).map((p) => { const len = (p.n / tot) * C; const s = `<circle cx="60" cy="60" r="${R}" fill="none" stroke="${p.c}" stroke-width="16" stroke-dasharray="${len - 2} ${C - len + 2}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"/>`; off += len; return s; }).join("")}
      <text x="60" y="58" text-anchor="middle" class="dn">${tot}</text><text x="60" y="74" text-anchor="middle" class="dl">ideas</text></svg>`;
  }
  function pnlChart(trades, curve) {
    const first = trades.map((t) => Date.parse(t.opened_at)).filter(Boolean).sort((a, b) => a - b)[0];
    const pts = [[first, 0], ...curve.map((p) => [Date.parse(p.t), +p.cum_pnl_pct])];
    const now = Date.now(); pts.push([now, pts[pts.length - 1][1]]);
    const W = 520, H = 150, P = { l: 44, r: 12, t: 14, b: 26 };
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), lo = Math.min(0, ...ys), hi = Math.max(0, ...ys), pad = (hi - lo) * 0.15 || 5;
    const X = (v) => P.l + ((v - x0) / (x1 - x0 || 1)) * (W - P.l - P.r), Y = (v) => P.t + (1 - (v - (lo - pad)) / (hi + pad - (lo - pad))) * (H - P.t - P.b);
    // step line: P&L changes only when a trade closes
    let d = `M${X(pts[0][0])},${Y(pts[0][1])}`; for (let i = 1; i < pts.length; i++) d += `H${X(pts[i][0])}V${Y(pts[i][1])}`;
    const last = ys[ys.length - 1], col = last >= 0 ? "var(--pv-up)" : "var(--pv-down)";
    const ticks = [0, ...curve.map((p) => +p.cum_pnl_pct)].filter((v, i, a) => a.indexOf(v) === i);
    return `<svg class="pv-pnl-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Cumulative paper P&L ${sgn(last)}">
      ${ticks.map((v) => `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="rgba(148,163,184,${v === 0 ? ".35" : ".1"})" ${v === 0 ? "" : 'stroke-dasharray="3 4"'}/><text x="${P.l - 6}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v === 0 ? "0%" : sgn(v, 1)}</text>`).join("")}
      <path d="${d}" fill="none" stroke="${col}" stroke-width="2.5" stroke-linejoin="round"/>
      ${curve.map((p) => `<circle cx="${X(Date.parse(p.t))}" cy="${Y(+p.cum_pnl_pct)}" r="4.5" fill="${col}"><title>${esc(p.trade_id)} closed: cumulative ${sgn(+p.cum_pnl_pct)}</title></circle>`).join("")}
      <text x="${P.l}" y="${H - 6}" class="ax">${ctDate(x0)}</text><text x="${W - P.r}" y="${H - 6}" text-anchor="end" class="ax">now</text></svg>`;
  }
  function renderScore(D) {
    const all = D.trades.trades || [], st = D.trades.stats || {};
    const n = (f) => all.filter(f).length;
    const won = n((t) => t.status === "won" || t.status === "target" || (["closed"].includes(t.status) && t.pnl_pct > 0));
    const lost = n((t) => ["stopped", "lost"].includes(t.status) || (t.status === "closed" && t.pnl_pct <= 0));
    const parts = [{ l: "won", n: won, c: "#22c55e" }, { l: "stopped", n: lost, c: "#f43f5e" }, { l: "open", n: n((t) => t.status === "open"), c: "#38bdf8" }, { l: "pending", n: n((t) => t.status === "pending"), c: "#fbbf24" }, { l: "cancelled", n: n((t) => t.status === "cancelled"), c: "#64748b" }];
    const opens = all.filter((t) => t.status === "open" && t.unrealized_pnl_pct != null);
    const mx = Math.max(1, ...opens.map((t) => Math.abs(t.unrealized_pnl_pct)));
    const sym = (id) => (D.prices.assets[id] || {}).symbol || id;
    const closed = all.filter((t) => !["pending", "open"].includes(t.status)).sort((a, b) => String(b.closed_at || b.opened_at).localeCompare(String(a.closed_at || a.opened_at)));
    $("pv-score").innerHTML = `
      <article class="pv-card pv-score-a">
        <div class="pv-donut-wrap">${donut(parts)}<ul class="pv-keys">${parts.map((p) => `<li><i style="background:${p.c}"></i>${p.n} ${p.l}</li>`).join("")}</ul></div>
        <div class="pv-kpis"><span><small>Win rate (closed)</small><b>${st.win_rate_pct != null ? st.win_rate_pct.toFixed(0) + "%" : "—"}</b><small class="muted">${won}W / ${lost}L</small></span>
          <span><small>Cumulative paper P&amp;L</small><b class="${(st.cumulative_pnl_pct || 0) >= 0 ? "up" : "down"}">${st.cumulative_pnl_pct != null ? sgn(st.cumulative_pnl_pct) : "—"}</b><small class="muted">closed trades, at leverage</small></span></div>
      </article>
      <article class="pv-card pv-score-b">
        <div class="pv-card-top"><span class="pv-kicker">Cumulative paper P&amp;L</span><span class="muted">realized, equal size per trade</span></div>
        ${pnlChart(all, st.equity_curve || [])}
        ${opens.length ? `<div class="pv-open-pnl"><span class="pv-kicker">Open ideas right now (unrealized)</span>${opens.map((t) => `<div class="pv-ob"><span>${esc(sym(t.coin))} <small class="muted mono">${esc(t.id)}</small></span><span class="pv-ob-track"><i class="${t.unrealized_pnl_pct >= 0 ? "pos" : "neg"}" style="width:${(Math.abs(t.unrealized_pnl_pct) / mx) * 50}%"></i></span>${pctSpan(t.unrealized_pnl_pct)}</div>`).join("")}</div>` : ""}
        ${st.note ? `<p class="pv-fine">${esc(st.note)}</p>` : ""}
      </article>
      <details class="pv-fold pv-span"><summary>Full trade history (${all.length})</summary>
        <div class="pv-table-wrap"><table class="pv-table"><thead><tr><th>ID</th><th>Coin</th><th>Side</th><th>Entry</th><th>Stop</th><th>Targets</th><th>Status</th><th>Result</th></tr></thead><tbody>
        ${all.slice().reverse().map((t) => `<tr><td class="mono">${esc(t.id)}</td><td>${esc(sym(t.coin))}</td><td>${esc(t.direction)} ${lev(t)}x</td><td class="mono">${num(t.entry)}</td><td class="mono">${num(t.current_stop ?? t.stop)}</td><td class="mono">${(t.targets || []).map(num).join(" / ")}</td><td><span class="pv-status ${statusOf(t)[0]}">${statusOf(t)[1]}</span></td><td>${t.pnl_pct != null ? pctSpan(t.pnl_pct) : t.unrealized_pnl_pct != null ? pctSpan(t.unrealized_pnl_pct) + '<small class="muted"> open</small>' : "—"}</td></tr>`).join("")}
        </tbody></table></div>${closed.length ? "" : ""}</details>`;
  }

  /* ---------- 5. analysis, collapsed ---------- */
  function projBar(pr, price, sup, res) {
    let bear, base, bull, cap2;
    if (pr && pr.bear != null && pr.bull != null) { bear = +pr.bear; base = +pr.base; bull = +pr.bull; cap2 = `${pr.horizon_days || 7}-day projection`; }
    else return "";
    const mn = Math.min(bear, price), mx = Math.max(bull, price), r = mx - mn || 1, X = (v) => ((v - mn) / r) * 100;
    const chg = (v) => sgn(((v - price) / price) * 100);
    return `<div class="pv-proj" aria-label="${cap2}: bear ${num(bear)}, base ${num(base)}, bull ${num(bull)}; price ${num(price)}">
      <div class="pv-proj-cap"><span class="muted">${cap2}</span></div>
      <div class="pv-proj-track"><span class="seg" style="left:${X(bear)}%;width:${X(bull) - X(bear)}%"></span>
        <i class="pt bear" style="left:${X(bear)}%"></i><i class="pt base" style="left:${X(base)}%"></i><i class="pt bull" style="left:${X(bull)}%"></i>
        <b class="now" style="left:${X(price)}%" title="now ${num(price)}"></b></div>
      <div class="pv-proj-lbl"><span class="down">Bear ${num(bear)}<small>${chg(bear)}</small></span><span>Base ${num(base)}<small>${chg(base)}</small></span><span class="up">Bull ${num(bull)}<small>${chg(bull)}</small></span></div></div>`;
  }
  function renderAnalysis(D) {
    const an = D.analysis.coins || {};
    $("pv-an-asof").textContent = D.analysis.as_of ? `Reviewed ${ct(D.analysis.as_of)}` : "";
    $("pv-analysis").innerHTML = D.ids.filter((id) => an[id]).map((id) => {
      const c = an[id], a = D.prices.assets[id], s = (D.signals.coins || {})[id] || {}, tf = s.timeframes || {};
      const tfTxt = ["1h", "4h", "1d"].filter((k) => tf[k]).map((k) => `${k} ${tf[k].label}`).join(" · ");
      const sup = (c.support || [])[0], res = (c.resistance || [])[0];
      const summary = `${esc(cap(c.bias))}. ` + (sup != null && res != null ? `Nearest support <b class="mono">${num(sup)}</b>, resistance <b class="mono">${num(res)}</b>` : "") + (tfTxt ? `; signals ${esc(tfTxt)}.` : ".");
      const page = D.pages.has(a.symbol.toLowerCase()) ? `<a class="pv-more-link" href="${ROOT}${a.symbol.toLowerCase()}/">Open the ${esc(a.symbol)} page ${ICON.arrow}</a>` : "";
      return `<article class="pv-card pv-an">
        <div class="pv-an-top"><a href="${tileHref(id, a.symbol)}"><b>${esc(a.symbol)}</b> <span class="muted">${esc(a.name)}</span></a><span class="mono">${fmtPrice(a.price)} ${pctSpan(a.change_24h)}</span>${sigBadge(s.label)}</div>
        <p class="pv-an-sum">${summary}</p>
        ${projBar(c.projection, a.price, sup, res)}
        <details class="pv-an-full"><summary>Read full analysis</summary>
          <div class="pv-lv"><span><small>Support</small>${(c.support || []).map(num).join(" · ") || "—"}</span><span><small>Resistance</small>${(c.resistance || []).map(num).join(" · ") || "—"}</span></div>
          <p>${esc(c.commentary || "")}</p>
          ${(c.catalysts || []).length ? `<h4>Catalysts</h4><ul class="pv-cat">${c.catalysts.map((x) => `<li><span class="pv-tag">${esc(x.kind)}</span> <b>${esc(x.date)}</b> ${esc(x.text)}${x.url ? ` <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source || "source")}</a>` : ""}</li>`).join("")}</ul>` : ""}
          ${(c.sources || []).length ? `<h4>Sources</h4><ul class="pv-src">${c.sources.map((x) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a></li>`).join("")}</ul>` : ""}
        </details>${page}
      </article>`;
    }).join("");
  }

  function renderLog(D) {
    const e = ((D.log || {}).entries || []).slice(0, 10);
    $("pv-log").innerHTML = e.map((x) => `<li><span class="mono muted">${ct(x.t)}</span> <span class="pv-tag">${esc(x.kind)}</span> ${esc(x.text)}</li>`).join("");
  }
  function renderFoot(D) {
    const links = D.ids.map((id) => D.prices.assets[id].symbol).filter((s) => D.pages.has(s.toLowerCase()));
    if (!$("pv-foot-coins")) return; // the main page has the static block from build_pages.py
    $("pv-foot-coins").innerHTML = links.length ? "Coin pages: " + links.map((s) => `<a href="${ROOT}${s.toLowerCase()}/">${esc(s)}</a>`).join(" · ") : "";
  }

  let D = null;
  async function load() {
    try {
      const [prices, signals, trades, analysis, context, coins, log, pg] = await Promise.all(
        ["prices.json", "signals.json", "trades.json", "analysis.json", "context.json", "coins.json", "log.json"].map(get).concat([pages()]));
      const order = (coins.coins || []).map((c) => c.id).filter((id) => prices.assets[id]);
      const cb = Object.fromEntries((coins.coins || []).map((c) => [c.id, c.coinbase || ""]));
      D = { prices, signals, trades, analysis, context, coins, log, pages: pg, ids: order, cb };
      const openKeep = [...document.querySelectorAll("details[open]")].map((d) => d.closest("[data-slate]")?.dataset.slate || d.querySelector("summary")?.textContent);
      [renderGlance, renderTiles, renderSlate, renderSignals, renderScore, renderAnalysis, renderLog, renderFoot].forEach((f) => { try { f(D); } catch (e) { console.warn("preview:", f.name, e); } });
      document.querySelectorAll("details").forEach((d) => { const k = d.closest("[data-slate]")?.dataset.slate || d.querySelector("summary")?.textContent; if (openKeep.includes(k)) d.open = true; });
      $("pv-snap").innerHTML = `<span class="dot" aria-hidden="true"></span> Data as of ${ct(prices.updated_utc)}`;
    } catch (e) {
      $("pv-snap").textContent = "Couldn't load data. Try refreshing.";
      console.warn("preview load failed", e);
    }
  }
  const boot = () => { wireSignalSort(); load(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
  setInterval(load, 5 * 60e3);
})();
