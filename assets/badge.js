/* /agents/#badge: builds the "Tested by Lumi" badge URLs and embed snippets for one key, client-side.
 * key = a Lumi vendor id or the host of the seller's x402 URL. No listing or search: it only shows the one badge. */
(() => {
  "use strict";
  const API = "https://api.lumitrades.io";
  const I = window.LumiI18n || { t: (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s) };
  const tr = I.t;
  const $ = (id) => document.getElementById(id);
  const ALT = "Tested by Lumi: latest dated x402 test-buy result";
  const ID = /^[a-z0-9][a-z0-9-]{0,63}$/;
  const HOST = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}$/;
  function keyOf(raw) {
    let s = String(raw || "").trim().toLowerCase();
    if (!s) return null;
    if (/^[a-z][a-z0-9+.-]*:\/\//.test(s) || /[/?#]/.test(s)) {
      try { s = new URL(/^[a-z][a-z0-9+.-]*:\/\//.test(s) ? s : "https://" + s).hostname; } catch (e) { return null; }
    }
    s = s.replace(/\.$/, "");
    return ID.test(s) || HOST.test(s) ? s : null;
  }
  function init() {
    const f = $("bd-form");
    if (!f) return;
    f.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const k = keyOf($("bd-key").value);
      const out = $("bd-out"), err = $("bd-err");
      if (!k) {
        err.textContent = tr("Not a valid key: use a vendor id or a host name like api.example.com.");
        err.hidden = false; out.hidden = true;
        return;
      }
      err.hidden = true;
      const img = `${API}/badge/${encodeURIComponent(k)}.svg`, page = `${API}/trust/v/${encodeURIComponent(k)}`;
      out.textContent = "";
      const a = document.createElement("a");
      a.href = page; a.target = "_blank"; a.rel = "noopener";
      const im = document.createElement("img");
      im.src = img; im.alt = ALT; im.height = 20; im.style.verticalAlign = "middle";
      a.appendChild(im);
      const pl = document.createElement("a");
      pl.href = page; pl.target = "_blank"; pl.rel = "noopener"; pl.textContent = tr("Result page") + " ↗";
      out.append(a, " ", pl);
      out.hidden = false;
      $("bd-md").textContent = `[![${ALT}](${img})](${page})`;
      $("bd-html").textContent = `<a href="${page}"><img src="${img}" alt="${ALT}" height="20"></a>`;
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
