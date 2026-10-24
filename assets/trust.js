/* /trust/: the vendor table is rendered at build time (scripts/site_pages.py); this refreshes it live from the free
 * endpoint https://api.lumitrades.io/v1/trust/vendors. On any error the static table simply stays. */
(() => {
  "use strict";
  const API = "https://api.lumitrades.io/v1/trust/vendors";
  const I = window.LumiI18n || { t: (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s), locale: "en-US", en: true };
  const tr = I.t;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const https = (u) => (/^https:\/\//i.test(u || "") ? u : "");
  // vendor homepages that don't load for visitors: link to Lumi's vendor report instead (mirrors NO_HOME in scripts/site_pages.py)
  const NO_HOME = ["x402.cryptobuddy.com.au", "oracle.evebrief.org"];
  function vendorLink(v) {
    const home = https(v.homepage);
    const host = (home.match(/^https:\/\/([^\/:]+)/i) || [])[1] || "";
    return NO_HOME.includes(host.toLowerCase()) && v.id ? "https://api.lumitrades.io/trust/v/" + encodeURIComponent(v.id) : home;
  }
  function fmt(iso) {
    const d = new Date(iso || "");
    if (!iso || isNaN(d)) return "—";
    try { return d.toLocaleString(I.locale || "en-US", { timeZone: "America/Chicago", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " CT"; }
    catch (e) { return d.toISOString().slice(0, 16).replace("T", " ") + " UTC"; }
  }
  function lastChecked(v) {
    const t = (v.latest_probes || []).filter((p) => p && p.checked_at).map((p) => p.checked_at);
    if (v.last_paid_observation && v.last_paid_observation.observed_at) t.push(v.last_paid_observation.observed_at);
    t.sort();
    return t.length ? t[t.length - 1] : null;
  }
  // "Tested by Lumi" badge from the latest stored paid test-buy only (mirrors badge_html() in scripts/site_pages.py):
  // result · UTC date (MM-DD-YYYY, as on the API badge) · chain. No paid test-buy on record = no badge.
  function chainName(n) {
    n = String(n || "").toLowerCase();
    if (n.indexOf("xrpl") === 0) return "XRPL";
    if (n.indexOf("stellar") === 0) return "Stellar";
    return ["base", "base-mainnet", "eip155:8453"].includes(n) ? "Base" : "";
  }
  const RES = { delivered: "delivered", no_delivery: "no delivery", inconclusive: "inconclusive" };
  const TIP = { delivered: "Latest paid test-buy by Lumi: data delivered.", no_delivery: "Latest paid test-buy by Lumi: no data delivered.",
    inconclusive: "Latest paid test-buy by Lumi: result inconclusive." };
  function badge(o) {
    if (!o || !o.observed_at) return "";
    const m = String(o.observed_at).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return "";
    const res = o.delivery === "delivered" ? "delivered"
      : (o.delivery === "not_delivered" || o.delivery === "failed" || o.data_returned === false) ? "no_delivery" : "inconclusive";
    const ch = chainName(o.network);
    const right = [tr(RES[res]), m[2] + "-" + m[3] + "-" + m[1]].concat(ch ? [ch] : []).join(" · ");
    const label = tr("Tested by Lumi");
    const tip = tr(TIP[res]) + " " + tr("Date in UTC. A dated test result, not an endorsement or guarantee.");
    return `<span class="lt-badge b-${res}" role="img" aria-label="${esc(label)}: ${esc(right)}" title="${esc(tip)}">` +
      `<span class="lt-b-l" aria-hidden="true">${esc(label)}</span><span class="lt-b-r" aria-hidden="true">${esc(right)}</span></span>`;
  }
  // Free on-chain proof (mirrors obs_tx()/tx_html() in scripts/site_pages.py): the tx hash of the latest paid test-buy, from
  // the live API if it carries one, else from the build's copy (#tr-tx) only when id, observed_at, endpoint and network all
  // match that same buy. No match = no link; hashes are never derived or made up.
  let SNAP = {};
  try { SNAP = JSON.parse(($("tr-tx") || {}).textContent || "{}") || {}; } catch (e) { SNAP = {}; }
  const EXPL = { XRPL: "https://livenet.xrpl.org/transactions/", Base: "https://basescan.org/tx/", Stellar: "https://stellar.expert/explorer/public/tx/" };
  const TXRE = { XRPL: /^[0-9A-F]{64}$/, Base: /^0x[0-9a-f]{64}$/, Stellar: /^[0-9a-f]{64}$/ };
  function txFor(v, o) {
    if (!o || !o.observed_at) return null;
    const ch = chainName(o.network);
    if (!ch) return null;
    let h = o.tx_hash;
    if (!h) {
      const x = Object.prototype.hasOwnProperty.call(SNAP, v.id) ? SNAP[v.id] : null;
      if (x && x.observed_at === o.observed_at && x.endpoint === o.endpoint && x.network === o.network) h = x.tx_hash;
    }
    h = String(h || "").trim();
    h = ch === "XRPL" ? h.toUpperCase() : ch === "Base" ? h.toLowerCase() : h;
    return TXRE[ch].test(h) ? { h, url: EXPL[ch] + h, ch } : null;
  }
  function txLink(v, o) {
    const t = txFor(v, o);
    if (!t) return "";
    const short = t.h.indexOf("0x") === 0 ? t.h.slice(0, 8) + "…" + t.h.slice(-6) : t.h.slice(0, 6) + "…" + t.h.slice(-6);
    return `<span class="tr-tx">${esc(tr("On-chain tx"))} <a href="${esc(t.url)}" target="_blank" rel="noopener" ` +
      `title="${esc(tr("Lumi's payment for this test-buy on the public {chain} ledger. Free to check.", { chain: t.ch }))}" data-tx="${esc(t.h)}"><code>${esc(short)}</code> ↗</a></span>`;
  }
  // Opt-in "Test payment not accepted yet on XRPL" label (mirrors vendor_attempts()/attempts_html() in scripts/site_pages.py): only for
  // vendors with zero paid test-buys and an explicit opt-in (the API's payment_attempts, else the build's copy in #tr-att).
  // Neutral grey, never part of the score. "The seller is online" only if a quote check in the last 90 min got a valid 402.
  let ATT = {};
  try { ATT = JSON.parse(($("tr-att") || {}).textContent || "{}") || {}; } catch (e) { ATT = {}; }
  function attempts(v) {
    if ((v.samples && v.samples.paid_test_buys) || v.last_paid_observation) return null;
    let a = v.payment_attempts;
    if (!(a && a.status === "test_payment_not_accepted_yet")) a = Object.prototype.hasOwnProperty.call(ATT, v.id) ? ATT[v.id] : null;
    const n = a ? parseInt(a.count, 10) : 0;
    return n >= 1 && !isNaN(new Date(a.first_attempt || "")) ? { count: n, first_attempt: a.first_attempt } : null;
  }
  function online(v) {
    if (v.status && v.status !== "live") return false;
    return (v.latest_probes || []).some((p) => {
      const t = new Date((p && p.checked_at) || "").getTime();
      return p && p.http_status === 402 && p.valid_quote === true && !isNaN(t) && Date.now() - t >= -60000 && Date.now() - t <= 90 * 60000;
    });
  }
  function fmtDate(iso) {
    const d = new Date(iso);
    try { return d.toLocaleDateString(I.locale || "en-US", { timeZone: "America/Chicago", year: "numeric", month: "short", day: "numeric" }); }
    catch (e) { return d.toISOString().slice(0, 10); }
  }
  function attLabel(v) {
    const a = attempts(v);
    if (!a) return "";
    const date = fmtDate(a.first_attempt);
    let note = a.count === 1 ? tr("Lumi has tried once on XRPL, on {date}.", { date }) : tr("Lumi has tried {n} times on XRPL since {date}.", { n: a.count, date });
    if (online(v)) note += (/^ja/i.test(I.locale || "") ? "" : " ") + tr("The seller is online, but our payment hasn't gone through yet.");
    return `<span class="tr-att" title="${esc(tr("Lumi's signed test payments on the XRPL were not accepted by this endpoint, so nothing was charged. Informational only; not part of the score."))}">${esc(tr("Test payment not accepted yet on XRPL"))}</span>` +
      `<span class="tr-att-note">${esc(note)} <a href="#reply">${esc(tr("Seller? Help us complete it"))}</a></span>`;
  }
  function row(v) {
    const s = v.samples || {}, o = v.last_paid_observation, home = vendorLink(v);
    const own = home.indexOf("https://api.lumitrades.io/trust/v/") === 0; // no working homepage: say it's Lumi's own result page
    const name = own ? `${esc(v.name || v.id)} <a class="tr-own" href="${esc(home)}" target="_blank" rel="noopener">${esc(tr("Lumi test result"))} ↗</a>`
      : home ? `<a href="${esc(home)}" target="_blank" rel="noopener nofollow">${esc(v.name || v.id)}</a>` : esc(v.name || v.id);
    const conf = String(v.confidence || "—");
    const confTxt = ["low", "medium", "high"].includes(conf) ? tr(conf) : conf;
    let ev = "—";
    if (o && o.observed_at) { // outcome + time of the latest paid test-buy (free data); signed receipts are in the paid vendor report
      const dv = o.delivery === "delivered" ? tr("Delivered") : (o.delivery === "not_delivered" || o.delivery === "failed" || o.data_returned === false) ? tr("No data") : tr("Inconclusive");
      ev = `<span title="${esc(tr("Signed receipt and full history: paid vendor report ($0.02)"))}">${esc(dv)} · ${esc(fmt(o.observed_at))}</span>`;
    }
    if (o && https(o.explorer)) {
      ev = `<a href="${esc(o.explorer)}" target="_blank" rel="noopener" title="${esc(o.summary || "")}">${esc(((o.amount || "") + " " + (o.asset || "")).trim())} · ${esc(o.data_returned ? tr("data") : tr("no data"))} ↗</a>`;
    }
    if (v.replies && https(v.detail)) ev += ` <a href="${esc(v.detail)}" target="_blank" rel="noopener">· ${esc(tr("reply ({n})", { n: v.replies }))}</a>`;
    return `<tr><td>${name}${badge(o)}${txLink(v, o)}${attLabel(v)}<span class="vid">${esc(v.id)}</span></td><td class="num">${v.score == null ? "—" : esc(v.score)}</td>` +
      `<td><span class="tr-conf c-${esc(conf)}">${esc(confTxt)}</span></td><td class="num">${esc(s.paid_test_buys || 0)}</td>` +
      `<td class="num">${esc(s.delivered || 0)}</td><td>${esc(fmt(lastChecked(v)))}</td><td>${ev}</td></tr>`;
  }
  fetch(API, { headers: { Accept: "application/json" } })
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((d) => {
      const list = (d && d.vendors) || [];
      if (!list.length) return;
      $("tr-body").innerHTML = list.map(row).join("");
      $("tr-count").textContent = "(" + list.length + ")";
      if (d.generated_at) $("tr-gen").textContent = tr("Data generated {when}.", { when: fmt(d.generated_at) });
      $("tr-table").hidden = false;
      if ($("tr-status")) $("tr-status").hidden = true;
    })
    .catch(() => {
      const st = $("tr-status");
      if (st) st.innerHTML = esc(tr("Could not load observations right now.")) + ` <a href="${API}">${API}</a>`;
    });
})();
