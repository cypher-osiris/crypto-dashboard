/* Affiliate links — driven by data/config.json. Empty bitunix_url => nothing is shown. */
(() => {
  "use strict";
  const DISCLOSURE = "Some links are affiliate links; we may earn a commission at no cost to you. Paper trades, not financial advice.";
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let URL_ = "", LABEL = "Trade on Bitunix";

  const link = (text, cls) => `<a class="aff-btn ${cls || ""}" href="${esc(URL_)}" rel="sponsored noopener" target="_blank">${esc(text)}<span aria-hidden="true"> ↗</span></a>`;
  const note = () => `<p class="aff-note">${esc(DISCLOSURE)}</p>`;

  function decorateSlate() {
    document.querySelectorAll(".slate-card[data-slate]").forEach((card) => {
      if (card.querySelector(".aff-wrap")) return;
      if (!(card.classList.contains("pending") || card.classList.contains("open"))) return; // active ideas only
      const sym = (card.querySelector(".coin-mark") || {}).textContent || "";
      const w = document.createElement("div");
      w.className = "aff-wrap";
      w.innerHTML = link("Trade this setup on Bitunix", "") + note();
      const a = w.querySelector("a"); if (sym) a.setAttribute("aria-label", `Trade this ${sym} setup on Bitunix (affiliate link, opens in a new tab)`);
      const why = card.querySelector("details.why");
      why ? card.insertBefore(w, why) : card.appendChild(w);
    });
  }

  function apply() {
    const cta = document.getElementById("aff-cta");
    if (cta) { cta.innerHTML = link(LABEL, "sm") + `<a class="aff-tag" href="#aff-foot">Affiliate link · disclosure</a>`; cta.hidden = false; }
    const calc = document.getElementById("aff-calc");
    if (calc) { calc.innerHTML = link(LABEL, "") + note(); calc.hidden = false; }
    const foot = document.getElementById("aff-foot");
    if (foot) { foot.textContent = DISCLOSURE; foot.hidden = false; }
    decorateSlate();
    const grid = document.getElementById("slate-grid");
    if (grid) new MutationObserver(decorateSlate).observe(grid, { childList: true, subtree: true });
  }

  async function start() {
    try {
      const r = await fetch(`data/config.json?v=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) return;
      const a = ((await r.json()) || {}).affiliate || {};
      const u = String(a.bitunix_url || "").trim();
      if (!/^https:\/\/[^\s"'<>]+$/i.test(u)) return; // empty or not https => keep everything hidden
      URL_ = u; if (a.label) LABEL = String(a.label);
      document.documentElement.classList.add("has-aff");
      apply();
    } catch (e) { /* config missing/invalid => no affiliate UI */ }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
