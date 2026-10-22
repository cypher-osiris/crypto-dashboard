/* Slate review schedule note (.slate-sched). The static text says the schedule in Central time; this adds
 * "Your time: …" when the visitor's zone shows different clock times, and "Next review: …". DST-safe: every review
 * instant is computed from America/Chicago wall time via Intl. Edit HOURS if the schedule changes (also index.html,
 * scripts/build_pages.py SCHEDULE_NOTE and the README). */
(() => {
  "use strict";
  const tr = (window.LumiI18n && window.LumiI18n.t) || ((s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s)); // assets/i18n.js
  const TZ = "America/Chicago", HOURS = [6, 12, 18, 23];
  const parts = (d, tz) => Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23",
    year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric" }).formatToParts(d).map((p) => [p.type, p.value]));
  // UTC instant of a wall-clock time in TZ (two passes settle the offset across DST changes)
  function zoned(y, m, d, h) {
    let t = Date.UTC(y, m - 1, d, h);
    for (let i = 0; i < 2; i++) {
      const p = parts(new Date(t), TZ);
      const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute);
      t += Date.UTC(y, m - 1, d, h) - asUtc;
    }
    return new Date(t);
  }
  const LOC = (window.LumiI18n && window.LumiI18n.locale) || "en-US";
  const fmt = (d, tz, opts) => new Intl.DateTimeFormat(LOC, Object.assign({ timeZone: tz, hour: "numeric" }, opts || {})).format(d);
  const clock = (d, tz) => { const p = parts(d, tz); return fmt(d, tz, +p.minute ? { minute: "2-digit" } : {}); };
  const join = (a) => a.length > 1 ? a.slice(0, -1).join(", ") + tr(" & ") + a[a.length - 1] : a.join("");
  function run() {
    const els = document.querySelectorAll(".slate-sched");
    if (!els.length) return;
    let local = ""; try { local = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { /* none */ }
    const now = new Date(), c = parts(now, TZ);
    const today = HOURS.map((h) => zoned(+c.year, +c.month, +c.day, h));
    const ct = today.map((d) => clock(d, TZ)), mine = local ? today.map((d) => clock(d, local)) : ct;
    const differs = local && mine.join() !== ct.join();
    // next review: today's remaining slots, else tomorrow 6 AM CT (tomorrow = CT date of now + 24h, safe across DST)
    let next = today.find((d) => d > now);
    if (!next) { const t = parts(new Date(now.getTime() + 864e5), TZ); next = zoned(+t.year, +t.month, +t.day, HOURS[0]); }
    const mins = Math.round((next - now) / 6e4), inTxt = mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins}m`;
    const sameDay = parts(next, TZ).day === c.day;
    const nextTxt = `${clock(next, TZ)} CT${sameDay ? "" : " " + tr("tomorrow")}` + (differs ? " " + tr("({t} your time)", { t: clock(next, local) }) : "") + tr(", in {d}", { d: inTxt });
    els.forEach((el) => {
      let x = el.querySelector(".sched-live");
      if (!x) { x = document.createElement("span"); x.className = "sched-live"; el.appendChild(x); }
      x.innerHTML = (differs ? `<span class="sched-local"> · ${tr("Your time:")} ${join(mine)}</span>` : "") +
        `<span class="sched-next"> · ${tr("Next review:")} <b>${nextTxt}</b></span>`;
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
  setInterval(run, 60000);
})();
