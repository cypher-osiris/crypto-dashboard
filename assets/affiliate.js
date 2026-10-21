/* Affiliate links — driven by data/config.json, geo-gated client-side.
 *   Bitunix (affiliate.bitunix_url)   NON-US visitors only (Bitunix bans US users).
 *   Coinbase (US visitors only): affiliate.coinbase_advanced_url = main "Trade on Coinbase Advanced" buttons,
 *     affiliate.coinbase_url = small "New to crypto? Get started on Coinbase" link. Both empty => nothing is shown.
 * Fail closed: all affiliate UI stays hidden until the country is known. Lookup order:
 *   ?geo=XX debug override -> sessionStorage cache -> api.country.is -> ipapi.co/country -> Intl timeZone (US zones => US).
 * If everything fails (no country, no time zone) nothing is shown.
 * Coinbase links are referral JOIN links used exactly as configured (no per-coin path/query is ever appended, so the
 *   referral code is never dropped). They open Coinbase's "Sign up to activate your referral" page; an existing member
 *   (e.g. the referrer himself) only sees that page plus "Already have an account?". So every Coinbase per-trade button
 *   carries a one-line note saying so and naming the pair to open after signing in. Coins with no Coinbase product in
 *   data/coins.json (ZBCN, XDC: card data-cb="") get NO Coinbase trade button, only a short "not listed on Coinbase" note.
 * Bitunix: always the general referral link (no per-pair URL). Spot ideas (leverage 1, card data-lev="1") are labelled
 *   "Buy <SYM> spot on Bitunix" (XDC has no Bitunix perpetual; XDC/USDT spot is listed).
 * Hardware-wallet pick (#wallet-pick, under the calculator): shown to ALL visitors, no geo gate.
 *   affiliate.dcent_url (+ dcent_label) = main button; affiliate.ledger_url (+ ledger_label) = second option, hidden while empty. */
