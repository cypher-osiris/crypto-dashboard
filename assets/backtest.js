/* Signal Backtest section — renders data/backtest.json (written by scripts/backtest.py). */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let BT = null, cur = null, charts = [];
  const f = (x, d = 1) => (x == null || isNaN(x) ? "—" : Number(x).toFixed(d));
  const sgn = (x, d = 1, suf = "%") => (x == null ? "—" : `<span class="${x > 0 ? "up" : x < 0 ? "down" : ""}">${x > 0 ? "+" : ""}${f(x, d)}${suf}</span>`);

  function summary() {
    const D = window.Dash, mt = BT.multiple_testing, w = BT.weights;
    const eq = w.candidates_oos.find((c) => c.weights === "equal");
    const score = w.components.find((c) => c.component === "score");
    let beat = 0, pairs = 0, ruin = 0, smallN = 0;
    for (const c of Object.values(BT.coins)) {
      for (const s of c.strategies) {
        const hold = s.name.startsWith("Daily") ? c.hold.daily_period.total_return_pct : c.hold["4h_period"].total_return_pct;
        if (s.trades < 20) { smallN++; continue; }
        pairs++; if (s.total_return_pct > hold) beat++; if (s.ruined) ruin++;
      }
    }
    $("bt-summary").innerHTML = `
      <p class="bt-verdict"><b>Bottom line: no reliable edge.</b> Nothing in this system passes a basic robustness check across coins and time.</p>
      <ul>
        <li><b>Individual signals:</b> of ${mt.tests_with_n_ge_30} indicator tests with ≥30 events, ${mt.t_ge_2} cleared t ≥ 2 and ${mt.t_le_minus_2} came in at t ≤ −2 — luck alone would produce about ${mt.expected_by_chance_each_side} on each side. The "winners" are different signals on different coins.</li>
        <li><b>Composite score:</b> its correlation with the next-24h return is slightly <i>negative</i> both in-sample (${f(score.is_mean_ic, 3)}, positive in ${score.is_positive} series) and out-of-sample (${f(score.oos_mean_ic, 3)}, ${score.oos_positive}). Trend components (EMA stack, volume) were mildly contrarian in a year when most of these coins fell.</li>
        <li><b>Strategies (3x, ATR stops, fees):</b> beat buy-and-hold in ${beat} of ${pairs} coin/strategy pairs with ≥20 trades, but the same rule wins big on one coin and wipes out on another (${ruin} hit ruin). Beating a falling buy-and-hold is a low bar; most curves are dominated by a handful of trades.</li>
        <li><b>Reweighting:</b> no candidate weighting holds up out-of-sample (best: ${D.esc(w.candidates_oos.slice().sort((a, b) => (b.oos_mean_ic ?? -9) - (a.oos_mean_ic ?? -9))[0].weights)}, OOS IC ${f(w.candidates_oos.slice().sort((a, b) => (b.oos_mean_ic ?? -9) - (a.oos_mean_ic ?? -9))[0].oos_mean_ic, 3)}). Weights are <b>proposed only, not applied</b>; the dashboard keeps equal weights.</li>
        <li><b>Caveats:</b> ~1 year of 1h/4h (ZBCN: 30 days 1h, 120 days 4h — tiny), ~2 years daily, one mostly-bearish regime, no slippage/funding, overlapping windows inflate t-stats, ${smallN} strategy runs had &lt;20 trades. Treat every number here as noise until proven otherwise.</li>
      </ul>`;
  }

  function weights() {
    const w = BT.weights;
    $("bt-weights").innerHTML = `
      <div class="table-wrap"><table><thead><tr><th>Component</th><th>In-sample IC</th><th>IS +</th><th>Out-of-sample IC</th><th>OOS +</th><th>Proposed weight</th></tr></thead><tbody>
      ${w.components.filter((c) => c.component !== "score").map((c) => `<tr><td>${c.component}</td><td>${sgn(c.is_mean_ic, 3, "")}</td><td>${c.is_positive}</td><td>${sgn(c.oos_mean_ic, 3, "")}</td><td>${c.oos_positive}</td><td>${f(w.proposed_weights[c.component], 2)}</td></tr>`).join("")}
      </tbody></table></div>
      <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Weighting</th><th>In-sample IC</th><th>IS +</th><th>Out-of-sample IC</th><th>OOS +</th></tr></thead><tbody>
      ${w.candidates_oos.map((c) => `<tr><td>${c.weights}${c.weights === "equal" ? " (live)" : ""}</td><td>${sgn(c.is_mean_ic, 3, "")}</td><td>${c.is_positive}</td><td>${sgn(c.oos_mean_ic, 3, "")}</td><td>${c.oos_positive}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="meta">IC = correlation between the component's points and the next-24h return, averaged over coins × timeframes (first 70% of history = in-sample, last 30% = out-of-sample). Decision rule: ${window.Dash.esc(w.solid_rule)} → <b>${w.evidence_solid ? "met" : "not met"}</b>, so no weighted score was added.</p>`;
  }

  function renderCoin(id) {
    const D = window.Dash, c = BT.coins[id]; cur = id;
    document.querySelectorAll("#bt-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
    const cov = Object.entries(c.coverage).map(([tf, v]) => `${tf}: ${v.bars} bars (${v.from.slice(0, 10)} → ${v.to.slice(0, 10)})`).join(" · ");
    const h4 = c.hold["4h_period"], hd = c.hold.daily_period;
    $("bt-coin").innerHTML = `
      <p class="meta">${D.esc(c.source)} · ${cov}</p>
      <div class="table-wrap"><table class="bt-strat"><thead><tr><th>Strategy (3x)</th><th>Trades</th><th>Win</th><th>Return</th><th>Max DD</th><th>PF</th><th>Exits T/S/time</th><th>Buy &amp; hold</th></tr></thead><tbody>
      ${c.strategies.map((s) => { const hold = s.name.startsWith("Daily") ? hd : h4; return `<tr><td>${D.esc(s.name)}${s.trades < 20 ? ' <span class="small-n">n&lt;20</span>' : ""}${s.ruined ? ' <span class="ruin">ruin</span>' : ""}</td><td>${s.trades}</td><td>${s.win_rate == null ? "—" : f(s.win_rate * 100, 0) + "%"}</td><td>${sgn(s.total_return_pct)}</td><td>${sgn(s.max_drawdown_pct)}</td><td>${f(s.profit_factor, 2)}</td><td>${s.exits.target}/${s.exits.stop}/${s.exits.time}${s.exits.liquidated ? `/${s.exits.liquidated} liq` : ""}</td><td>${sgn(hold.total_return_pct)}</td></tr>`; }).join("")}
      </tbody></table></div>
      <div class="bt-charts"><div class="bt-chart"><canvas id="bt-ch1" role="img" aria-label="${D.esc(c.symbol)} equity curves: composite strategies versus buy and hold"></canvas></div><div class="bt-chart"><canvas id="bt-ch2" role="img" aria-label="${D.esc(c.symbol)} daily-score strategy versus buy and hold"></canvas></div></div>
      <h3 class="sub-h">Indicators ranked by 24h edge <small class="muted">(edge = avg directional return minus the unconditional drift; t ignores overlap)</small></h3>
      <div class="table-wrap bt-rank"><table><thead><tr><th>TF</th><th>Signal</th><th>n</th><th>Hit</th><th>Base hit</th><th>Edge 24h</th><th>t</th></tr></thead><tbody>
      ${c.ranked.map((r) => `<tr class="${r.small_sample ? "dim" : ""}"><td>${D.esc(r.tf)}</td><td>${D.esc(r.signal)}${r.small_sample ? ' <span class="small-n">small n</span>' : ""}</td><td>${r.n}</td><td>${f(r.hit * 100, 0)}%</td><td>${f(r.base_hit * 100, 0)}%</td><td>${sgn(r.edge_pct, 2)}</td><td class="${Math.abs(r.t) >= 2 ? (r.t > 0 ? "up" : "down") : ""}">${f(r.t, 2)}</td></tr>`).join("")}
      </tbody></table></div>`;
    charts.forEach((ch) => ch.destroy()); charts = [];
    if (!window.Chart) return;
    const pal = ["#22d3ee", "#a78bfa", "#f5b041", "#94a3b8"];
    const line = (label, pts, color, dash) => ({ label, data: pts.map(([t, v]) => ({ x: t * 1000, y: (v - 1) * 100 })), borderColor: color, borderWidth: dash ? 1.5 : 2, borderDash: dash ? [5, 4] : [], pointRadius: 0, stepped: !dash, fill: false });
    const opts = (title, ds) => { const xs = ds.flatMap((d) => d.data.map((q) => q.x)); return ({ responsive: true, maintainAspectRatio: false, animation: false, parsing: false,
      scales: { x: { type: "linear", min: Math.min(...xs), max: Math.max(...xs), grid: { color: D.COLORS.grid }, ticks: { maxTicksLimit: 6, callback: (v) => new Date(v).toLocaleDateString("en-US", { month: "short", year: "2-digit" }) } },
        y: { grid: { color: D.COLORS.grid }, ticks: { callback: (v) => v + "%" } } },
      plugins: { title: { display: true, text: title, color: D.COLORS.tick, font: { size: 12, weight: "600" } }, legend: { position: "bottom", labels: { color: D.COLORS.tick, boxWidth: 12, boxHeight: 2, font: { size: 10 } } },
        tooltip: { callbacks: { title: (it) => D.ct(it[0].parsed.x, false), label: (it) => `${it.dataset.label}: ${it.parsed.y.toFixed(1)}%` } } } }); };
    const s4 = c.strategies.filter((s) => !s.name.startsWith("Daily"));
    const ds1 = [...s4.map((s, i) => line(s.name.replace(" (4h)", ""), s.curve, pal[i])), line("Buy & hold (1x)", h4.curve, pal[3], true)];
    charts.push(new Chart($("bt-ch1"), { type: "line", data: { datasets: ds1 }, options: opts("Composite strategies vs holding — 1h/4h period", ds1) }));
    const sd = c.strategies.find((s) => s.name.startsWith("Daily"));
    const ds2 = [line("Daily score Buy/Sell", sd.curve, pal[0]), line("Buy & hold (1x)", hd.curve, pal[3], true)];
    charts.push(new Chart($("bt-ch2"), { type: "line", data: { datasets: ds2 }, options: opts("Daily-score strategy vs holding — long history", ds2) }));
  }

  async function start() {
    const el = $("backtest"); if (!el) return;
    try {
      const r = await fetch(`${document.documentElement.dataset.root || ""}data/backtest.json?v=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      BT = await r.json();
    } catch (e) { $("bt-summary").innerHTML = `<p class="meta">No backtest data yet (run scripts/backtest.py).</p>`; return; }
    const D = window.Dash, a = BT.assumptions;
    $("bt-meta").textContent = `Run ${D.ct(BT.generated_utc)}`;
    $("bt-assume").innerHTML = `Assumptions: ${a.leverage}x, fees ${a.fee_per_side_pct}% per side, stop ${a.stop_atr}×ATR(14), target ${a.target_atr}×ATR, time stop ${D.esc(a.time_stop)}; ${D.esc(a.sizing)}; ${D.esc(a.entry)}; ${D.esc(a.path)}. Indicator math is verified bar-by-bar against signals.py (no lookahead).`;
    summary(); weights();
    const ids = Object.keys(BT.coins);
    $("bt-tabs").innerHTML = ids.map((id) => `<button type="button" data-id="${id}">${D.esc(BT.coins[id].symbol)}</button>`).join("");
    $("bt-tabs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) renderCoin(b.dataset.id); });
    renderCoin(ids.includes("ripple") ? "ripple" : ids[0]);
  }
  // data/backtest.json is ~0.5 MB: fetch it only when the section is about to scroll into view
  const lazy = () => {
    const el = document.getElementById("backtest"); if (!el) return;
    if (!("IntersectionObserver" in window) || location.hash === "#backtest") { start(); return; }
    const io = new IntersectionObserver((ents) => { if (ents.some((e) => e.isIntersecting)) { io.disconnect(); start(); } }, { rootMargin: "800px 0px" });
    io.observe(el);
  };
  const boot = () => (window.Dash && window.Dash.ready ? window.Dash.ready.then(lazy) : setTimeout(boot, 50));
  boot();
})();
