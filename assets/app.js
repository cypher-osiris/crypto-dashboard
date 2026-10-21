/* Crypto dashboard — renders everything from data/*.json. No build step. */
(() => {
  "use strict";
  const TZ = "America/Chicago";
  const DAY = 864e5;
  const COLORS = { line: "#58a6ff", sup: "#3fb950", res: "#f85149", bull: "#3fb950", base: "#d29922", bear: "#f85149", grid: "#222b38", tick: "#8b98a9" };

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
      tension: 0.15, fill: { target: "origin", above: "rgba(88,166,255,0.06)" }, order: 1,
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
  function renderHeader(prices, analysis) {
    $("updated").textContent = ct(prices.updated_utc);
    $("analysis-meta").innerHTML = `Commentary as of ${esc(ct(analysis.as_of))} · ${esc(analysis.author || "")}` +
      (analysis.label ? `<br>${esc(analysis.label)}` : "");
  }

  function renderBackdrop(prices, analysis) {
    const b = prices.assets[prices.backdrop];
    const an = analysis.backdrop || {};
    $("btc-price").textContent = fmtPrice(b.price);
    $("btc-chg").innerHTML = `<span>24h ${pct(b.change_24h)}</span><span>7d ${pct(b.change_7d)}</span><span>30d ${pct(b.change_30d)}</span>` +
      (an.bias ? `<div class="bias">${esc(an.bias)}</div>` : "");
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
      el.className = "coin";
      el.id = `coin-${id}`;
      el.innerHTML = `
        <div class="coin-head">
          <div><div class="name">${esc(a.symbol)}<small>${esc(a.name)}${a.market_cap_rank ? " · #" + a.market_cap_rank : ""}</small></div>
            ${an.bias ? `<div class="bias">${esc(an.bias)}</div>` : ""}</div>
          <div><div class="price">${fmtPrice(a.price)}</div>
            <div class="chg">24h ${pct(a.change_24h)} &nbsp; 7d ${pct(a.change_7d)}</div></div>
        </div>
        <div class="coin-chart"><canvas id="chart-${id}" aria-label="${esc(a.symbol)} 30 day chart"></canvas></div>
        <div class="levels">
          <span><i class="legend-dot" style="background:${COLORS.sup}"></i>Support <b>${(an.support || []).map(num).join(" / ") || "—"}</b></span>
          <span><i class="legend-dot" style="background:${COLORS.res}"></i>Resistance <b>${(an.resistance || []).map(num).join(" / ") || "—"}</b></span>
          ${pr ? `<span>${pr.horizon_days || 7}d targets: bull <b class="up">${num(pr.bull)}</b> · base <b>${num(pr.base)}</b> · bear <b class="down">${num(pr.bear)}</b></span>` : ""}
          <span>24h range <b>${num(a.low_24h)}–${num(a.high_24h)}</b></span>
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
      ["Win rate", s.win_rate_pct == null ? "n/a" : `${s.win_rate_pct}%`],
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
      if (!window.Chart) { const e = $("error"); e.hidden = false; e.textContent = "Chart library failed to load (offline or CDN blocked) — numbers below are still current."; }
      renderHeader(prices, analysis);
      renderBackdrop(prices, analysis);
      renderCoins(prices, analysis, trades);
      renderTrades(prices, trades);
      renderLog(log);
      document.body.dataset.ready = "1";
    } catch (err) {
      console.error(err);
      const e = $("error"); e.hidden = false;
      e.textContent = "Could not load dashboard data: " + err.message + (location.protocol === "file:" ? " (open via a web server, not file://)" : "");
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", main); else main();
})();
