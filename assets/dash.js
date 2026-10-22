/* Main dashboard (/, visual-first; was the /preview/ page). Reads data/*.json and draws everything with small inline
 * SVG/HTML (no chart library). The detailed classic dashboard lives at /classic/ (app.js etc.).
 * <html data-root="..."> = path prefix to the site root ("" at /, "../" one level down). */
(() => {
  "use strict";
  const TZ = "America/Chicago";
  const ROOT = document.documentElement.dataset.root ?? "";
  const HOME = document.documentElement.dataset.home ?? ROOT; // this language's home (coin pages, trades/); ROOT = data/assets/classic
  const I = window.LumiI18n || { t: (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s), locale: "en-US", en: true };
  const tr = I.t, LOC = I.locale;
  // free text from data/*.json: obj.i18n[lang][field] if present, else the English text (marked lang="en" on translated pages)
  const fx = (o, f, d) => { const v = o && o.i18n && o.i18n[I.lang] && o.i18n[I.lang][f]; if (v) return esc(v); const e = o && o[f] != null ? o[f] : (d || ""); if (e && !I.en && tr(String(e)) !== String(e)) return esc(tr(String(e))); return e && !I.en ? `<span lang="en" class="i18n-en">${esc(e)}</span>` : esc(e); };
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtPrice = (p) => {
    if (p == null || isNaN(p)) return "—";
    const a = Math.abs(p), d = a >= 1000 ? 0 : a >= 1 ? 3 : a >= 0.1 ? 4 : a >= 0.01 ? 5 : 6;
    return "$" + Number(p).toLocaleString("en-US", { minimumFractionDigits: Math.min(d, 2), maximumFractionDigits: d });
  };
  const num = (p) => fmtPrice(p).replace("$", "");
  const sgn = (v, d = 1) => (v > 0 ? "+" : "") + Number(v).toFixed(d) + "%";
  const pctSpan = (v, d = 1) => v == null || isNaN(v) ? `<span class="muted">${tr("n/a")}</span>` : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${sgn(v, d)}</span>`;
  const big = (v) => v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`;
  const tzA = (ts) => (new Intl.DateTimeFormat("en-US", { timeZone: TZ, timeZoneName: "short" }).formatToParts(new Date(ts)).find((p) => p.type === "timeZoneName") || {}).value || "";
  const ct = (ts, o) => { // US Central like the rest of the site; other languages keep the CDT/CST abbreviation (Intl would say GMT-5)
    const op = Object.assign({ timeZone: TZ, month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }, o || {});
    if (I.en || !op.timeZoneName) return new Date(ts).toLocaleString(LOC, op);
    delete op.timeZoneName; return new Date(ts).toLocaleString(LOC, op) + " " + tzA(ts);
  };
  const ctDate = (ts) => new Date(ts).toLocaleDateString(LOC, { timeZone: TZ, month: "short", day: "numeric" });
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
  const sigBadge = (label) => { const [c, w] = SIG[label] || ["neu", label || "n/a"]; return `<span class="pv-sig ${c}">${tr(w)}</span>`; };

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
    return `<svg class="pv-gauge" viewBox="0 0 200 108" role="img" aria-label="${tr("Market mood {v} out of 100", { v })}">
      ${seg(0, 0.25, "#f43f5e")}${seg(0.255, 0.45, "#fb923c")}${seg(0.455, 0.545, "#94a3b8")}${seg(0.55, 0.75, "#4ade80")}${seg(0.755, 1, "#22c55e")}
      <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="#e7ecf3" stroke-width="4" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="7" fill="#e7ecf3"/></svg>`;
  }
  const moodWord = (v) => tr(v < 25 ? "Fearful" : v < 45 ? "Cautious" : v <= 55 ? "Neutral" : v < 75 ? "Upbeat" : "Euphoric");

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
    const fg0 = context.fear_greed || {}, fg = fg0.source === "CoinMarketCap" && !fg0.error ? fg0 : {}; // CoinMarketCap only
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
    const evChip = (e) => `<li><span class="pv-ev-date">${new Date(e.date + "T12:00:00Z").toLocaleDateString(LOC, { month: "short", day: "numeric", timeZone: "UTC" })}<small>${days(e.date) === 0 ? tr("today") : days(e.date) === 1 ? tr("tomorrow") : tr("in {n}d", { n: days(e.date) })}</small></span><span title="${esc(e.text)}"${I.en ? "" : ' lang="en"'}><b>${esc(sym(e.id))}</b> ${esc(e.text.length > 120 ? e.text.slice(0, 117).replace(/\s+\S*$/, "") + "…" : e.text)}${e.url ? ` <a href="${esc(e.url)}" target="_blank" rel="noopener">${tr("source")}</a>` : ""}</span></li>`;
    const g = context.global || {}, dv = context.derivatives || {};
    $("pv-glance").innerHTML = `
      <article class="pv-card pv-btc">
        <div class="pv-card-top"><span class="pv-kicker">Bitcoin</span>${sigBadge(bs.label)}</div>
        <div class="pv-btc-price"><b class="mono">${fmtPrice(btc.price)}</b>${pctSpan(btc.change_24h, 2)}<small class="muted">24h</small></div>
        <div class="pv-btc-chart">${spark(lastHours(btc.history, 24 * 30), 300, 70)}<span class="pv-chart-cap">${tr("30 days")} · ${pctSpan(btc.change_30d)}</span></div>
        <div class="pv-btc-foot"><span>7d ${pctSpan(btc.change_7d)}</span><span class="pv-tfs">${tfRow}</span></div>
      </article>
      <article class="pv-card pv-mood">
        <div class="pv-card-top"><span class="pv-kicker">${tr("Market mood")}</span><span class="pv-mood-val"><b>${mood}</b>/100</span></div>
        ${gauge(mood)}
        <p class="pv-mood-word">${moodWord(mood)}</p>
        <ul class="pv-mood-parts">
          <li>${tr("<b>{up}/{n}</b> tracked coins up 24h", { up, n: ids.length })}</li>
          ${fg.value != null ? `<li>${tr("Fear &amp; Greed")} <b>${esc(fg.value)}</b> (${esc(tr(fg.classification || ""))})</li>` : ""}
          ${bs.score != null ? `<li>${tr("BTC signal")} <b>${esc(tr(bs.label))}</b> (${bs.score > 0 ? "+" : ""}${(+bs.score).toFixed(2)})</li>` : ""}
        </ul>
      </article>
      <article class="pv-card pv-events">
        <div class="pv-card-top"><span class="pv-kicker">${ICON.cal} ${tr("Coming up")}</span></div>
        ${ev.length ? `<ul class="pv-ev">${ev.slice(0, 3).map(evChip).join("")}</ul>` : `<p class="muted">${tr("No dated events in Lumi's catalyst list right now.")}</p>`}
        <div class="pv-stats">
          ${g.total_mcap_usd ? `<span><small>${tr("Total mcap")}</small>${big(g.total_mcap_usd)} ${pctSpan(g.mcap_change_24h_pct)}</span>` : ""}
          ${g.btc_dominance_pct ? `<span><small>${tr("BTC dominance")}</small>${g.btc_dominance_pct.toFixed(1)}%</span>` : ""}
          ${dv.funding_rate_pct != null ? `<span><small>${tr("BTC funding")}</small>${dv.funding_rate_pct.toFixed(4)}%</span>` : ""}
        </div>
      </article>`;
  }

  /* ---------- 2. heat-map tiles ---------- */
  function tileHref(id, sym) { return D.pages.has(sym.toLowerCase()) ? `${HOME}${sym.toLowerCase()}/` : `${ROOT}classic/#coins`; }
  function renderTiles(D) {
    const { prices, signals, trades } = D;
    const active = new Set((trades.trades || []).filter((t) => ["pending", "open"].includes(t.status)).map((t) => t.coin));
    const groups = (D.coins.groups || []).map((g) => ({ ...g, ids: D.ids.filter((id) => (prices.assets[id].group || "") === g.id) }));
    $("pv-tiles").innerHTML = groups.filter((g) => g.ids.length).map((g) => `<h3 class="pv-group">${esc(tr(g.label))}</h3><div class="pv-tile-grid">` + g.ids.map((id) => {
      const a = prices.assets[id], c = a.change_24h || 0, k = Math.min(Math.abs(c) / 8, 1);
      const rgb = c >= 0 ? "34,197,94" : "244,63,94";
      const s = (signals.coins || {})[id] || {};
      return `<a class="pv-tile" href="${tileHref(id, a.symbol)}" style="--heat:rgba(${rgb},${(0.07 + k * 0.38).toFixed(3)});--edge:rgba(${rgb},${(0.2 + k * 0.5).toFixed(3)})" aria-label="${esc(tr("{name} {price}, {chg} in 24 hours, signal {label}", { name: a.name, price: fmtPrice(a.price), chg: sgn(c), label: tr(s.label || "n/a") }))}">
        <div class="pv-tile-top"><b>${esc(a.symbol)}</b>${sigBadge(s.label)}</div>
        <div class="pv-tile-price mono">${fmtPrice(a.price)}</div>
        <div class="pv-tile-chg ${c >= 0 ? "up" : "down"}">${c >= 0 ? ICON.up : ICON.down}${sgn(c)}</div>
        <div class="pv-tile-spark">${spark(lastHours(a.history, 24 * 7), 120, 34, { sw: 1.4 })}</div>
        <div class="pv-tile-foot"><small class="muted">${esc(a.name)}</small>${active.has(id) ? `<span class="pv-idea" title="${tr("Active paper-trade idea")}">${tr("idea")}</span>` : ""}</div>
      </a>`;
    }).join("") + `</div>`).join("");
  }

  /* ---------- 3. visual trade cards ---------- */
  const zoneOf = (t) => t.entry_zone ? { lo: +t.entry_zone.low, hi: +t.entry_zone.high } : { lo: +t.entry, hi: +t.entry };
  function statusOf(t) {
    if (t.status === "pending") return ["pending", tr("Pending")];
    if (t.status === "open") return (t.targets_hit || []).some(Boolean) ? ["hit", tr("T1 hit · open")] : ["open", tr("Open")];
    if (t.status === "won" || t.status === "target") return ["hit", tr("Hit target")];
    if (t.status === "stopped" || t.status === "lost") return ["stopped", tr("Stopped")];
    return ["closed", tr(cap(t.status))];
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
    const marks = [{ v: stop, k: "stop", l: tr("Stop") }, ...tg.map((v, i) => ({ v, k: (t.targets_hit || [])[i] ? "tg hit" : "tg", l: `T${i + 1}${(t.targets_hit || [])[i] ? " ✓" : ""}` }))];
    marks.push(open ? { v: +t.entry, k: "fill", l: tr("Fill") } : { v: (lo + hi) / 2, k: "zone", l: tr("Entry"), txt: lo === hi ? num(lo) : `${num(lo)}–${num(hi)}` });
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
    return `<div class="pv-ladder" style="--rows:${nRows}" role="img" aria-label="${esc(tr("Price ladder: stop {stop}, entry {lo} to {hi}", { stop: num(stop), lo: num(lo), hi: num(hi) }) + (open ? tr(", filled {p}", { p: num(t.entry) }) : "") + tr(", targets {list}, price now {p}", { list: tg.map(num).join(", "), p: num(price) }))}">
      <div class="pv-lad-now" style="${pos(X(price))}"><b>${tr("now {p}", { p: num(price) })}</b></div>
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
    return `<div class="pv-rr" title="${t.status === "open" ? tr("Risk vs reward from the fill") : tr("Risk vs reward from the middle of the entry zone")}">
      <div class="pv-rr-bar"><span class="r" style="width:${(100 / tot).toFixed(1)}%"></span>${rr.map((v, i) => `<span class="g${i}" style="width:${(((v - (i ? rr[i - 1] : 0)) / tot) * 100).toFixed(1)}%"></span>`).join("")}</div>
      <div class="pv-rr-txt"><span class="down">${tr("risk {p}%", { p: mv(stop).toFixed(1) })}</span><span>R:R ${rr.map((v, i) => `<b>${v.toFixed(1)}</b><small>T${i + 1}</small>`).join(" · ")}</span><span class="up">T${tg.length} +${mv(tg[tg.length - 1]).toFixed(1)}%</span></div>
      <small class="muted">${L === 1 ? tr("spot, no leverage") : tr("{n}x paper leverage", { n: L })} · ${tr("% moves include leverage")}</small></div>`;
  }
  function missedHtml(t) {
    const p = t.missed_plan, mi = t.missed_it; let h = "";
    if (mi) h += `<p><b>${tr("Missed it?")}</b> ${mi.max_entry != null ? `${tr("Max entry")} <span class="mono">${num(mi.max_entry)}</span>. ` : ""}${fx(mi, "note")}</p>`;
    if (p && p.type !== "none") {
      const z = p.entry_zone || {};
      h += `<p><b>${tr("Plan B")} (${esc(tr(p.type))})${p.status ? ` · ${esc(tr(p.status))}` : ""}:</b> ${fx(p, "trigger")}</p>
        <p class="mono pv-mp">${tr("entry")} ${num(z.low)}–${num(z.high)} · ${tr("stop")} ${num(p.stop)} · ${tr("target")} ${num(p.target)} · ${(+p.leverage || lev(t)) === 1 ? tr("spot") : (+p.leverage || lev(t)) + "x"}</p>${p.reasoning ? `<p>${fx(p, "reasoning")}</p>` : ""}`;
    } else if (p && p.type === "none") h += `<p><b>${tr("Plan B")}:</b> ${tr("no good chase.")} ${fx(p, "reasoning")}</p>`;
    return h;
  }
  // breakdown / breakout entry (trade.alt_entry): one short line on the card, details under Read more
  function altLine(t) {
    const a = t.alt_entry, et = t.entry_type;
    if (!a || !a.trigger_rule) return "";
    const below = a.type === "breakdown", lvl = num(a.trigger_rule.level);
    if (t.status !== "pending") return et === a.type ? `<p class="pv-linked pv-alt">${below ? tr("Filled on a breakdown: 1h close below {lvl}", { lvl: `<span class="mono">${lvl}</span>` }) : tr("Filled on a breakout: 1h close above {lvl}", { lvl: `<span class="mono">${lvl}</span>` })}</p>` : "";
    if ((a.status || "watching") !== "watching") return "";
    const L = +a.leverage || lev(t);
    const lv = `<b class="mono">${lvl}</b>`;
    return `<p class="pv-linked pv-alt" title="${esc(a.reasoning || a.trigger || "")}">${below ? tr("Or on a 1h close below {lvl}", { lvl: lv }) : tr("Or on a 1h close above {lvl}", { lvl: lv })}${a.max_fill != null ? ` · ${tr("fills to {p}", { p: `<span class="mono">${num(a.max_fill)}</span>` })}` : ""} · ${tr("stop")} <span class="mono">${num(a.stop)}</span> · ${L === 1 ? tr("spot") : L + "x"}${L < lev(t) ? tr(", smaller size") : ""}</p>`;
  }
  function altHtml(t) {
    const a = t.alt_entry; if (!a || !a.trigger_rule) return "";
    return `<p><b>${esc(tr(cap(a.type) + " entry"))}${a.status ? ` · ${esc(tr(a.status))}` : ""}:</b> ${fx(a, "trigger")}</p>
      <p class="mono pv-mp">${tr("fills to {p}", { p: num(a.max_fill) })} · ${tr("stop")} ${num(a.stop)} · ${(+a.leverage || lev(t)) === 1 ? tr("spot") : (+a.leverage || lev(t)) + "x"}${a.conviction ? ` · ${esc(tr(cap(a.conviction) + " conviction"))}` : ""}</p>${a.reasoning ? `<p>${fx(a, "reasoning")}</p>` : ""}`;
  }
  // "5x · High conviction" (leverage is picked per idea, 1x-10x, by conviction; 1x = spot)
  function levBadge(t) {
    const L = lev(t), c = String(t.conviction || "").toLowerCase();
    return `<div class="pv-lev c-${esc(c || "na")}" title="${esc(t.leverage_reason || tr("Leverage set per idea (1x-10x) by conviction"))}">
      <b>${L === 1 ? tr("Spot · 1x") : L + "x"}</b>${c ? `<span>${esc(tr(cap(c) + " conviction"))}</span>` : ""}
      <i class="pv-lev-meter" aria-hidden="true">${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => `<u class="${n <= L ? "on" : ""}"></u>`).join("")}</i></div>`;
  }
  function tradeCard(t) {
    const a = D.prices.assets[t.coin], an = (D.analysis.coins || {})[t.coin] || {};
    const [cls, lbl] = statusOf(t), long = t.direction !== "short", L = lev(t);
    const page = D.pages.has(a.symbol.toLowerCase()) ? `<a class="pv-more-link" href="${HOME}${a.symbol.toLowerCase()}/">${tr("{sym} analysis &amp; levels", { sym: esc(a.symbol) })} ${ICON.arrow}</a>` : "";
    let live = "";
    if (t.status === "open" && t.unrealized_pnl_pct != null) live = `<span class="pv-pnl">P&amp;L ${pctSpan(t.unrealized_pnl_pct)}<small> (${t.last_checked ? ct(t.last_checked, { month: undefined, day: undefined }) : tr("tracker")})</small></span>`;
    else if (t.status === "pending" && t.expiry) live = `<span class="muted pv-exp">${ICON.clock} ${tr("expires {when}", { when: ct(t.expiry) })}</span>`;
    return `<article class="slate-card pv-trade ${esc(t.status)}" data-slate="${esc(t.id)}" data-coin="${esc(t.coin)}" data-sym="${esc(a.symbol)}" data-lev="${L}" data-dir="${esc(t.direction)}" data-cb="${esc(D.cb[t.coin] || "")}">
      <div class="pv-trade-top">
        <span class="pv-dir ${long ? "long" : "short"}" title="${long ? tr("Long") : tr("Short")}">${long ? ICON.up : ICON.down}</span>
        <div class="pv-trade-id"><b>${esc(a.symbol)}</b> <span class="muted">${long ? tr("Long") : tr("Short")}</span></div>
        <span class="pv-status ${cls}">${lbl}</span>
      </div>
      ${levBadge(t)}
      <div class="pv-tags"><span class="pv-tag">${esc(tr(cap(t.timeframe || "short-term")))}</span>${t.plan_type ? `<span class="pv-tag">${esc(tr(t.plan_type + " plan"))}</span>` : ""}<span class="pv-tag mono">${esc(t.id)}</span>${live}</div>
      <p class="pv-thesis">${an.bias ? fx({ ...an, bias: cap(an.bias) }, "bias") : fx({ ...t, trigger: cap(t.trigger || "") }, "trigger")}</p>
      ${ladder(t, a.price)}
      ${rrBar(t)}
      ${altLine(t)}
      ${t.parent_id ? `<p class="pv-linked">${tr("Follow-up of {id}", { id: esc(t.parent_id) })}${t.trigger ? `: ${fx(t, "trigger")}` : ""}</p>` : ""}
      <details class="why"><summary>${tr('Read more: reasoning &amp; "missed it?"')}</summary>
        ${t.leverage_reason ? `<p class="pv-levwhy"><b>${tr("Why {lev}", { lev: L === 1 ? tr("spot (1x)") : L + "x" })}${t.conviction ? ` · ${esc(tr(cap(t.conviction) + " conviction"))}` : ""}:</b> ${fx(t, "leverage_reason")}</p>` : ""}
        <p>${fx(t, "reasoning")}</p>${altHtml(t)}${missedHtml(t)}${t.size_note ? `<p>${fx(t, "size_note")}</p>` : ""}${t.leverage_note ? `<p class="muted">${fx(t, "leverage_note")}</p>` : ""}
      </details>
      <div class="pv-card-links">${D.pages.has("trades") ? `<a class="pv-more-link" href="${HOME}trades/${encodeURIComponent(t.id)}/">${tr("Trade {id} page", { id: esc(t.id) })} ${ICON.arrow}</a>` : ""}${page}</div>
    </article>`;
  }
  function renderSlate(D) {
    const all = D.trades.trades || [], sl = (D.trades.slate || {}).coins || {};
    const act = all.filter((t) => ["pending", "open"].includes(t.status)).sort((a, b) => (a.status === "open" ? 0 : 1) - (b.status === "open" ? 0 : 1));
    $("slate-grid").innerHTML = act.length ? act.map(tradeCard).join("") : `<p class="muted">${tr("No active ideas right now. That's a valid call too.")}</p>`;
    const none = Object.entries(sl).filter(([id, e]) => !e.trade_id && D.prices.assets[id]);
    $("pv-nosetup").innerHTML = none.length ? `<details class="pv-fold"><summary>${tr(none.length > 1 ? "{n} coins with no setup right now:" : "{n} coin with no setup right now:", { n: none.length })} ${none.map(([id]) => esc(D.prices.assets[id].symbol)).join(", ")}</summary>
      <ul class="pv-nosetup">${none.map(([id, e]) => `<li><b>${esc(D.prices.assets[id].symbol)}</b> ${fx(e, "note")}</li>`).join("")}</ul></details>` : "";
    if (D.trades.slate && D.trades.slate.as_of) {
      const s = $("slate-sched"); let m = s.querySelector(".pv-asof"); if (!m) { m = document.createElement("span"); m.className = "pv-asof"; s.appendChild(m); }
      m.textContent = " · " + tr("Slate as of {when}", { when: ct(D.trades.slate.as_of) });
    }
  }


  /* ---------- signals (indicator reads per coin) ---------- */
  const READ = (l) => ({ "Strong Buy": ["sb", "Strong Buy", 2], Buy: ["b", "Buy", 1], Neutral: ["n", "Neutral", 0], Sell: ["s", "Sell", -1], "Strong Sell": ["ss", "Strong Sell", -2] }[l] || ["n", l || "n/a", 0]);
  const ARROW = { sb: "M12 3l8 8-1.8 1.8L12 6.6l-6.2 6.2L4 11zm0 7l8 8-1.8 1.8-6.2-6.2-6.2 6.2L4 18z", b: "M12 4 4 13h5v7h6v-7h5z",
    n: "M4 11h11V7l5 5-5 5v-4H4z", s: "M12 20 4 11h5V4h6v7h5z", ss: "M12 21l-8-8 1.8-1.8 6.2 6.2 6.2-6.2L20 13zm0-7L4 6l1.8-1.8L12 10.4l6.2-6.2L20 6z" };
  const arrowSvg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="${ARROW[k] || ARROW.n}"/></svg>`;
  const IND = [["rsi", "RSI"], ["macd", "MACD"], ["ema", tr("EMA trend")], ["ema200", "EMA200"], ["bb", "Bollinger"], ["stochrsi", "StochRSI"], ["volume", tr("Volume")]];
  const st = (s) => String(s || "").split(" · ").map((x) => tr(x)).join(" · "); // signal states ("lower half · squeeze")
  const TFS = ["1h", "4h", "1d"];
  const dirOf = (pts) => (pts > 0 ? "up" : pts < 0 ? "down" : "flat");
  const tri = { up: '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 1 9.5 9h-9z" fill="currentColor"/></svg>', down: '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 9 .5 1h9z" fill="currentColor"/></svg>', flat: '<svg viewBox="0 0 10 10" aria-hidden="true"><rect x="1" y="4" width="8" height="2" rx="1" fill="currentColor"/></svg>' };
  function sigLine(c) {
    const tf = c.timeframes || {}, reads = TFS.filter((k) => tf[k]).map((k) => READ(tf[k].label)[2]);
    const bull = reads.filter((v) => v > 0).length, bear = reads.filter((v) => v < 0).length, n = reads.length;
    const head = bull === n ? tr("All {n} timeframes bullish", { n }) : bear === n ? tr("All {n} timeframes bearish", { n })
      : bull > bear ? tr("{k} of {n} timeframes bullish", { k: bull, n }) : bear > bull ? tr("{k} of {n} timeframes bearish", { k: bear, n })
      : bull ? tr("Mixed: {bull} bullish, {bear} bearish", { bull, bear }) : tr("No clear lean on any timeframe");
    const r = tf["1d"] && tf["1d"].indicators && tf["1d"].indicators.rsi, rv = r && r.value != null ? Math.round(r.value) : null;
    const rsi = rv == null ? "" : tr("; daily RSI {v}, {state}", { v: rv, state: tr(rv >= 70 ? "overbought" : rv <= 30 ? "oversold" : rv >= 60 ? "strong, not overbought" : rv <= 40 ? "weak, not oversold" : "mid-range") });
    const e = tf["1d"] && tf["1d"].indicators && tf["1d"].indicators.ema;
    const trend = e ? (e.points >= 1 ? tr("; daily uptrend") : e.points <= -1 ? tr("; daily downtrend") : "") : "";
    return head + rsi + trend + tr(".");
  }
  function signalCard(id) {
    const c = (D.signals.coins || {})[id], a = D.prices.assets[id];
    const [k, lbl0] = READ(c.label), lbl = tr(lbl0), sc = +c.score || 0, tf = c.timeframes || {};
    const pos = ((Math.max(-1, Math.min(1, sc)) + 1) / 2) * 100;
    const chips = IND.filter(([key]) => TFS.some((t) => tf[t] && tf[t].indicators && tf[t].indicators[key])).map(([key, name]) => {
      const per = TFS.map((t) => { const x = tf[t] && tf[t].indicators && tf[t].indicators[key]; return x ? { t, d: dirOf(+x.points || 0), st: x.state, v: x.value } : null; }).filter(Boolean);
      const net = per.reduce((s2, x) => s2 + (x.d === "up" ? 1 : x.d === "down" ? -1 : 0), 0);
      const tip = per.map((x) => `${x.t}: ${st(x.st)}${x.v != null && key === "rsi" ? ` (${(+x.v).toFixed(0)})` : ""}`).join(" · ");
      return `<span class="sg-chip ${net > 0 ? "up" : net < 0 ? "down" : "flat"}" title="${esc(name + " — " + tip)}"><b>${name}</b>${per.map((x) => `<i class="${x.d}" aria-label="${x.t} ${tr(x.d)}">${tri[x.d]}</i>`).join("")}</span>`;
    }).join("");
    return `<article class="sg-card k-${k}" aria-label="${esc(tr("{sym} signal {label}, score {score}", { sym: a.symbol, label: lbl, score: sc.toFixed(2) }))}">
      <div class="sg-top"><a href="${tileHref(id, a.symbol)}"><b>${esc(a.symbol)}</b></a><span class="mono muted">${fmtPrice(a.price)}</span></div>
      <div class="sg-read"><span class="sg-arrow">${arrowSvg(k)}</span><b>${esc(lbl)}</b></div>
      <div class="sg-meter" title="${tr("Composite score {s} (−1 to +1)", { s: (sc > 0 ? "+" : "") + sc.toFixed(2) })}"><span class="sg-track"><i style="left:${pos.toFixed(1)}%"></i></span><span class="sg-score mono">${sc > 0 ? "+" : ""}${sc.toFixed(2)}</span></div>
      <div class="sg-tfs">${TFS.filter((t) => tf[t]).map((t) => { const [tk, tl] = READ(tf[t].label); return `<span class="sg-tf k-${tk}"><small>${t}</small>${esc(tr(tl))}</span>`; }).join("")}</div>
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
    $("sg-sum").innerHTML = `<span class="up">${tr("{n} buy", { n: counts[0] })}</span> · <span>${tr("{n} neutral", { n: counts[1] })}</span> · <span class="down">${tr("{n} sell", { n: counts[2] })}</span>` +
      (D.signals.generated_utc ? ` <span class="muted">· ${tr("computed {when}", { when: ct(D.signals.generated_utc) })}</span>` : "");
  }
  function wireSignalSort() {
    document.querySelectorAll("[data-sgsort]").forEach((b) => b.addEventListener("click", () => {
      sigSort = b.dataset.sgsort;
      document.querySelectorAll("[data-sgsort]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      if (D) renderSignals(D);
    }));
  }

  /* ---------- 4. (scorecard removed Oct 22, 2026: the paper-trade track record is no longer published) ---------- */

  /* ---------- 5. analysis, collapsed ---------- */
  function projBar(pr, price, sup, res) {
    let bear, base, bull, cap2;
    if (pr && pr.bear != null && pr.bull != null) { bear = +pr.bear; base = +pr.base; bull = +pr.bull; cap2 = tr("{n}-day projection", { n: pr.horizon_days || 7 }); }
    else return "";
    const mn = Math.min(bear, price), mx = Math.max(bull, price), r = mx - mn || 1, X = (v) => ((v - mn) / r) * 100;
    const chg = (v) => sgn(((v - price) / price) * 100);
    return `<div class="pv-proj" aria-label="${esc(tr("{cap}: bear {bear}, base {base}, bull {bull}; price {p}", { cap: cap2, bear: num(bear), base: num(base), bull: num(bull), p: num(price) }))}">
      <div class="pv-proj-cap"><span class="muted">${cap2}</span></div>
      <div class="pv-proj-track"><span class="seg" style="left:${X(bear)}%;width:${X(bull) - X(bear)}%"></span>
        <i class="pt bear" style="left:${X(bear)}%"></i><i class="pt base" style="left:${X(base)}%"></i><i class="pt bull" style="left:${X(bull)}%"></i>
        <b class="now" style="left:${X(price)}%" title="${tr("now {p}", { p: num(price) })}"></b></div>
      <div class="pv-proj-lbl"><span class="down">${tr("Bear")} ${num(bear)}<small>${chg(bear)}</small></span><span>${tr("Base")} ${num(base)}<small>${chg(base)}</small></span><span class="up">${tr("Bull")} ${num(bull)}<small>${chg(bull)}</small></span></div></div>`;
  }
  function renderAnalysis(D) {
    const an = D.analysis.coins || {};
    $("pv-an-asof").textContent = D.analysis.as_of ? tr("Reviewed {when}", { when: ct(D.analysis.as_of) }) : "";
    $("pv-analysis").innerHTML = D.ids.filter((id) => an[id]).map((id) => {
      const c = an[id], a = D.prices.assets[id], s = (D.signals.coins || {})[id] || {}, tf = s.timeframes || {};
      const tfTxt = ["1h", "4h", "1d"].filter((k) => tf[k]).map((k) => `${k} ${tr(tf[k].label)}`).join(" · ");
      const sup = (c.support || [])[0], res = (c.resistance || [])[0];
      const summary = `${fx({ ...c, bias: cap(c.bias) }, "bias")}. ` + (sup != null && res != null ? tr("Nearest support {s}, resistance {r}", { s: `<b class="mono">${num(sup)}</b>`, r: `<b class="mono">${num(res)}</b>` }) : "") + (tfTxt ? tr("; signals {list}.", { list: esc(tfTxt) }) : ".");
      const page = D.pages.has(a.symbol.toLowerCase()) ? `<a class="pv-more-link" href="${HOME}${a.symbol.toLowerCase()}/">${tr("Open the {sym} page", { sym: esc(a.symbol) })} ${ICON.arrow}</a>` : "";
      return `<article class="pv-card pv-an">
        <div class="pv-an-top"><a href="${tileHref(id, a.symbol)}"><b>${esc(a.symbol)}</b> <span class="muted">${esc(a.name)}</span></a><span class="mono">${fmtPrice(a.price)} ${pctSpan(a.change_24h)}</span>${sigBadge(s.label)}</div>
        <p class="pv-an-sum">${summary}</p>
        ${projBar(c.projection, a.price, sup, res)}
        <details class="pv-an-full"><summary>${tr("Read full analysis")}</summary>
          <div class="pv-lv"><span><small>${tr("Support")}</small>${(c.support || []).map(num).join(" · ") || "—"}</span><span><small>${tr("Resistance")}</small>${(c.resistance || []).map(num).join(" · ") || "—"}</span></div>
          ${I.en || (c.i18n && c.i18n[I.lang] && c.i18n[I.lang].commentary) ? "" : `<p class="muted i18n-note">${tr("Lumi writes this commentary in English; numbers and levels are the same in every language.")}</p>`}<p>${fx(c, "commentary")}</p>
          ${(c.catalysts || []).length ? `<h4>${tr("Catalysts")}</h4><ul class="pv-cat">${c.catalysts.map((x) => `<li><span class="pv-tag">${esc(tr(x.kind))}</span> <b>${esc(x.date)}</b> ${fx(x, "text")}${x.url ? ` <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source || tr("source"))}</a>` : ""}</li>`).join("")}</ul>` : ""}
          ${(c.sources || []).length ? `<h4>${tr("Sources")}</h4><ul class="pv-src"${I.en ? "" : ' lang="en"'}>${c.sources.map((x) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a></li>`).join("")}</ul>` : ""}
        </details>${page}
      </article>`;
    }).join("");
  }

  // the update log stays, minus trade results (closed WON/LOST/STOPPED at …, win rate …): the track record is private
  // same rules as scripts/privacy.py (which already scrubs the data files; this is a backstop)
  const TID = String.raw`\bT\d{3}[a-z]?\b`, RES = String.raw`(?:stopped|stop(?:ped)?\s+out|took\s+out|taken\s+out|won(?!['’]t)|lost|closed\s+(?:as\s+)?(?:WON|LOST|STOPPED|EXPIRED|CLOSED)|hit\s+(?:its|the)\s+stop|realized|result(?:s|ed)?)`;
  const BAD = [new RegExp(TID + String.raw`[^()]{0,90}?\b` + RES + String.raw`\b`, "i"), new RegExp(String.raw`\b` + RES + String.raw`\b[^()]{0,70}?` + TID, "i"),
    new RegExp(TID + String.raw`.{0,120}?\b(?:stopped|won(?!['’]t)|lost)\b.{0,40}?[+\-−]\d`, "i"), /\b(?:win\s*rate|track\s+record|scorecard|cumulative\s+(?:paper\s+)?P&L|equity\s+curve|hit\s+rate)\b/i,
    /\b(?:stopped|won(?!['’]t)|lost|closed)\b.{0,80}?[+\-−]\d+(?:\.\d+)?%\s*(?:at\s*\d+x|on\s+margin)/i, /\b\d+\s*W\s*\/\s*\d+\s*L\b/, /^\W*closed:\s*\d+/i, /\bstays?\s+as\s+recorded\b/i];
  const noRecord = (t) => String(t || "")
    .replace(/\b(T\d{3}[a-z]?) \(?(\w+)\)?(?: (?:long|short) (?:[\d.]+x|spot))? closed (?:as )?(?:WON|LOST|STOPPED|EXPIRED|CLOSED)\b[^;]*?(?=;|\.(?:\s|$)|$)/g, "$1 $2 idea closed")
    .replace(/;?\s*\bclosed: \d+(?=[;.])/g, "")
    .split(/(?<=[.;])\s+/).filter((seg) => !BAD.some((re) => re.test(seg))).join(" ").replace(/^Trade events:\s*\.?$/, "").replace(/;$/, ".").trim();
  function renderLog(D) {
    const e = ((D.log || {}).entries || []).slice(0, 10);
    $("pv-log").innerHTML = e.map((x) => ({ t: x.t, kind: x.kind, text: noRecord(x.text) })).filter((x) => x.text).map((x) => `<li><span class="mono muted">${ct(x.t)}</span> <span class="pv-tag">${esc(tr(x.kind))}</span> ${fx(x, "text")}</li>`).join("");
  }
  function renderFoot(D) {
    const links = D.ids.map((id) => D.prices.assets[id].symbol).filter((s) => D.pages.has(s.toLowerCase()));
    if (!$("pv-foot-coins")) return; // the main page has the static block from build_pages.py
    $("pv-foot-coins").innerHTML = links.length ? tr("Coin pages:") + " " + links.map((s) => `<a href="${HOME}${s.toLowerCase()}/">${esc(s)}</a>`).join(" · ") : "";
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
      [renderGlance, renderTiles, renderSlate, renderSignals, renderAnalysis, renderLog, renderFoot].forEach((f) => { try { f(D); } catch (e) { console.warn("preview:", f.name, e); } });
      document.querySelectorAll("details").forEach((d) => { const k = d.closest("[data-slate]")?.dataset.slate || d.querySelector("summary")?.textContent; if (openKeep.includes(k)) d.open = true; });
      $("pv-snap").innerHTML = `<span class="dot" aria-hidden="true"></span> ${tr("Data as of {when}", { when: ct(prices.updated_utc) })}`;
    } catch (e) {
      $("pv-snap").textContent = tr("Couldn't load data. Try refreshing.");
      console.warn("preview load failed", e);
    }
  }
  const boot = () => { wireSignalSort(); load(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
  setInterval(load, 5 * 60e3);
})();
