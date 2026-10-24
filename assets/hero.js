/* Lumi Glow hero: the home page's 2-slide deck (latest delivered trust test-buys first, then the x402 agent flow)
 * and the trust page's live test-buy feed. No libraries. The hero shows no market levels, targets or signals.
 * Slides rotate every 8 s and pause on hover, focus and touch, and there is no autoplay with prefers-reduced-motion
 * or on small screens (there the slides are swipeable tabs). Data: the public trust API. */
(() => {
  "use strict";
  const I = window.LumiI18n || { t: (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s), locale: "en-US" };
  const tr = I.t, LOC = I.locale || "en-US";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const j = (u) => fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const mq = (q) => !!(window.matchMedia && window.matchMedia(q).matches);
  const REDUCE = mq("(prefers-reduced-motion: reduce)");
  const NET = (n) => { n = String(n || "").split(":")[0]; return n === "xrpl" ? "XRPL" : n === "eip155" ? "Base" : n === "stellar" ? "Stellar" : n; };
  const host = (u) => { try { return new URL(u).host.replace(/^www\./, ""); } catch (e) { return ""; } };
  const ct = (iso) => new Date(iso).toLocaleString(LOC, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Chicago" }) + " CT";

  /* ---- trust feed (home slide 1 and trust page hero) ---- */
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

  const panel = $("lg-deck");

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

  function init() { deck(); feed(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
