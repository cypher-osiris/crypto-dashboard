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
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".28"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs>
      <path d="${d}L${w} ${h}L0 ${h}Z" fill="url(#${gid})"/><path d="${d}" fill="none" stroke="${c}" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }
  const COIN_COLORS = { HBAR: ["#3a3a3a", "#0b0b0b"], XLM: ["#5b6cff", "#1b1f4a"], XRP: ["#2d3748", "#0a0f17"], ZBCN: ["#06b6d4", "#0e3a52"], AXL: ["#6366f1", "#111827"], BTC: ["#f7931a", "#7a3e00"] };
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

  async function getJSON(name) {
    const r = await fetch(`data/${name}?v=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
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
    const ids = [prices.backdrop, ...prices.coins];
    const item = (id, dup) => {
      const a = prices.assets[id];
      return `<a class="tk${dup ? " dup" : ""}" href="#${id === prices.backdrop ? "market" : "coin-" + id}"${dup ? ' aria-hidden="true" tabindex="-1"' : ""}>
        <span class="s">${esc(a.symbol)}</span><span class="p">${fmtPrice(a.price)}</span>${chip(a.change_24h)}${spark(a.history, 56, 18, 72)}</a>`;
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
    $("btc-chg").innerHTML = chip(b.change_24h, "24h") + chip(b.change_7d, "7d") + chip(b.change_30d, "30d");
    if (an.bias) $("btc-chg").insertAdjacentHTML("afterend", `<div class="bias">${esc(an.bias)}</div>`);
    $("btc-commentary").textContent = an.commentary || "";
    $("btc-sources").innerHTML = sourcesHTML(an.sources);
    priceChart($("chart-bitcoin"), b, an);
  }

  function renderCoins(prices, analysis, trades) {
    const grid = $("coin-grid");
    grid.innerHTML = "";
    for (const id of prices.coins) {
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
            <div><div class="name">${esc(a.symbol)}<small>${esc(a.name)}${a.market_cap_rank ? " · rank #" + a.market_cap_rank : ""}</small></div>
              ${an.bias ? `<div class="bias">${esc(an.bias)}</div>` : ""}</div>
          </div>
          <div class="coin-right">
            ${spark(a.history)}
            <div><div class="price">${fmtPrice(a.price)}</div>
              <div class="chg">${chip(a.change_24h, "24h")}${chip(a.change_7d, "7d")}</div></div>
          </div>
        </div>
        <div class="coin-chart"><canvas id="chart-${id}" aria-label="${esc(a.symbol)} 30 day chart"></canvas></div>
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
      priceChart(el.querySelector("canvas"), a, an, { markers });
    }
  }

  function tradePnl(t) {
    if (t.pnl_pct != null) return pct(t.pnl_pct);
    if (t.unrealized_pnl_pct != null) return pct(t.unrealized_pnl_pct) + ' <small class="meta">(open)</small>';
    return "—";
  }

  function renderTrades(prices, trades) {
    const all = trades.trades || [];
    const sym = (id) => prices.assets[id]?.symbol || id;
    const idea = all.find((t) => t.id === trades.current_idea_id);
    const ideaEl = $("idea");
    if (idea) {
      const lev = idea.leverage || 5;
      const move = (p) => ((idea.direction === "short" ? -1 : 1) * (p - idea.entry) / idea.entry) * 100;
      const mark = prices.assets[idea.coin]?.price;
      ideaEl.innerHTML = `
        <h3>Today's trade idea · ${esc(idea.id)} — ${esc(sym(idea.coin))} ${esc(idea.direction.toUpperCase())} ${lev}x
          <span class="status s-${esc(idea.status)}">${esc(idea.status)}</span></h3>
        <div class="grid">
          <div><small>Entry</small>${num(idea.entry)}</div>
          <div><small>Stop</small>${num(idea.stop)} <span class="down">(${(move(idea.stop) * lev).toFixed(1)}%)</span></div>
          ${idea.targets.map((x, i) => `<div><small>Target ${i + 1}</small>${num(x)} <span class="up">(+${(move(x) * lev).toFixed(1)}%)</span></div>`).join("")}
          <div><small>Now</small>${num(mark)}</div>
          <div><small>Posted</small>${esc(ct(idea.opened_at))}</div>
          ${idea.fill_by ? `<div><small>Fill by</small>${esc(ct(idea.fill_by))}</div>` : ""}
        </div>
        <p>${esc(idea.reasoning)}</p>`;
    } else {
      ideaEl.innerHTML = "<h3>Today's trade idea</h3><p>No idea posted for today — sitting on hands is a position too.</p>";
    }

    const s = trades.stats || {};
    $("stats").innerHTML = [
      ["Win rate", s.win_rate_pct == null ? "n/a" : `<span class="${s.win_rate_pct >= 50 ? "up" : "down"}">${s.win_rate_pct}%</span>`],
      ["Cumulative P&L", s.cumulative_pnl_pct == null ? "n/a" : pct(s.cumulative_pnl_pct)],
      ["Closed", `${s.closed ?? 0} <small class="meta">(${s.won ?? 0}W / ${s.lost_or_stopped ?? 0}L)</small>`],
      ["Open / pending", `${s.open ?? 0} / ${s.pending ?? 0}`],
    ].map(([k, v]) => `<div class="stat"><small>${k}</small><b>${v}</b></div>`).join("");

    const rows = [...all].sort((a, b) => Date.parse(b.opened_at) - Date.parse(a.opened_at));
    $("trades-body").innerHTML = rows.map((t) => `
      <tr title="${esc(t.reasoning)}">
        <td>${esc(t.id)}</td><td>${esc(sym(t.coin))}</td><td>${esc(t.direction)} ${t.leverage || 5}x</td>
        <td>${esc(ct(t.opened_at))}</td><td>${num(t.entry)}</td><td>${num(t.stop)}</td>
        <td>${t.targets.map((x, i) => (t.targets_hit || [])[i] ? `<b class="up">${num(x)}✓</b>` : num(x)).join(" / ")}</td>
        <td><span class="status s-${esc(t.status)}">${esc(t.status)}</span>${t.closed_at ? `<br><small class="meta">${esc(ct(t.closed_at))}</small>` : ""}</td>
        <td>${t.exit_price != null ? num(t.exit_price) : t.mark_price != null ? `<small class="meta">mark ${num(t.mark_price)}</small>` : "—"}</td>
        <td>${tradePnl(t)}</td>
      </tr>`).join("") || '<tr><td colspan="10">No trades yet.</td></tr>';

    if (window.Chart) {
      const curve = (s.equity_curve || []).map((p) => ({ x: Date.parse(p.t), y: p.cum_pnl_pct, id: p.trade_id }));
      const first = all.length ? Math.min(...all.map((t) => Date.parse(t.opened_at))) : Date.now();
      const pts = [{ x: first, y: 0, id: "start" }, ...curve];
      const lastPt = pts[pts.length - 1];
      if (Date.now() > lastPt.x) pts.push({ x: Date.now(), y: lastPt.y, id: "now" });
      new Chart($("chart-pnl"), {
        type: "line",
        data: { datasets: [{ label: "Cumulative P&L % (5x)", data: pts, stepped: true, borderColor: COLORS.base, borderWidth: 2, pointRadius: 3, fill: { target: { value: 0 }, above: "rgba(63,185,80,0.15)", below: "rgba(248,81,73,0.15)" } }] },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false, parsing: false,
          scales: {
            x: { type: "linear", min: pts[0].x, max: Math.max(Date.now(), pts[pts.length - 1].x), afterBuildTicks: dayTicks, grid: { color: COLORS.grid }, ticks: { color: COLORS.tick, callback: (v) => shortDate(v) } },
            y: { grid: { color: COLORS.grid }, ticks: { color: COLORS.tick, callback: (v) => v + "%" } },
          },
          plugins: { legend: { labels: { color: COLORS.tick } }, tooltip: { callbacks: { title: (it) => ct(it[0].parsed.x), label: (it) => `${it.raw.id}: ${it.parsed.y.toFixed(2)}%` } } },
        },
      });
    }
  }

  function renderLog(log) {
    const entries = [...(log.entries || [])].sort((a, b) => Date.parse(b.t) - Date.parse(a.t));
    $("log-list").innerHTML = entries.map((e) => `
      <li class="${esc(e.kind)}"><time datetime="${esc(e.t)}">${esc(ct(e.t))}<span class="who">${esc(e.kind)} · ${esc(e.author || "")}</span></time>${esc(e.text)}</li>`).join("") || "<li>No updates yet.</li>";
  }

  async function main() {
    try {
      const [prices, analysis, trades, log] = await Promise.all(["prices.json", "analysis.json", "trades.json", "log.json"].map(getJSON));
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
