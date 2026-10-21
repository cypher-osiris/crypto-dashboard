/* Crypto dashboard — renders everything from data/*.json. No build step. */
(() => {
  "use strict";
  const TZ = "America/Chicago";
  const DAY = 864e5;
  const COLORS = { line: "#60a5fa", sup: "#22c55e", res: "#f43f5e", bull: "#22c55e", base: "#f5b041", bear: "#f43f5e", grid: "rgba(148,163,184,0.08)", tick: "#7d8ba0" };
  const areaFill = (ctx) => {
    const { chart } = ctx; const { ctx: c, chartArea } = chart;
    if (!chartArea) return "rgba(96,165,250,0.08)";
    const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, "rgba(96,165,250,0.28)"); g.addColorStop(1, "rgba(96,165,250,0)");
    return g;
  };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function fmtPrice(p) {
    if (p == null || isNaN(p)) return "—";
    const a = Math.abs(p);
    const d = a >= 1000 ? 0 : a >= 1 ? 3 : a >= 0.1 ? 4 : a >= 0.01 ? 5 : 6;
    return "$" + Number(p).toLocaleString("en-US", { minimumFractionDigits: Math.min(d, 2), maximumFractionDigits: d });
  }
  const num = (p) => fmtPrice(p).replace("$", "");
  function pct(v, digits = 2) {
    if (v == null || isNaN(v)) return '<span class="muted">n/a</span>';
    const cls = v > 0 ? "up" : v < 0 ? "down" : "";
    return `<span class="${cls}">${v > 0 ? "+" : ""}${Number(v).toFixed(digits)}%</span>`;
  }
  function ct(ts, withTime = true) {
    if (!ts) return "—";
    const d = new Date(ts);
    const opts = { timeZone: TZ, month: "short", day: "numeric", year: "numeric" };
    if (withTime) Object.assign(opts, { hour: "numeric", minute: "2-digit", timeZoneName: "short" });
    return d.toLocaleString("en-US", opts);
  }
  function chip(v, label) {
    const cls = v == null || isNaN(v) ? "flat" : v > 0 ? "up" : v < 0 ? "down" : "flat";
    const txt = v == null || isNaN(v) ? "n/a" : `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%`;
    return `<span class="chip ${cls}">${label ? `<span class="lbl">${label}</span>` : ""}${txt}</span>`;
  }
  // Inline SVG sparkline from [[ts, price], ...]
  function spark(history, w = 84, h = 26, points = 168) {
    const pts = history.slice(-points).map((p) => p[1]);
    if (pts.length < 2) return "";
    const step = Math.max(1, Math.floor(pts.length / 60));
    const ys = pts.filter((_, i) => i % step === 0 || i === pts.length - 1);
    const lo = Math.min(...ys), hi = Math.max(...ys), rng = hi - lo || 1;
    const xy = ys.map((v, i) => [(i / (ys.length - 1)) * w, h - 2 - ((v - lo) / rng) * (h - 4)]);
    const d = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
    const up = ys[ys.length - 1] >= ys[0];
    const c = up ? "#22c55e" : "#f43f5e";
    const gid = "g" + Math.random().toString(36).slice(2, 8);
    return `<svg focusable="false" class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".28"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs>
      <path d="${d}L${w} ${h}L0 ${h}Z" fill="url(#${gid})"/><path d="${d}" fill="none" stroke="${c}" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }
  // fallback colors; data/coins.json "colors" override/extend these at load time
  const COIN_COLORS = { HBAR: ["#3a3a3a", "#0b0b0b"], XLM: ["#5b6cff", "#1b1f4a"], XRP: ["#2d3748", "#0a0f17"], ZBCN: ["#06b6d4", "#0e3a52"], AXL: ["#6366f1", "#111827"], BTC: ["#f7931a", "#7a3e00"] };
  const uniq = (a) => [...new Set(a)];
  // groups: [{id,label,coins:[ids]}] from prices.json (written from data/coins.json) or coins.json; fallback one group
  function groupsOf(prices) {
    const cfg = Dash.state.coincfg;
    let g = prices.groups && prices.groups.length ? prices.groups : null;
    if (!g && cfg && cfg.groups) g = cfg.groups.map((x) => ({ ...x, coins: cfg.coins.filter((c) => c.group === x.id).map((c) => c.id) }));
    if (!g) g = [{ id: "all", label: "Coins", coins: prices.coins }];
    g = g.map((x) => ({ ...x, coins: x.coins.filter((id) => prices.assets[id]) })).filter((x) => x.coins.length);
    const seen = new Set(g.flatMap((x) => x.coins)), rest = prices.coins.filter((id) => !seen.has(id) && prices.assets[id]);
    if (rest.length) g.push({ id: "other", label: "Other", coins: rest });
    return g;
  }
  const allIds = (prices) => groupsOf(prices).flatMap((g) => g.coins);
  const shortDate = (ms) => new Date(ms).toLocaleDateString("en-US", { timeZone: TZ, month: "short", day: "numeric" });
  // Day-aligned ticks (~CT midnight, 05:00 UTC) so labels never repeat.
  function dayTicks(scale) {
    const span = (scale.max - scale.min) / DAY;
    const step = Math.max(1, Math.ceil(span / 6));
    let t = Math.ceil((scale.min - 5 * 36e5) / DAY) * DAY + 5 * 36e5;
    const ticks = [];
    for (; t <= scale.max; t += step * DAY) ticks.push({ value: t });
    scale.ticks = ticks;
  }

  const Dash = (window.Dash = window.Dash || {});
  Object.assign(Dash, { fmtPrice, num, pct, chip, ct, esc, spark, COLORS, COIN_COLORS, dayTicks, shortDate, groupsOf, allIds, charts: {}, state: {} });
  let readyResolve; Dash.ready = new Promise((r) => (readyResolve = r));

  async function getJSON(name, optional) {
    const r = await fetch(`data/${name}?v=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) { if (optional) return null; throw new Error(`${name}: HTTP ${r.status}`); }
    return r.json();
  }
  function sourcesHTML(list) {
    if (!list || !list.length) return "";
    return "Sources:<ul>" + list.map((s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></li>`).join("") + "</ul>";
  }

  /* ---------- price chart with S/R lines + projection band ---------- */
  function priceChart(canvas, asset, an, opts = {}) {
    if (!window.Chart) return null;
    const hist = asset.history.map(([t, p]) => ({ x: t, y: p }));
    const last = hist[hist.length - 1];
    const datasets = [{
      label: asset.symbol, data: hist, borderColor: COLORS.line, borderWidth: 1.6, pointRadius: 0,
      tension: 0.15, fill: "start", backgroundColor: areaFill, order: 1,
    }];
    let xMax = last.x;
    const pr = an && an.projection;
    if (pr && last) {
      const end = last.x + (pr.horizon_days || 7) * DAY;
      xMax = end;
      const seg = (y) => [{ x: last.x, y: last.y }, { x: end, y }];
      datasets.push(
        { label: `Bear ${num(pr.bear)}`, data: seg(pr.bear), borderColor: COLORS.bear, borderDash: [4, 4], borderWidth: 1.4, pointRadius: [0, 3], fill: false, order: 2 },
        { label: `Bull ${num(pr.bull)}`, data: seg(pr.bull), borderColor: COLORS.bull, borderDash: [4, 4], borderWidth: 1.4, pointRadius: [0, 3], fill: { target: "-1", above: "rgba(210,153,34,0.12)", below: "rgba(210,153,34,0.12)" }, order: 2 },
        { label: `Base ${num(pr.base)}`, data: seg(pr.base), borderColor: COLORS.base, borderWidth: 1.8, pointRadius: [0, 3], fill: false, order: 2 },
      );
    }
    const ann = {};
    const addLine = (v, kind, i) => {
      ann[`${kind}${i}`] = {
        type: "line", yMin: v, yMax: v, borderColor: kind === "s" ? COLORS.sup : COLORS.res, borderWidth: 1, borderDash: [6, 4],
        label: { display: true, content: `${kind === "s" ? "S" : "R"} ${num(v)}`, position: "start", backgroundColor: "rgba(13,17,23,0.75)", color: kind === "s" ? COLORS.sup : COLORS.res, font: { size: 10 }, padding: 3 },
      };
    };
    (an?.support || []).forEach((v, i) => addLine(v, "s", i));
    (an?.resistance || []).forEach((v, i) => addLine(v, "r", i));
    if (pr && last) {
      ann.now = { type: "line", xMin: last.x, xMax: last.x, borderColor: "rgba(139,152,169,0.4)", borderWidth: 1, label: { display: true, content: "now", position: "end", color: COLORS.tick, backgroundColor: "transparent", font: { size: 10 } } };
    }
    for (const m of opts.markers || []) ann[m.id] = m;

    return new Chart(canvas, {
      type: "line",
      data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false, parsing: false, normalized: true,
        interaction: { mode: "nearest", axis: "x", intersect: false },
        scales: {
          x: { type: "linear", min: hist[0].x, max: xMax, afterBuildTicks: dayTicks, grid: { color: COLORS.grid }, ticks: { color: COLORS.tick, callback: (v) => shortDate(v) } },
          y: { grid: { color: COLORS.grid }, ticks: { color: COLORS.tick, callback: (v) => num(v) } },
        },
        plugins: {
          legend: { display: !!pr, position: "bottom", labels: { color: COLORS.tick, boxWidth: 12, boxHeight: 2, font: { size: 11 }, filter: (i) => i.datasetIndex > 0 } },
          tooltip: { callbacks: { title: (it) => ct(it[0].parsed.x), label: (it) => `${it.dataset.label}: ${fmtPrice(it.parsed.y)}` } },
          annotation: { annotations: ann },
        },
      },
    });
  }

  /* ---------- sections ---------- */
  function renderTicker(prices) {
    const ids = uniq([...allIds(prices), prices.backdrop]).filter((id) => prices.assets[id]);
    const item = (id, dup) => {
      const a = prices.assets[id];
      return `<a class="tk${dup ? " dup" : ""}" href="#${document.getElementById("coin-" + id) || prices.coins.includes(id) ? "coin-" + id : "market"}"${dup ? ' aria-hidden="true" tabindex="-1"' : ""}>
        <span class="s">${esc(a.symbol)}</span><span class="p" data-lp="${id}">${fmtPrice(a.price)}</span><span data-lc="${id}">${chip(a.change_24h)}</span>${spark(a.history, 56, 18, 72)}</a>`;
    };
    $("ticker").innerHTML = ids.map((i) => item(i, false)).join("") + ids.map((i) => item(i, true)).join("");
  }

  function reveal() {
    const els = document.querySelectorAll(".reveal:not(.in)");
    if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) { els.forEach((e) => e.classList.add("in")); return; }
    const io = new IntersectionObserver((ents) => ents.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -40px 0px" });
    els.forEach((e) => io.observe(e));
  }

  function renderHeader(prices, analysis) {
    $("updated").textContent = ct(prices.updated_utc);
    $("analysis-meta").innerHTML = `Commentary as of ${esc(ct(analysis.as_of))} · ${esc(analysis.author || "")}` +
      (analysis.label ? `<br>${esc(analysis.label)}` : "");
  }

  function renderBackdrop(prices, analysis) {
    const b = prices.assets[prices.backdrop];
    const an = analysis.backdrop || {};
    $("btc-price").textContent = fmtPrice(b.price);
    $("btc-price").dataset.lp = prices.backdrop;
    $("btc-chg").innerHTML = `<span data-lc="${prices.backdrop}" data-lbl="24h">${chip(b.change_24h, "24h")}</span>` + chip(b.change_7d, "7d") + chip(b.change_30d, "30d");
    if (an.bias) $("btc-chg").insertAdjacentHTML("afterend", `<div class="bias">${esc(an.bias)}</div>`);
    $("btc-commentary").textContent = an.commentary || "";
    $("btc-sources").innerHTML = sourcesHTML(an.sources);
    Dash.charts["__backdrop"] = priceChart($("chart-bitcoin"), b, an);
  }

  // charts below the fold are created only when their card approaches the viewport (keeps 12+ cards fast)
  let chartIO = null;
  const pendingCharts = new Map();
  function lazyChart(el, make) {
    if (!("IntersectionObserver" in window)) { make(); return; }
    if (!chartIO) chartIO = new IntersectionObserver((ents) => ents.forEach((e) => {
      if (!e.isIntersecting) return;
      const f = pendingCharts.get(e.target); pendingCharts.delete(e.target); chartIO.unobserve(e.target); if (f) f();
    }), { rootMargin: "400px 0px" });
    pendingCharts.set(el, make); chartIO.observe(el);
  }
  function renderCoins(prices, analysis, trades) {
    const root = $("coin-grid");
    root.innerHTML = "";
    const groups = groupsOf(prices);
    const tabs = $("coin-tabs");
    if (tabs) tabs.innerHTML = groups.length > 1 ? groups.map((g) => `<a href="#grp-${esc(g.id)}" class="grp-link">${esc(g.label)} <small>${g.coins.length}</small></a>`).join("") : "";
    for (const g of groups) {
    const sec = document.createElement("div"); sec.className = "coin-group"; sec.id = `grp-${g.id}`;
    if (groups.length > 1) sec.innerHTML = `<h3 class="grp-h">${esc(g.label)}</h3>`;
    const grid = document.createElement("div"); grid.className = "coin-grid-inner"; sec.appendChild(grid); root.appendChild(sec);
    for (const id of g.coins) {
      const a = prices.assets[id];
      const an = (analysis.coins || {})[id] || {};
      const pr = an.projection;
      const el = document.createElement("article");
      const dir = (a.change_24h || 0) >= 0 ? "is-up" : "is-down";
      const [c1, c2] = COIN_COLORS[a.symbol] || [];
      el.className = `coin reveal ${dir}`;
      el.id = `coin-${id}`;
      el.innerHTML = `
        <div class="coin-head">
          <div class="coin-id">
            <div class="coin-mark" style="--c1:${c1 || "#334155"};--c2:${c2 || "#0f172a"}">${esc(a.symbol)}</div>
            <div><h4 class="name">${esc(a.symbol)}<small>${esc(a.name)}${a.market_cap_rank ? " · rank #" + a.market_cap_rank : ""}</small></h4>
              ${an.bias ? `<div class="bias">${esc(an.bias)}</div>` : ""}</div>
          </div>
          <div class="coin-right">
            ${spark(a.history)}
            <div><div class="price" data-lp="${id}">${fmtPrice(a.price)}</div>
              <div class="chg"><span data-lc="${id}" data-lbl="24h">${chip(a.change_24h, "24h")}</span>${chip(a.change_7d, "7d")}</div>
              <div class="src-tag" data-src="${id}">snapshot</div></div>
          </div>
        </div>
        <div class="coin-chart"><canvas id="chart-${id}" role="img" aria-label="${esc(a.name)} (${esc(a.symbol)}) price, last 30 days, with support and resistance levels"></canvas></div>
        <div class="levels">
          <div class="lv sup"><small>Support</small><b>${(an.support || []).map(num).join(" / ") || "—"}</b></div>
          <div class="lv res"><small>Resistance</small><b>${(an.resistance || []).map(num).join(" / ") || "—"}</b></div>
          ${pr ? `<div class="lv proj"><small>${pr.horizon_days || 7}d bull / base / bear</small><b><span class="up">${num(pr.bull)}</span> / ${num(pr.base)} / <span class="down">${num(pr.bear)}</span></b></div>` : ""}
          <div class="lv"><small>24h range</small><b>${num(a.low_24h)} – ${num(a.high_24h)}</b></div>
        </div>
        <p class="commentary">${esc(an.commentary || "No commentary yet.")}</p>
        <div class="sources">${sourcesHTML(an.sources)}</div>`;
      grid.appendChild(el);
      // mark entries of trades on this coin
      const markers = (trades.trades || []).filter((t) => t.coin === id && t.status !== "pending" && t.status !== "cancelled").map((t) => ({
        id: `entry-${t.id}`, type: "point", xValue: Date.parse(t.filled_at || t.opened_at), yValue: t.entry, radius: 4,
        backgroundColor: t.status === "won" ? COLORS.sup : t.status === "open" ? COLORS.line : COLORS.res, borderColor: "#fff", borderWidth: 1,
      }));
      const cv = el.querySelector("canvas");
      lazyChart(el.querySelector(".coin-chart"), () => { Dash.charts[id] = priceChart(cv, a, an, { markers }); });
    }
    }
  }

  /* ---------- trades: slate + table ---------- */
  const dirSign = (t) => (t.direction === "short" ? -1 : 1);
  const lev = (t) => t.leverage || 3;
  const movePct = (t, p, from = t.entry) => (dirSign(t) * (p - from) / from) * 100;
  function livePnl(t, price) {
    // blended across targets, same rule as the update script (targets already hit are locked in)
    const n = t.targets.length, hits = (t.targets_hit || []).map((h) => h.price);
    const legs = hits.concat(Array(Math.max(0, n - hits.length)).fill(price));
    return legs.reduce((a, p) => a + movePct(t, p) * lev(t), 0) / n;
  }
  function zoneOf(t) { const z = t.entry_zone || {}; return { lo: z.low ?? t.entry, hi: z.high ?? t.entry }; }
  function zoneDistance(t, price) {
    const { lo, hi } = zoneOf(t);
    if (price >= lo && price <= hi) return { txt: "in zone — fill area", cls: "in" };
    const above = price > hi;
    const d = above ? (price / hi - 1) * 100 : (1 - price / lo) * 100;
    const base = `${d.toFixed(1)}% ${above ? "above" : "below"} zone`;
    const mi = t.missed_it && t.missed_it.max_entry;
    // The "chase" side is the side the trade profits on: above the zone for longs, below it for shorts.
    const chaseSide = t.direction === "short" ? !above : above;
    if (!chaseSide) return { txt: `${base} — moving toward the stop side`, cls: "away" };
    if (mi == null) return { txt: `${base} — waiting for a pullback into the zone`, cls: "away" };
    const within = t.direction === "short" ? price >= mi : price <= mi;
    return within
      ? { txt: `${base} — still within the missed-it limit (${num(mi)})`, cls: "ok" }
      : { txt: `${base} — past the missed-it limit (${num(mi)}): wait for the zone, don't chase`, cls: "missed" };
  }
  /* ---------- missed-it plan (trade.missed_plan) ---------- */
  const MP_STATE = { watching: "watching", armed: "armed: watching the trigger", triggered: "triggered", void: "void: main idea filled",
    invalidated: "invalidated", expired: "expired", "n/a": "no chase" };
  const mpUser = new Set(); // cards whose block the reader toggled by hand: never auto-open/close those
  const pastLimit = (t, price) => {
    const mi = t.missed_it && t.missed_it.max_entry;
    if (mi == null || price == null) return false;
    return t.direction === "short" ? price < mi : price > mi;
  };
  const mpDir = (t, p) => p.direction || (p.type === "flip" ? (t.direction === "long" ? "short" : "long") : t.direction);
  function mpRR(t, p) {
    const z = p.entry_zone; if (!z || p.stop == null || p.target == null) return null;
    const long = mpDir(t, p) === "long", worst = long ? z.high : z.low, best = long ? z.low : z.high;
    const f = (e) => Math.abs(p.target - e) / Math.abs(e - p.stop);
    return [f(worst), f(best)];
  }
  function mpDistance(t, p, price) {
    if (!p || p.type === "none" || price == null) return "";
    const st = p.status || "watching";
    if (!["watching", "armed"].includes(st)) return "";
    const r = p.trigger_rule || {}, kind = r.kind || (p.type === "pullback" ? "retest_hold" : "");
    const z = p.entry_zone || {};
    const pc = (a, b) => `${Math.abs((a / b - 1) * 100).toFixed(1)}%`;
    if (kind === "close_above" || kind === "close_below") {
      const lv = r.level, past = kind === "close_above" ? price > lv : price < lv;
      return past ? `Price ${fmtPrice(price)} is past the trigger ${num(lv)}: needs a 1h close ${kind === "close_above" ? "above" : "below"} it`
        : `Price ${fmtPrice(price)} is ${pc(price, lv)} from the trigger ${num(lv)}`;
    }
    const long = mpDir(t, p) === "long";
    if (price >= z.low && price <= z.high) return `Price ${fmtPrice(price)} is in the plan zone: needs a 1h close ${long ? "at or above " + num(z.low) : "at or below " + num(z.high)}`;
    const edge = price > z.high ? z.high : z.low;
    const toward = long ? price > z.high : price < z.low;
    return `Price ${fmtPrice(price)} is ${pc(price, edge)} ${price > z.high ? "above" : "below"} the plan zone` + (toward ? " — waiting for the retest" : ` — on the stop side (plan stop ${num(p.stop)})`);
  }
  function missedBlock(t, price) {
    const p = t.missed_plan, mi = t.missed_it;
    if (!p && !mi) return "";
    if (!p) return `<div class="missed"><span class="mi-ico">↯</span><div><b>Missed it?</b> ${mi.max_entry != null ? `Max entry <span class="mono">${num(mi.max_entry)}</span>. ` : ""}${esc(mi.note || "")}</div></div>`;
    const st = p.status || (p.type === "none" ? "n/a" : "watching");
    const limit = mi && mi.max_entry != null ? `<p class="mp-limit">Missed-it limit <span class="mono">${num(mi.max_entry)}</span>${mi.note ? `: ${esc(mi.note)}` : ""}</p>` : "";
    if (p.type === "none") {
      return `<details class="mplan none" data-mp="${esc(t.id)}"><summary><span class="mi-ico">↯</span><b>Missed it?</b> <span class="mp-head">No good chase</span><span class="mp-state s-na">wait for a new setup</span></summary>
        <div class="mp-body"><p>${esc(p.reasoning || "")}</p>${limit}</div></details>`;
    }
    const rr = mpRR(t, p), L = p.leverage || 3, z = p.entry_zone || {};
    const d = mpDir(t, p);
    return `<details class="mplan" data-mp="${esc(t.id)}"><summary><span class="mi-ico">↯</span><b>Missed it?</b> <span class="mp-head">Here's the move</span>
        <span class="mp-type">${esc(p.type)}</span><span class="mp-state s-${esc(st)}" data-mp-state>${esc(MP_STATE[st] || st)}${st === "triggered" && p.linked_id ? ` → ${esc(p.linked_id)}` : ""}</span></summary>
      <div class="mp-body">
        <p class="mp-trigger"><small>Trigger</small>${esc(p.trigger || "")}</p>
        <div class="mp-grid">
          <div><small>Entry zone</small>${num(z.low)} – ${num(z.high)}</div>
          <div><small>Stop</small>${num(p.stop)}</div>
          <div><small>Target</small>${num(p.target)}</div>
          <div><small>${d === t.direction ? "" : esc(d) + " · "}Leverage</small>${L}x</div>
          <div class="mp-rr"><small>R:R (worst / best fill)</small>${rr ? `${rr[0].toFixed(2)} / ${rr[1].toFixed(2)}` : "—"}</div>
        </div>
        ${p.size_note ? `<p class="mp-size">${esc(p.size_note)}</p>` : ""}
        <p class="mp-dist" data-mp-dist>${esc(mpDistance(t, p, price))}</p>
        ${limit}
        <details class="why"><summary>Why this plan</summary><p>${esc(p.reasoning || "")}</p></details>
      </div></details>`;
  }
  function updateMissed(el, t, price) {
    const box = el.querySelector("[data-mp]"); if (!box) return;
    const p = t.missed_plan || {};
    const hot = t.status === "pending" && (pastLimit(t, price) || p.status === "armed");
    box.classList.toggle("hot", hot);
    box.querySelector("summary").dataset.hot = hot ? (pastLimit(t, price) ? "past the limit" : "plan armed") : "";
    if (!mpUser.has(t.id) && box.open !== hot) { box.dataset.auto = "1"; box.open = hot; }
    const dd = box.querySelector("[data-mp-dist]"); if (dd) dd.textContent = mpDistance(t, p, price);
  }
  document.addEventListener("toggle", (e) => {
    const b = e.target; if (!(b instanceof HTMLElement) || !b.matches || !b.matches("details[data-mp]")) return;
    if (b.dataset.auto === "1") { b.dataset.auto = ""; return; } // programmatic toggle
    mpUser.add(b.dataset.mp);
  }, true);

  function countdown(iso) {
    const ms = Date.parse(iso) - Date.now();
    if (!(ms > 0)) return "expired";
    const h = Math.floor(ms / 36e5), m = Math.floor((ms % 36e5) / 6e4);
    return h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : `${h}h ${m}m`;
  }

  function buildSlate(prices, trades) {
    const all = trades.trades || [];
    const slate = trades.slate && trades.slate.coins ? trades.slate.coins : null;
    return allIds(prices).map((id) => {
      let entry = slate ? slate[id] : null;
      if (!slate) {
        const t = all.find((x) => x.id === trades.current_idea_id && x.coin === id);
        entry = t ? { trade_id: t.id } : null;
      }
      const t = entry && entry.trade_id ? all.find((x) => x.id === entry.trade_id) : null;
      return { id, trade: t, note: entry && entry.note };
    });
  }

  function slateCard(prices, { id, trade: t, note }) {
    const a = prices.assets[id];
    const [c1, c2] = COIN_COLORS[a.symbol] || [];
    const head = (badge) => `<div class="slate-head"><div class="coin-id"><div class="coin-mark sm" style="--c1:${c1 || "#334155"};--c2:${c2 || "#0f172a"}">${esc(a.symbol)}</div>
      <div><b>${esc(a.symbol)}</b><small class="muted"> ${esc(a.name)}</small></div></div>${badge}</div>`;
    const priceRow = `<div class="slate-live"><span class="muted">Live</span> <b class="mono" data-lp="${id}">${fmtPrice(a.price)}</b> <span data-lc="${id}">${chip(a.change_24h)}</span></div>`;
    if (!t) {
      return `<article class="slate-card none">${head('<span class="status s-none">no setup</span>')}${priceRow}
        <p class="slate-note">${esc(note || "No setup right now.")}</p></article>`;
    }
    const L = lev(t);
    const { lo, hi } = zoneOf(t);
    const zoneTxt = lo === hi ? num(lo) : `${num(lo)} – ${num(hi)}`;
    const closed = !["pending", "open"].includes(t.status);
    const side = `<span class="side ${t.direction}">${t.direction === "short" ? "SHORT" : "LONG"} ${L}x</span>`;
    const ref = t.status === "open" ? t.entry : (lo + hi) / 2;
    const tg = t.targets.map((x, i) => `<div><small>T${i + 1}${(t.targets_hit || [])[i] ? " ✓" : ""}</small>${num(x)} <span class="up">+${(movePct(t, x, ref) * L).toFixed(1)}%</span></div>`).join("");
    return `<article class="slate-card ${t.status}" data-slate="${esc(t.id)}" data-coin="${id}">
      ${head(`<span class="status s-${esc(t.status)}">${esc(t.status)}</span>`)}
      <div class="slate-sub">${side}${t.timeframe ? ` <span class="tf-badge" title="${esc(t.timeframe_note || "")}">${esc(String(t.timeframe).charAt(0).toUpperCase() + String(t.timeframe).slice(1))}</span>` : ""} <span class="muted mono">${esc(t.id)}</span>${t.expiry && t.status === "pending" ? ` <span class="muted">· expires in <b class="mono" data-exp="${esc(t.expiry)}">${countdown(t.expiry)}</b></span>` : ""}</div>
      ${priceRow}
      <div class="slate-dist" data-dist>${closed ? `closed ${ct(t.closed_at)}` : "—"}</div>
      <div class="slate-grid">
        <div><small>${t.status === "open" ? "Filled" : "Entry zone"}</small>${t.status === "open" ? num(t.entry) : zoneTxt}</div>
        <div><small>Stop</small>${num(t.current_stop ?? t.stop)} <span class="down">${(movePct(t, t.current_stop ?? t.stop, ref) * L).toFixed(1)}%</span></div>
        ${tg}
        <div class="pnl-cell"><small>${closed ? "Result" : t.status === "open" ? "Unrealized P&L" : "If filled now"}</small><b class="mono" data-upnl>${closed && t.pnl_pct != null ? pct(t.pnl_pct) : "—"}</b></div>
      </div>
      ${t.parent_id ? `<p class="mp-linked">↯ Missed-it plan of <b class="mono">${esc(t.parent_id)}</b>${t.plan_type ? ` (${esc(t.plan_type)})` : ""}${t.trigger ? `: ${esc(t.trigger)}` : ""}${t.size_note ? `. ${esc(t.size_note)}` : ""}</p>` : ""}
      ${closed ? "" : missedBlock(t, a.price)}
      ${t.leverage_note ? `<p class="meta">${esc(t.leverage_note)}</p>` : ""}
      <details class="why"><summary>Reasoning</summary><p>${esc(t.reasoning || "")}</p></details>
    </article>`;
  }

  function updateSlateLive(id, price) {
    document.querySelectorAll(`.slate-card[data-coin="${id}"]`).forEach((el) => {
      const t = (Dash.state.trades.trades || []).find((x) => x.id === el.dataset.slate);
      if (!t) return;
      const dist = el.querySelector("[data-dist]"), up = el.querySelector("[data-upnl]");
      updateMissed(el, t, price);
      if (t.status === "pending") {
        const z = zoneDistance(t, price);
        dist.className = "slate-dist " + z.cls;
        dist.textContent = z.txt;
        // hypothetical P&L is meaningless before a fill: show R:R from the zone midpoint instead
        const { lo, hi } = zoneOf(t), mid = (lo + hi) / 2;
        const rr = Math.abs(t.targets[0] - mid) / Math.abs(mid - t.stop);
        up.innerHTML = `<span class="muted">R:R to T1 ${rr.toFixed(2)}</span>`;
      } else if (t.status === "open") {
        const v = livePnl(t, price);
        dist.className = "slate-dist " + (v >= 0 ? "in" : "away");
        dist.textContent = `${(movePct(t, price) >= 0 ? "+" : "")}${movePct(t, price).toFixed(2)}% from fill`;
        up.innerHTML = pct(v);
      }
    });
    document.querySelectorAll("[data-exp]").forEach((e) => (e.textContent = countdown(e.dataset.exp)));
  }

  function renderTrades(prices, trades) {
    const all = trades.trades || [];
    const sym = (id) => prices.assets[id]?.symbol || id;
    const slate = buildSlate(prices, trades);
    const active = slate.filter((s) => s.trade && ["pending", "open"].includes(s.trade.status)).length;
    const cap = Dash.state.coincfg?.slate_max || 6;
    const shown = slate.filter((s) => s.trade), none = slate.filter((s) => !s.trade);
    $("slate-meta").textContent = `${active} active idea${active === 1 ? "" : "s"} · ${none.length} coins with no setup · max one per coin, ${cap} total` + (trades.slate?.as_of ? ` · slate as of ${ct(trades.slate.as_of)}` : "");
    $("slate-grid").innerHTML = `<div class="slate-grid-cards">${shown.map((s) => slateCard(prices, s)).join("") || '<p class="meta">No active ideas right now.</p>'}</div>` +
      (none.length ? `<div class="slate-none"><h3 class="sub-h">No setup right now <small class="muted">(tap for why)</small></h3><div class="slate-none-list">${none.map((s) => {
        const a = prices.assets[s.id];
        return `<details class="none-item"><summary><b>${esc(a.symbol)}</b> <span class="mono" data-lp="${s.id}">${fmtPrice(a.price)}</span> <span data-lc="${s.id}">${chip(a.change_24h)}</span></summary><p>${esc(s.note || "No setup right now.")}</p></details>`;
      }).join("")}</div></div>` : "");
    shown.forEach((s) => updateSlateLive(s.id, prices.assets[s.id].price));

    const rows = [...all].sort((a, b) => Date.parse(b.opened_at) - Date.parse(a.opened_at));
    $("trades-body").innerHTML = rows.map((t) => {
      const z = t.entry_zone;
      return `<tr title="${esc(t.reasoning)}">
        <td>${esc(t.id)}</td><td>${esc(sym(t.coin))}</td><td>${esc(t.direction)} ${lev(t)}x</td>
        <td>${esc(ct(t.opened_at))}</td><td>${t.status === "pending" && z ? `${num(z.low)}–${num(z.high)}` : num(t.entry)}</td><td>${num(t.stop)}</td>
        <td>${t.targets.map((x, i) => (t.targets_hit || [])[i] ? `<b class="up">${num(x)}✓</b>` : num(x)).join(" / ")}</td>
        <td><span class="status s-${esc(t.status)}">${esc(t.status)}</span>${t.closed_at ? `<br><small class="meta">${esc(ct(t.closed_at))}</small>` : ""}</td>
        <td>${t.exit_price != null ? num(t.exit_price) : t.mark_price != null ? `<small class="meta">mark <span data-lp="${t.coin}">${num(t.mark_price)}</span></small>` : "—"}</td>
        <td data-row-pnl="${esc(t.id)}">${t.pnl_pct != null ? pct(t.pnl_pct) : t.status === "open" && t.unrealized_pnl_pct != null ? pct(t.unrealized_pnl_pct) : "—"}</td>
      </tr>`;
    }).join("") || '<tr><td colspan="10">No trades yet.</td></tr>';
  }

  /* ---------- live wiring ---------- */
  const lastDom = {};
  function onTick(t) {
    const st = Dash.state.prices; if (!st || !st.assets[t.id]) return;
    const prev = Dash.state.live[t.id]?.price ?? st.assets[t.id].price;
    Dash.state.live[t.id] = t;
    const now = performance.now();
    if (lastDom[t.id] && now - lastDom[t.id] < 250) return; // throttle DOM work per coin
    lastDom[t.id] = now;
    const dir = t.price > prev ? "flash-up" : t.price < prev ? "flash-down" : "";
    document.querySelectorAll(`[data-lp="${t.id}"]`).forEach((e) => {
      e.textContent = fmtPrice(t.price);
      if (dir) { e.classList.remove("flash-up", "flash-down"); void e.offsetWidth; e.classList.add(dir); }
    });
    if (t.change24 != null) document.querySelectorAll(`[data-lc="${t.id}"]`).forEach((e) => (e.innerHTML = chip(t.change24, e.dataset.lbl)));
    document.querySelectorAll(`[data-src="${t.id}"]`).forEach((e) => { e.textContent = `${window.Live?.SOURCE_LABEL[t.source] || t.source} ${t.source === "coingecko" ? "· 60s poll" : "· live"}`; e.className = "src-tag " + (t.source === "coingecko" ? "poll" : "ws"); });
    updateSlateLive(t.id, t.price);
    // open-trade rows in the table
    (Dash.state.trades.trades || []).filter((x) => x.coin === t.id && x.status === "open").forEach((x) => {
      const td = document.querySelector(`[data-row-pnl="${x.id}"]`); if (td) td.innerHTML = pct(livePnl(x, t.price)) + ' <small class="meta">live</small>';
    });
    updateChart(t.id, t.price);
    if (t.id === st.backdrop) updateChart("__backdrop", t.price);
    document.dispatchEvent(new CustomEvent("live:tick", { detail: t }));
  }
  const chartTimer = {};
  function updateChart(id, price) {
    const ch = Dash.charts[id]; if (!ch) return;
    if (chartTimer[id]) return;
    chartTimer[id] = setTimeout(() => {
      chartTimer[id] = null;
      const data = ch.data.datasets[0].data, lastPt = data[data.length - 1], now = Date.now();
      const p = Dash.state.live[id === "__backdrop" ? Dash.state.prices.backdrop : id]?.price ?? price;
      if (lastPt.live && now - lastPt.start < 15 * 60000) { lastPt.x = now; lastPt.y = p; }
      else data.push({ x: now, y: p, live: true, start: now });
      if (now > ch.options.scales.x.max) ch.options.scales.x.max = now;
      const ds = ch.data.datasets[0];
      ds.pointRadius = data.map((d, i) => (i === data.length - 1 ? 3 : 0));
      ds.pointBackgroundColor = "#fff";
      ch.update("none");
    }, 1500);
  }
  function liveIndicator(s) {
    const el = $("live-ind"); if (!el) return;
    const m = s.mode;
    el.className = "live-ind " + m;
    el.querySelector("b").textContent = m === "live" ? "LIVE" : m === "delayed" ? "DELAYED" : "SNAPSHOT";
    el.title = `Coinbase websocket: ${s.conn.coinbase} · Kraken websocket: ${s.conn.kraken} · CoinGecko poll: ${s.conn.coingecko}`;
    $("live-sub").textContent = m === "live" ? "streaming" : m === "delayed" ? "polling 60s" : "connecting…";
  }

  function renderLog(log) {
    const entries = [...(log.entries || [])].sort((a, b) => Date.parse(b.t) - Date.parse(a.t));
    $("log-list").innerHTML = entries.map((e) => `
      <li class="${esc(e.kind)}"><time datetime="${esc(e.t)}">${esc(ct(e.t))}<span class="who">${esc(e.kind)} · ${esc(e.author || "")}</span></time>${esc(e.text)}</li>`).join("") || "<li>No updates yet.</li>";
  }

  async function main() {
    try {
      const [prices, analysis, trades, log] = await Promise.all(["prices.json", "analysis.json", "trades.json", "log.json"].map((n) => getJSON(n)));
      const [signals, context] = await Promise.all([getJSON("signals.json", true).catch(() => null), getJSON("context.json", true).catch(() => null)]);
      const coincfg = await getJSON("coins.json", true).catch(() => null);
      Object.assign(Dash.state, { prices, analysis, trades, log, signals, context, coincfg, live: {} });
      if (coincfg && coincfg.coins) for (const c of coincfg.coins) if (c.colors) COIN_COLORS[c.symbol] = c.colors;
      // coins present in prices.json but not yet in coins.json still render; feeds come from coins.json
      const feedList = (coincfg?.coins || []).filter((c) => prices.assets[c.id]);
      if (window.Chart && window["chartjs-plugin-annotation"]) Chart.register(window["chartjs-plugin-annotation"]);
      if (window.Chart) {
        Chart.defaults.font.family = "Inter, system-ui, sans-serif";
        Chart.defaults.color = COLORS.tick;
        Object.assign(Chart.defaults.plugins.tooltip, { backgroundColor: "rgba(11,16,25,.95)", borderColor: "rgba(148,163,184,.25)", borderWidth: 1, padding: 10, cornerRadius: 8, titleFont: { family: "JetBrains Mono, monospace", size: 11 }, bodyFont: { family: "JetBrains Mono, monospace", size: 11 } });
      }
      if (!window.Chart) { const e = $("error"); e.hidden = false; e.textContent = "Chart library failed to load (offline or CDN blocked) — numbers below are still current."; }
      renderTicker(prices);
      renderHeader(prices, analysis);
      renderBackdrop(prices, analysis);
      renderCoins(prices, analysis, trades);
      renderTrades(prices, trades);
      renderLog(log);
      reveal();
      readyResolve(Dash.state);
      if (window.Live) { if (feedList.length) Live.configure(feedList); Live.on(onTick); Live.onStatus(liveIndicator); liveIndicator(Live.status()); Live.start(); }
      if (window.Signals) Signals.start(signals, feedList.length ? feedList : null);
      setInterval(() => window.Live && liveIndicator(Live.status()), 5000);
      document.body.dataset.ready = "1";
    } catch (err) {
      console.error(err);
      document.querySelectorAll(".reveal").forEach((e) => e.classList.add("in"));
      const e = $("error"); e.hidden = false;
      e.textContent = "Could not load dashboard data: " + err.message + (location.protocol === "file:" ? " (open via a web server, not file://)" : "");
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", main); else main();
})();