(() => {
  "use strict";
  const DISCLOSURE = "Some links are affiliate links; we may earn a commission at no cost to you. Paper trades, not financial advice.";
  const CACHE_KEY = "lumi_geo_v1";
  const US_CODES = new Set(["US", "PR", "GU", "VI", "AS", "MP", "UM"]); // US + territories
  const US_ZONES = new Set(["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Phoenix",
    "America/Anchorage", "America/Detroit", "America/Boise", "Pacific/Honolulu", "America/Juneau", "America/Sitka",
    "America/Nome", "America/Yakutat", "America/Metlakatla", "America/Adak", "America/Menominee", "America/Puerto_Rico",
    "US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "US/Arizona", "US/Alaska", "US/Hawaii", "US/Michigan",
    // legacy/canonical aliases browsers may report (e.g. Chrome turns America/Indiana/Indianapolis into America/Indianapolis)
    "America/Indianapolis", "America/Fort_Wayne", "America/Knox_IN", "America/Louisville", "America/Shiprock", "America/Atka",
    "Navajo", "US/East-Indiana", "US/Indiana-Starke", "US/Aleutian", "EST5EDT", "CST6CDT", "MST7MDT", "PST8PDT",
    // territories
    "America/St_Thomas", "America/Virgin", "Pacific/Guam", "Pacific/Saipan", "Pacific/Pago_Pago", "Pacific/Samoa", "US/Samoa", "Pacific/Johnston"]);
  const US_ZONE_PREFIXES = ["America/Indiana/", "America/Kentucky/", "America/North_Dakota/"];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const okUrl = (u) => /^https:\/\/[^\s"'<>]+$/i.test(u);
  const cc = (s) => { const c = String(s || "").trim().toUpperCase(); return /^[A-Z]{2}$/.test(c) ? c : ""; };
  let P = null; // active program: { name, url, label, slate, aria, extra: {url, text} | null }

  // ---- geo ---------------------------------------------------------------------------------------
  async function fetchCountry(url, pick, ms) {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
    try {
      const r = await fetch(url, { signal: ctl.signal, cache: "no-store" });
      if (!r.ok) return "";
      return cc(pick(await r.text()));
    } catch (e) { return ""; } finally { clearTimeout(t); }
  }
  function zoneIsUS() {
    let z = ""; try { z = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { /* none */ }
    if (!z) return null; // unknown
    return US_ZONES.has(z) || US_ZONE_PREFIXES.some((p) => z.startsWith(p));
  }
  /* -> { us: true|false|null, country, src }  (us === null => unknown => show nothing) */
  async function geo() {
    const q = cc(new URLSearchParams(location.search).get("geo"));
    if (q) return { us: US_CODES.has(q), country: q, src: "override" }; // debug, never cached
    try { const c = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null"); if (c && typeof c.us === "boolean") return c; } catch (e) { /* ignore */ }
    let country = await fetchCountry("https://api.country.is/", (t) => { try { return JSON.parse(t).country; } catch (e) { return ""; } }, 2500);
    let src = "country.is";
    if (!country) { country = await fetchCountry("https://ipapi.co/country/", (t) => t, 2500); src = "ipapi.co"; }
    let res;
    if (country) res = { us: US_CODES.has(country), country, src };
    else { const z = zoneIsUS(); res = { us: z, country: z === null ? "" : (z ? "US?" : "non-US?"), src: "timezone" }; }
    if (typeof res.us === "boolean") { try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(res)); } catch (e) { /* private mode */ } }
    return res;
  }

  // ---- render ------------------------------------------------------------------------------------
  const link = (text, cls) => `<a class="aff-btn ${cls || ""}" href="${esc(P.url)}" rel="sponsored noopener" target="_blank">${esc(text)}<span aria-hidden="true"> ↗</span></a>`;
  const extra = () => P.extra ? `<a class="aff-extra" href="${esc(P.extra.url)}" rel="sponsored noopener" target="_blank">${esc(P.extra.text)}<span aria-hidden="true"> ↗</span></a>` : "";
  const note = () => `<p class="aff-note">${esc(DISCLOSURE)}</p>`;

  function decorateSlate() {
    document.querySelectorAll(".slate-card[data-slate]").forEach((card) => {
      if (card.querySelector(".aff-wrap")) return;
      if (!(card.classList.contains("pending") || card.classList.contains("open"))) return; // active ideas only
      const sym = card.dataset.sym || (card.querySelector(".coin-mark") || {}).textContent || "";
      const spot = card.dataset.lev === "1";
      const w = document.createElement("div");
      w.className = "aff-wrap";
      if (P.key === "coinbase" && card.dataset.cb === "") {
        // not listed on Coinbase => a Coinbase "trade" button would lead nowhere useful
        w.innerHTML = `<p class="aff-note">${esc(sym)} isn't listed on Coinbase, so there's no Coinbase button for this idea.</p>`;
      } else {
        const lbl = P.key === "bitunix" && spot ? `Buy ${sym} spot on Bitunix` : P.slate;
        const hint = P.key === "coinbase" ? `<p class="aff-note">Referral sign-up link (new Coinbase accounts). Already have one? Sign in at Coinbase Advanced and open ${esc(card.dataset.cb || sym)}.</p>` : "";
        w.innerHTML = link(lbl, "") + hint + note();
        const a = w.querySelector("a");
        if (sym) a.setAttribute("aria-label", `${P.key === "bitunix" && spot ? lbl : P.aria(sym)} (affiliate link, opens in a new tab)`);
      }
      const why = card.querySelector(":scope > details.why");
      why ? card.insertBefore(w, why) : card.appendChild(w);
    });
  }

  function apply() {
    const cta = document.getElementById("aff-cta");
    if (cta) { cta.innerHTML = link(P.label, "sm") + extra() + `<a class="aff-tag" href="#aff-foot">Affiliate link · disclosure</a>`; cta.hidden = false; }
    const calc = document.getElementById("aff-calc");
    const cbHint = P.key === "coinbase" ? `<p class="aff-note">Coinbase referral sign-up page. Existing members: sign in on Coinbase as usual.</p>` : "";
    if (calc) { calc.innerHTML = link(P.label, "") + extra() + cbHint + note(); calc.hidden = false; }
    const foot = document.getElementById("aff-foot");
    if (foot) { foot.textContent = DISCLOSURE; foot.hidden = false; }
    decorateSlate();
    const grid = document.getElementById("slate-grid");
    if (grid) new MutationObserver(decorateSlate).observe(grid, { childList: true, subtree: true });
  }

  function renderWallet(a, s) {
    const box = document.getElementById("wallet-pick");
    const dcent = s("dcent_url"), ledger = s("ledger_url");
    if (!box || !dcent) return;
    const btn = (u, t, cls) => `<a class="aff-btn ${cls}" href="${esc(u)}" rel="sponsored noopener" target="_blank">${esc(t)}<span aria-hidden="true"> ↗</span></a>`;
    box.innerHTML = `<div class="w-ico" aria-hidden="true">🔐</div><div><h3>Keep your crypto safe</h3>` +
      `<p class="w-copy">Don't leave long-term holdings on an exchange. A hardware wallet keeps your keys offline. Lumi's pick: <b>D'CENT Biometric Wallet</b>.</p>` +
      `<div class="w-btns">${btn(dcent, String(a.dcent_label || "Get the D'CENT Biometric Wallet"), "sm")}` +
      (ledger ? btn(ledger, String(a.ledger_label || "Or choose Ledger"), "sm") : "") +
      `<a class="aff-tag" href="#aff-foot">Affiliate link · disclosure</a></div></div>`;
    box.hidden = false;
    const foot = document.getElementById("aff-foot");
    if (foot) { foot.textContent = DISCLOSURE; foot.hidden = false; }
    document.documentElement.classList.add("has-wallet-aff");
  }

  async function start() {
    try {
      const r = await fetch(`data/config.json?v=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) return;
      const a = ((await r.json()) || {}).affiliate || {};
      const s = (k) => { const u = String(a[k] || "").trim(); return okUrl(u) ? u : ""; };
      renderWallet(a, s); // all visitors, before any geo lookup
      const bitunix = s("bitunix_url"), cbAdv = s("coinbase_advanced_url"), cbJoin = s("coinbase_url");
      if (!bitunix && !cbAdv && !cbJoin) return; // nothing configured => no lookup, no UI
      const g = await geo();
      document.documentElement.dataset.geo = g.us === null ? "unknown" : (g.us ? "us" : "non-us");
      if (g.us === false && bitunix) {
        P = { key: "bitunix", url: bitunix, label: String(a.label || "Trade on Bitunix"), slate: "Trade this setup on Bitunix",
              aria: (sym) => `Trade this ${sym} setup on Bitunix`, extra: null };
      } else if (g.us === true && (cbAdv || cbJoin)) {
        // US: no leveraged perps on Coinbase for most users => neutral wording, no "setup" language
        const lbl = cbAdv ? String(a.coinbase_label || "Trade on Coinbase Advanced") : "Get started on Coinbase";
        P = { key: "coinbase", url: cbAdv || cbJoin, label: lbl, slate: lbl, aria: (sym) => `${lbl} (${sym})`,
              extra: cbAdv && cbJoin ? { url: cbJoin, text: "New to crypto? Get started on Coinbase" } : null };
      }
      if (!P) return; // unknown country, or no link for this region => keep everything hidden
      document.documentElement.classList.add("has-aff", "aff-" + P.key);
      apply();
    } catch (e) { /* config missing/invalid => no affiliate UI */ }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
