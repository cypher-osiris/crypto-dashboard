/* Lumi Glow hero: the home page's 3-slide deck (today's levels chart, the x402 agent flow, latest delivered trust test-buys)
 * and the trust page's live test-buy feed. No libraries. Motion rules: one thing moves at a time (the chart draws only
 * while slide 1 is showing), slides rotate every 8 s and pause on hover, focus and touch, and there is no autoplay with
 * prefers-reduced-motion or on small screens (there the slides are swipeable tabs). Data: data/*.json and the public trust API. */
(() => {
  "use strict";
  const I = window.LumiI18n || { t: (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s), locale: "en-US" };
  const tr = I.t, LOC = I.locale || "en-US";
  const root = document.documentElement.getAttribute("data-root") || (document.body.classList.contains("cp") ? "../" : "");
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const j = (u) => fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const mq = (q) => !!(window.matchMedia && window.matchMedia(q).matches);
  const REDUCE = mq("(prefers-reduced-motion: reduce)");
  function fmt(p) {
    if (p == null || !isFinite(p)) return "–";
    const d = p >= 1000 ? 0 : p >= 1 ? 4 : p >= 0.01 ? 4 : 6;
    return Number(p).toLocaleString(LOC, { minimumFractionDigits: p >= 1000 ? 0 : 2, maximumFractionDigits: d });
  }
  const NET = (n) => { n = String(n || "").split(":")[0]; return n === "xrpl" ? "XRPL" : n === "eip155" ? "Base" : n === "stellar" ? "Stellar" : n; };
  const host = (u) => { try { return new URL(u).host.replace(/^www\./, ""); } catch (e) { return ""; } };
  const ct = (iso) => new Date(iso).toLocaleString(LOC, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago" }) + " CT";

  /* ---- trust feed (home slide 3 and trust page hero) ---- */
  function feed() {
    const box = $("ag-rows");
    if (!box) return;
    j("https://api.lumitrades.io/v1/trust/vendors").then((d) => {
      const rows = (d.vendors || []).filter((v) => { const o = v.last_paid_observation; return o && o.observed_at && o.delivery === "delivered"; })
        .sort((a, b) => b.last_paid_observation.observed_at.localeCompare(a.last_paid_observation.observed_at)).slice(0, 4);
      box.innerHTML = rows.map((v) => {
        const o = v.last_paid_observation;
        return `<li><span class="ag-r-ic ok" aria-hidden="true">✓</span><span class="ag-r-m"><b>${esc(host(o.endpoint) || v.name)}</b>` +
          `<small>${esc(NET(o.network))} · HTTP <span class="mono">${esc(o.http_status)}</span> · ${esc(ct(o.observed_at))}</small></span>` +
          `<span class="ag-r-s ok">${esc(tr("Delivered"))}</span></li>`;
      }).join("") || `<li class="ag-empty">${esc(tr("No delivered test-buys in the live feed right now."))}</li>`;
    }).catch(() => { box.innerHTML = `<li class="ag-empty">${esc(tr("Live feed unavailable right now. See the vendor trust list."))}</li>`; });
  }

  /* ---- slide 1: live chart with today's paper-trade levels + slate summary ---- */
  let chartReady = false, wantDraw = false;
  const panel = $("lg-deck");
  function draw() {
    if (!panel) return;
    if (!chartReady) { wantDraw = true; return; }
    panel.classList.remove("drawn");
    if (REDUCE) return;
    void panel.offsetWidth;
    panel.classList.add("drawn");
    // one motion at a time: hold the price ticker still while the line draws
    document.body.classList.add("lg-drawing");
    clearTimeout(draw.t); draw.t = setTimeout(() => document.body.classList.remove("lg-drawing"), 2500);
  }
  function chart() {
    if (!$("ag-svg")) return;
    Promise.all([j(root + "data/prices.json"), j(root + "data/trades.json").catch(() => null), j(root + "data/signals.json").catch(() => null)]).then(([P, T, S]) => {
      const slate = (T && T.slate && T.slate.coins) || {}, byId = {};
      (T && T.trades || []).forEach((t) => { byId[t.id] = t; });
      const active = Object.keys(slate).map((c) => [c, byId[slate[c] && slate[c].trade_id]]).filter(([c, t]) => t && (t.status === "open" || t.status === "pending"));
      let coin = "ripple", trd = null;
      const pick = active.find(([c]) => c === "ripple") || active.find(([c]) => P.assets[c] && P.assets[c].history);
      if (pick && P.assets[pick[0]]) { coin = pick[0]; trd = pick[1]; }
      const a = P.assets[coin];
      if (!a || !a.history) return;
      const xs = a.history.slice(-168).map((p) => p[1]);
      const lv = [];
      if (trd) {
        if (trd.entry_zone) lv.push({ k: "zone", lo: trd.entry_zone.low, hi: trd.entry_zone.high });
        if (trd.stop != null) lv.push({ k: "stop", v: trd.stop });
        (trd.targets || []).forEach((v, i) => lv.push({ k: "t", v, n: i + 1 }));
      }
      let lo = Math.min(...xs), hi = Math.max(...xs);
      lv.forEach((l) => (l.k === "zone" ? [l.lo, l.hi] : [l.v]).forEach((v) => { if (v < lo && v > lo - (hi - lo) * 0.5) lo = v; if (v > hi && v < hi + (hi - lo) * 0.5) hi = v; }));
      const pad = (hi - lo) * 0.12 || 1; lo -= pad; hi += pad;
      const W = 600, H = 230, y = (v) => (H - 14) - (v - lo) / (hi - lo) * (H - 28);
      let g = "";
      lv.forEach((l) => {
        if (l.k === "zone") {
          const y1 = y(l.hi), y2 = y(l.lo);
          if (y2 < 0 || y1 > H) return;
          g += `<rect class="lvl-zone" x="0" width="${W}" y="${y1.toFixed(1)}" height="${Math.max(3, y2 - y1).toFixed(1)}"/>` +
            `<text class="lvt lvt-z" x="${W - 4}" y="${(y1 - 5).toFixed(1)}" text-anchor="end">${esc(tr("Entry zone"))} ${fmt(l.lo)}–${fmt(l.hi)}</text>`;
        } else {
          const yy = y(l.v);
          if (yy < 10 || yy > H - 4) return;
          const lab = l.k === "stop" ? tr("Stop") : tr("Target {n}", { n: l.n });
          g += `<line class="lvl-${l.k}" x1="0" x2="${W}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}"/>` +
            `<text class="lvt lvt-${l.k}" x="${W - 4}" y="${(yy - 5).toFixed(1)}" text-anchor="end">${esc(lab)} ${fmt(l.v)}</text>`;
        }
      });
      $("ag-levels").innerHTML = g;
      // the price line stops short of the stop/target labels so the last price never sits under a label
      let gut = 0;
      $("ag-levels").querySelectorAll(".lvt-stop,.lvt-t").forEach((t) => { try { gut = Math.max(gut, t.getBBox().width); } catch (e) {} });
      const R = Math.round(Math.min(560, Math.max(380, W - gut - 16)));
      const d = xs.map((v, i) => (i ? "L" : "M") + (i / (xs.length - 1) * R).toFixed(1) + " " + y(v).toFixed(1)).join(" ");
      $("ag-line").setAttribute("d", d);
      $("ag-area").setAttribute("d", d + ` L${R} ${H} L0 ${H}Z`);
      const dot = $("ag-dot"); dot.setAttribute("cx", R); dot.setAttribute("cy", y(xs[xs.length - 1]).toFixed(1));
      $("ag-sym").textContent = a.symbol || coin.toUpperCase();
      $("ag-px").textContent = "$" + fmt(a.price);
      const c = a.change_24h, ce = $("ag-chg");
      if (c != null) { ce.textContent = (c >= 0 ? "▲ +" : "▼ ") + c.toFixed(2) + "% 24h"; ce.className = "ag-chg mono " + (c >= 0 ? "up" : "down"); }
      if (S && S.coins && S.coins[coin] && S.coins[coin].label) { const sg = $("ag-sig"); sg.textContent = tr("Signal: {label}", { label: tr(S.coins[coin].label) }); sg.hidden = false; }
      const svg = $("ag-svg");
      svg.setAttribute("aria-label", tr("{sym}: 7-day price line with Lumi's paper-trade levels", { sym: a.symbol || coin.toUpperCase() }));
      // slate summary: every active idea, open or waiting for entry
      const ul = $("lg-slate");
      if (ul) {
        const items = active.slice(0, 6).map(([c, t]) => {
          const sym = (P.assets[c] && P.assets[c].symbol) || c.toUpperCase(), long = t.direction === "long";
          return `<li class="c"><b>${esc(sym)}</b> <span class="${long ? "long" : "short"}">${esc(tr(long ? "Long" : "Short"))}</span> <span class="st">${esc(tr(t.status === "open" ? "Open" : "Pending"))}</span></li>`;
        });
        ul.innerHTML = `<li class="lbl">${esc(tr("Today's slate:"))}</li>` + (items.join("") || `<li class="c st">${esc(tr("No active ideas right now."))}</li>`);
      }
      chartReady = true;
      if (wantDraw || (panel && panel.querySelector(".lg-slide.on") === $("lg-s0"))) draw();
    }).catch(() => {});
  }

  /* ---- the deck ---- */
  function deck() {
    if (!panel) return;
    const tabs = [...panel.querySelectorAll('[role="tab"]')], slides = tabs.map((t) => $(t.getAttribute("aria-controls")));
    const box = $("lg-slides"), btn = $("lg-pause"), DUR = 8000;
    const small = () => mq("(max-width: 760px)");
    let cur = 0, timer = 0, hold = 0, stopped = REDUCE || small();
    function select(i, opts) {
      opts = opts || {};
      cur = (i + slides.length) % slides.length;
      tabs.forEach((t, k) => { const on = k === cur; t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1; slides[k].classList.toggle("on", on); });
      if (opts.focus) tabs[cur].focus();
      if (small() && opts.scroll !== false) box.scrollTo({ left: slides[cur].offsetLeft - box.offsetLeft, behavior: REDUCE ? "auto" : "smooth" });
      if (cur === 0) draw(); else panel.classList.remove("drawn");
    }
    function setStopped(v) {
      stopped = v;
      panel.classList.toggle("stopped", v);
      box.setAttribute("aria-live", v ? "polite" : "off");
      if (btn) { const l = tr(v ? "Play slides" : "Pause slides"); btn.setAttribute("aria-label", l); btn.title = l; btn.setAttribute("aria-pressed", v ? "true" : "false"); }
      tick();
    }
    function tick() {
      clearTimeout(timer);
      if (stopped || hold || REDUCE || small() || document.hidden) return;
      timer = setTimeout(() => { select(cur + 1, { scroll: false }); tick(); }, DUR);
    }
    tabs.forEach((t, k) => {
      t.addEventListener("click", () => { select(k); tick(); });
      t.addEventListener("keydown", (e) => {
        const n = { ArrowRight: cur + 1, ArrowLeft: cur - 1, Home: 0, End: slides.length - 1 }[e.key];
        if (n === undefined) return;
        e.preventDefault(); select(n, { focus: true });
      });
    });
    if (btn) btn.addEventListener("click", () => setStopped(!stopped));
    const pause = () => { hold++; tick(); }, resume = () => { hold = Math.max(0, hold - 1); tick(); };
    panel.addEventListener("mouseenter", pause); panel.addEventListener("mouseleave", resume);
    panel.addEventListener("focusin", pause); panel.addEventListener("focusout", resume);
    panel.addEventListener("touchstart", () => { if (!stopped) setStopped(true); }, { passive: true }); // a touch means the reader is in control
    document.addEventListener("visibilitychange", tick);
    // small screens: swiping moves the selected tab along (scroll-snap does the swiping)
    let st = 0;
    box.addEventListener("scroll", () => {
      if (!small()) return;
      clearTimeout(st);
      st = setTimeout(() => { const i = Math.round(box.scrollLeft / Math.max(1, box.clientWidth)); if (i !== cur) select(i, { scroll: false }); }, 90);
    }, { passive: true });
    window.addEventListener("resize", () => { if (small() && !stopped) setStopped(true); });
    setStopped(stopped);
    select(0, { scroll: false });
  }

  function init() { deck(); chart(); feed(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
