/* Market context strip, Track record, Position calculator. Depends on window.Dash (app.js). */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const MARGIN = 100; // $ margin assumed per paper trade for the track record

  /* ---------------- market context ---------------- */
  const big = (v) => (v == null ? "—" : v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(2)}B` : `$${(v / 1e6).toFixed(1)}M`);
  const ctx = { global: null, fear_greed: null, derivatives: null, src: {} };
  function fngClass(v) { return v >= 75 ? "xg" : v >= 55 ? "g" : v > 45 ? "n" : v > 25 ? "f" : "xf"; }
  function renderContext() {
    const D = window.Dash, el = $("context"); if (!el) return;
    const g = ctx.global, f = ctx.fear_greed, d = ctx.derivatives;
    const item = (k, v, sub, title) => `<div class="ctx" title="${D.esc(title || "")}"><small>${k}</small><b class="mono">${v}</b>${sub ? `<span class="ctx-sub">${sub}</span>` : ""}</div>`;
    el.innerHTML = [
      g ? item("Total market cap", big(g.total_mcap_usd), g.mcap_change_24h_pct != null ? D.chip(g.mcap_change_24h_pct) : "", `CoinGecko /global · ${ctx.src.global}`) : "",
      g ? item("BTC dominance", `${g.btc_dominance_pct.toFixed(1)}%`, g.eth_dominance_pct != null ? `<span class="muted">ETH ${g.eth_dominance_pct.toFixed(1)}%</span>` : "", `CoinGecko /global · ${ctx.src.global}`) : "",
      g ? item("24h volume", big(g.total_volume_usd), "", `CoinGecko /global · ${ctx.src.global}`) : "",
      f ? item("Fear & Greed", `${f.value}`, `<span class="fng ${fngClass(f.value)}">${D.esc(f.classification)}</span>${f.previous != null ? `<span class="muted"> prev ${f.previous}</span>` : ""}`, `alternative.me Crypto Fear & Greed Index (daily) · ${ctx.src.fear_greed}`) : "",
      d ? item("BTC funding (8h)", `${d.funding_rate_pct >= 0 ? "+" : ""}${d.funding_rate_pct.toFixed(4)}%`, `<span class="muted">OKX perp</span>`, `OKX BTC-USDT-SWAP current funding rate · positive = longs pay shorts · ${ctx.src.derivatives}`) : "",
      d ? item("BTC open interest", big(d.open_interest_usd), `<span class="muted">${Math.round(d.open_interest_btc).toLocaleString()} BTC</span>`, `OKX BTC-USDT-SWAP open interest · ${ctx.src.derivatives}`) : "",
    ].join("") || '<div class="ctx"><small>Market context</small><b>unavailable</b></div>';
  }
  const getJ = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(r.status); return r.json(); };
  async function refreshContext() {
    const jobs = [
      getJ("https://api.coingecko.com/api/v3/global").then((j) => { const d = j.data; ctx.global = { total_mcap_usd: d.total_market_cap.usd, total_volume_usd: d.total_volume.usd, mcap_change_24h_pct: d.market_cap_change_percentage_24h_usd, btc_dominance_pct: d.market_cap_percentage.btc, eth_dominance_pct: d.market_cap_percentage.eth }; ctx.src.global = "live"; }),
      getJ("https://api.alternative.me/fng/?limit=2").then((j) => { const d = j.data; ctx.fear_greed = { value: +d[0].value, classification: d[0].value_classification, previous: d[1] ? +d[1].value : null }; ctx.src.fear_greed = "live"; }),
      Promise.all([getJ("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP"), getJ("https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP")]).then(([f, o]) => {
        ctx.derivatives = { funding_rate_pct: +f.data[0].fundingRate * 100, open_interest_usd: +o.data[0].oiUsd, open_interest_btc: +o.data[0].oiCcy }; ctx.src.derivatives = "live";
      }),
    ];
    await Promise.allSettled(jobs);
    renderContext();
  }
  function startContext(snap) {
    if (snap) for (const k of ["global", "fear_greed", "derivatives"]) if (snap[k] && !snap[k].error) { ctx[k] = snap[k]; ctx.src[k] = `snapshot ${window.Dash.ct(snap.generated_utc)}`; }
    renderContext();
    refreshContext();
    setInterval(refreshContext, 5 * 60000);
  }

  /* ---------------- track record ---------------- */
  function renderTrack(st) {
    const D = window.Dash;
    const all = st.trades.trades || [];
    const closed = all.filter((t) => ["won", "lost", "stopped"].includes(t.status) && t.pnl_pct != null).sort((a, b) => Date.parse(a.closed_at) - Date.parse(b.closed_at));
    const wins = closed.filter((t) => t.pnl_pct > 0), losses = closed.filter((t) => t.pnl_pct <= 0);
    const usd = (t) => (t.pnl_pct / 100) * MARGIN;
    const sum = (a) => a.reduce((x, y) => x + y, 0);
    const avg = (a) => (a.length ? sum(a) / a.length : null);
    const total = sum(closed.map(usd));
    const gp = sum(wins.map(usd)), gl = -sum(losses.map(usd));
    const money = (v) => (v == null ? "—" : `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v < 0 ? "−" : v > 0 ? "+" : ""}$${Math.abs(v).toFixed(2)}</span>`);
    const tiles = [
      ["Closed trades", `${closed.length}`, `${wins.length}W / ${losses.length}L`],
      ["Win rate", closed.length ? `${((wins.length / closed.length) * 100).toFixed(0)}%` : "n/a", ""],
      ["Avg win", wins.length ? D.pct(avg(wins.map((t) => t.pnl_pct))) : "—", "on margin"],
      ["Avg loss", losses.length ? D.pct(avg(losses.map((t) => t.pnl_pct))) : "—", "on margin"],
      ["Total return", money(total), closed.length ? `${((total / (MARGIN * closed.length)) * 100).toFixed(1)}% of $${MARGIN * closed.length} deployed` : ""],
      ["Profit factor", gl > 0 ? (gp / gl).toFixed(2) : gp > 0 ? "∞" : "—", "gross win ÷ gross loss"],
    ];
    $("track-stats").innerHTML = tiles.map(([k, v, s]) => `<div class="stat"><small>${k}</small><b>${v}</b>${s ? `<span class="stat-sub">${s}</span>` : ""}</div>`).join("");
    $("track-body").innerHTML = closed.slice().reverse().map((t) => `<tr>
      <td>${D.esc(t.id)}</td><td>${D.esc(st.prices.assets[t.coin]?.symbol || t.coin)}</td><td>${D.esc(t.direction)} ${D.levTxt(t.leverage)}</td>
      <td>${D.num(t.entry)}</td><td>${D.num(t.exit_price)}</td><td><span class="status s-${D.esc(t.status)}">${D.esc(t.status)}</span></td>
      <td>${D.pct(t.pnl_pct)}</td><td>${money(usd(t))}</td><td>${D.esc(D.ct(t.opened_at, false))} → ${D.esc(D.ct(t.closed_at, false))}</td></tr>`).join("") || '<tr><td colspan="9">No closed trades yet.</td></tr>';
    const openN = all.filter((t) => t.status === "open").length, pendN = all.filter((t) => t.status === "pending").length;
    $("track-note").innerHTML = `Every closed paper trade is included — losers too; nothing is removed after the fact. Results assume <b>$${MARGIN} margin per trade</b> at the trade's own leverage, equal size across targets, no fees or funding, evaluated on ~hourly CoinGecko prices (brief wicks can be missed). ` +
      `Leverage is each trade's own: T001 was 5x, Oct 21 ideas a fixed 3x, and from Oct 22, 2026 Lumi sets it per idea (1x–10x by conviction, loss at the stop capped near 25% of margin). ${openN} open and ${pendN} pending idea(s) are not counted until they close. ` +
      (closed.length < 20 ? `With only ${closed.length} closed trade${closed.length === 1 ? "" : "s"}, these numbers say almost nothing about skill yet.` : "");
    if (window.Chart) {
      let cum = 0;
      const first = all.length ? Math.min(...all.map((t) => Date.parse(t.opened_at))) : Date.now();
      const pts = [{ x: first, y: 0, id: "start" }].concat(closed.map((t) => ({ x: Date.parse(t.closed_at), y: +(cum += usd(t)).toFixed(2), id: `${t.id} ${t.pnl_pct > 0 ? "+" : ""}${t.pnl_pct}%` })));
      pts.push({ x: Date.now(), y: pts[pts.length - 1].y, id: "now" });
      if (D.charts.track) D.charts.track.destroy();
      D.charts.track = new Chart($("chart-track"), {
        type: "line",
        data: { datasets: [{ label: `Cumulative P&L ($${MARGIN} margin per trade)`, data: pts, stepped: true, borderColor: D.COLORS.base, borderWidth: 2, pointRadius: pts.map((p, i) => (i && i < pts.length - 1 ? 4 : 0)), pointBackgroundColor: pts.map((p) => (p.y < 0 ? D.COLORS.res : D.COLORS.sup)),
          fill: { target: { value: 0 }, above: "rgba(34,197,94,0.14)", below: "rgba(244,63,94,0.14)" } }] },
        options: { responsive: true, maintainAspectRatio: false, animation: false, parsing: false,
          scales: { x: { type: "linear", min: pts[0].x, max: pts[pts.length - 1].x, afterBuildTicks: D.dayTicks, grid: { color: D.COLORS.grid }, ticks: { callback: (v) => D.shortDate(v) } },
            y: { grid: { color: D.COLORS.grid }, ticks: { callback: (v) => `$${v}` } } },
          plugins: { legend: { labels: { color: D.COLORS.tick } }, tooltip: { callbacks: { title: (it) => D.ct(it[0].parsed.x), label: (it) => `${it.raw.id}: $${it.parsed.y.toFixed(2)} cumulative` } } } },
      });
    }
  }

  /* ---------------- position calculator ---------------- */
  function startCalc(st) {
    const D = window.Dash;
    const f = $("calc");
    if (!f) return;
    const ids = [...new Set([...(D.allIds ? D.allIds(st.prices) : st.prices.coins), st.prices.backdrop])].filter((id) => st.prices.assets[id]);
    f.coin.innerHTML = ids.map((id) => `<option value="${id}">${D.esc(st.prices.assets[id].symbol)} — ${D.esc(st.prices.assets[id].name)}</option>`).join("");
    f.coin.value = "ripple";
    const livePrice = (id) => st.live[id]?.price ?? st.prices.assets[id].price;
    const dec = (p) => (p >= 1000 ? 2 : p >= 1 ? 4 : p >= 0.01 ? 5 : 7);
    const setNum = (input, v) => { input.value = +(+v).toFixed(dec(v)); };
    function prefill(useSlate) {
      const id = f.coin.value, p = livePrice(id);
      const t = useSlate && (st.trades.trades || []).find((x) => x.coin === id && ["pending", "open"].includes(x.status));
      if (t) {
        const z = t.entry_zone; const e = t.status === "open" ? t.entry : z ? (z.low + z.high) / 2 : t.entry;
        f.side.value = t.direction; setNum(f.entry, e); setNum(f.stp, t.current_stop ?? t.stop); setNum(f.tgt, t.targets[0]); f.lev.value = t.leverage || 1;
        $("calc-src").textContent = `Loaded ${t.id} (${t.status}) from the slate.`;
      } else {
        const long = f.side.value === "long";
        setNum(f.entry, p); setNum(f.stp, p * (long ? 0.97 : 1.03)); setNum(f.tgt, p * (long ? 1.06 : 0.94));
        $("calc-src").textContent = `Entry prefilled with the live price ${D.fmtPrice(p)}; stop/target default to −3% / +6%.`;
      }
      f.levn.value = f.lev.value;
      calc();
    }
    function calc() {
      const long = f.side.value === "long", m = +f.margin.value, L = Math.min(20, Math.max(1, +f.lev.value)), e = +f.entry.value, tg = +f.tgt.value, sp = +f.stp.value;
      const out = $("calc-out");
      if (!(m > 0 && e > 0 && tg > 0 && sp > 0)) { out.innerHTML = '<p class="meta">Enter positive numbers.</p>'; return; }
      const s = long ? 1 : -1, size = m * L, qty = size / e;
      const pnlT = s * (tg - e) * qty, pnlS = s * (sp - e) * qty;
      const liq = long ? e * (1 - 1 / L) : e * (1 + 1 / L);
      const rr = Math.abs(tg - e) / Math.abs(e - sp);
      const badSide = long ? (tg <= e || sp >= e) : (tg >= e || sp <= e);
      const stopPastLiq = long ? (L > 1 && sp <= liq) : sp >= liq;
      const money = (v) => `<span class="${v > 0 ? "up" : v < 0 ? "down" : ""}">${v < 0 ? "−" : "+"}$${Math.abs(v).toFixed(2)}</span>`;
      const cell = (k, v, sub) => `<div class="co"><small>${k}</small><b class="mono">${v}</b>${sub ? `<span>${sub}</span>` : ""}</div>`;
      out.innerHTML = [
        cell("Position size", `$${size.toLocaleString(undefined, { maximumFractionDigits: 2 })}`, `${qty.toLocaleString(undefined, { maximumFractionDigits: qty < 10 ? 4 : 0 })} ${D.esc(st.prices.assets[f.coin.value].symbol)}`),
        cell("At target", money(pnlT), D.pct((pnlT / m) * 100) + " of margin"),
        cell("At stop", money(pnlS), D.pct((pnlS / m) * 100) + " of margin"),
        cell("Risk / reward", isFinite(rr) ? `1 : ${rr.toFixed(2)}` : "—", rr >= 2 ? '<span class="up">good</span>' : rr >= 1 ? "ok" : '<span class="down">poor</span>'),
        long && L === 1 ? cell("Approx. liquidation", "none", "spot (1x long): no liquidation") : cell("Approx. liquidation", D.fmtPrice(liq), `${(((liq - e) / e) * 100).toFixed(1)}% from entry`),
      ].join("") + (badSide ? `<p class="calc-warn">Check the side: for a ${long ? "long" : "short"}, the target should be ${long ? "above" : "below"} entry and the stop ${long ? "below" : "above"} it.</p>` : "")
        + (stopPastLiq ? `<p class="calc-warn">Your stop is at or beyond the approximate liquidation price — you would likely be liquidated first. Lower the leverage or tighten the stop.</p>` : "");
    }
    f.addEventListener("input", (ev) => { if (ev.target === f.lev) f.levn.value = f.lev.value; if (ev.target === f.levn) f.lev.value = f.levn.value; calc(); });
    f.coin.addEventListener("change", () => prefill(false));
    f.side.addEventListener("change", () => calc());
    $("calc-live").addEventListener("click", () => { setNum(f.entry, livePrice(f.coin.value)); calc(); });
    $("calc-slate").addEventListener("click", () => prefill(true));
    f.addEventListener("submit", (e) => e.preventDefault());
    document.addEventListener("live:tick", (ev) => { if (ev.detail.id === f.coin.value) $("calc-livep").textContent = D.fmtPrice(ev.detail.price); });
    $("calc-livep").textContent = D.fmtPrice(livePrice(f.coin.value));
    f.coin.addEventListener("change", () => ($("calc-livep").textContent = D.fmtPrice(livePrice(f.coin.value))));
    prefill(true);
  }

  function boot() {
    if (!window.Dash || !window.Dash.ready) return setTimeout(boot, 50);
    window.Dash.ready.then((st) => {
      startContext(st.context);
      renderTrack(st);
      startCalc(st);
    });
  }
  boot();
})();
