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
  function row(v) {
    const s = v.samples || {}, o = v.last_paid_observation, home = vendorLink(v);
    const own = home.indexOf("https://api.lumitrades.io/trust/v/") === 0; // no working homepage: say it's Lumi's own result page
    const name = own ? `${esc(v.name || v.id)} <a class="tr-own" href="${esc(home)}" target="_blank" rel="noopener">${esc(tr("Lumi test result"))} ↗</a>`
      : home ? `<a href="${esc(home)}" target="_blank" rel="noopener nofollow">${esc(v.name || v.id)}</a>` : esc(v.name || v.id);
    const conf = String(v.confidence || "—");
    const confTxt = ["low", "medium", "high"].includes(conf) ? tr(conf) : conf;
    let ev = "—";
    if (o && o.observed_at) { // outcome + time of the latest paid test-buy (free data); tx hashes are in the paid vendor report
      const dv = o.delivery === "delivered" ? tr("Delivered") : (o.delivery === "not_delivered" || o.delivery === "failed" || o.data_returned === false) ? tr("No data") : tr("Inconclusive");
      ev = `<span title="${esc(tr("Tx hash and signed receipt: paid vendor report ($0.02)"))}">${esc(dv)} · ${esc(fmt(o.observed_at))}</span>`;
    }
    if (o && https(o.explorer)) {
      ev = `<a href="${esc(o.explorer)}" target="_blank" rel="noopener" title="${esc(o.summary || "")}">${esc(((o.amount || "") + " " + (o.asset || "")).trim())} · ${esc(o.data_returned ? tr("data") : tr("no data"))} ↗</a>`;
    }
    if (v.replies && https(v.detail)) ev += ` <a href="${esc(v.detail)}" target="_blank" rel="noopener">· ${esc(tr("reply ({n})", { n: v.replies }))}</a>`;
    return `<tr><td>${name}${badge(o)}<span class="vid">${esc(v.id)}</span></td><td class="num">${v.score == null ? "—" : esc(v.score)}</td>` +
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
