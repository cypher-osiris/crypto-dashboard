/* Newsletter signup (Kit form 10079883). Progressive enhancement for form.nl-form:
 * without JS the form POSTs straight to Kit (app.kit.com/forms/10079883/subscriptions) and Kit shows its own page;
 * with JS it posts via fetch (Kit allows CORS, Accept: application/json) and shows the result inline.
 * Email only: the form has a single email_address field. */
(() => {
  "use strict";
  const tr = (window.LumiI18n && window.LumiI18n.t) || ((s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s)); // assets/i18n.js
  function wire(form) {
    if (form.dataset.wired) return; form.dataset.wired = "1";
    const msg = form.querySelector(".nl-msg"), btn = form.querySelector("button");
    form.addEventListener("submit", async (e) => {
      const email = form.querySelector('input[name="email_address"]');
      if (!email || !email.checkValidity()) return; // let the browser show its validation message
      e.preventDefault();
      btn.disabled = true; msg.className = "nl-msg"; msg.textContent = tr("Subscribing…");
      try {
        const r = await fetch(form.action, { method: "POST", headers: { Accept: "application/json" }, body: new FormData(form) });
        const j = await r.json().catch(() => ({}));
        if (r.ok && j.status !== "failed") {
          msg.className = "nl-msg ok";
          msg.textContent = tr("Almost done: check your inbox (and spam folder) to confirm your subscription.");
          form.classList.add("nl-done"); email.value = "";
        } else {
          throw new Error((j.errors && j.errors.join ? j.errors.join(" ") : "") || "failed");
        }
      } catch (err) {
        msg.className = "nl-msg err";
        msg.innerHTML = tr('Something went wrong. Please try again, or <a href="https://trade-with-lumi.kit.com/67c20c56b8" target="_blank" rel="noopener">sign up on the newsletter page</a>.');
      } finally { btn.disabled = false; }
    });
  }
  const go = () => document.querySelectorAll("form.nl-form").forEach(wire);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
})();
