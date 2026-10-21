/* Global Markets panel: live session clocks + 24h timeline (US Central axis).
   All conversions use Intl + IANA zones, so DST is automatic. Exchange holidays are NOT handled. */
(() => {
  "use strict";
  const LOCAL_TZ = "America/Chicago";
  const H = 36e5, M = 6e4, D = 864e5;
  const MARKETS = [
    { id: "tyo", region: "Asia", city: "Tokyo", short: "Tokyo", exch: "TSE", tz: "Asia/Tokyo", sessions: [["09:00", "11:30"], ["12:30", "15:30"]] },
    { id: "hkg", region: "Asia", city: "Hong Kong", short: "HK", exch: "HKEX", tz: "Asia/Hong_Kong", sessions: [["09:30", "12:00"], ["13:00", "16:00"]] },
    { id: "lon", region: "Europe", city: "London", short: "London", exch: "LSE", tz: "Europe/London", sessions: [["08:00", "16:30"]] },
    { id: "nyc", region: "US", city: "New York", short: "NY", exch: "NYSE", tz: "America/New_York", sessions: [["09:30", "16:00"]] },
  ];
  const OVERLAPS = [
    { a: ["tyo", "hkg"], b: ["lon"], label: "Asia × Europe" },
    { a: ["lon"], b: ["nyc"], label: "London × New York", key: true },
  ];
  const $ = (id) => document.getElementById(id);

  const fmtCache = {};
  function partsFmt(tz) {
    return (fmtCache[tz] ||= new Intl.DateTimeFormat("en-US", {
      timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", weekday: "short",
    }));
  }
  function zparts(ms, tz) {
    const o = {};
    for (const p of partsFmt(tz).formatToParts(ms)) o[p.type] = p.value;
    return { y: +o.year, mo: +o.month, d: +o.day, h: +o.hour % 24, mi: +o.minute, s: +o.second, wd: o.weekday };
  }
  const offset = (ms, tz) => { const p = zparts(ms, tz); return Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi, p.s) - Math.floor(ms / 1000) * 1000; };
  function zonedToUtc(y, mo, d, h, mi, tz) {
    const guess = Date.UTC(y, mo - 1, d, h, mi);
    let t = guess - offset(guess, tz);
    const o2 = offset(t, tz);
    if (guess - o2 !== t) t = guess - o2;
    return t;
  }
  const hm = (s) => s.split(":").map(Number);

  // Session intervals [open, close] (UTC ms) for market-local dates from -1 to +7 days, weekends skipped.
  function intervals(mkt, now) {
    const p = zparts(now, mkt.tz);
    const out = [];
    for (let k = -1; k <= 7; k++) {
      const base = new Date(Date.UTC(p.y, p.mo - 1, p.d + k));
      const dow = base.getUTCDay();
      if (dow === 0 || dow === 6) continue;
      const [y, mo, d] = [base.getUTCFullYear(), base.getUTCMonth() + 1, base.getUTCDate()];
      mkt.sessions.forEach(([a, b], i) => {
        const [ah, am] = hm(a), [bh, bm] = hm(b);
        out.push({ open: zonedToUtc(y, mo, d, ah, am, mkt.tz), close: zonedToUtc(y, mo, d, bh, bm, mkt.tz), idx: i, day: y * 1e4 + mo * 100 + d });
      });
    }
    return out.sort((x, y) => x.open - y.open);
  }

  function status(mkt, now) {
    const iv = intervals(mkt, now);
    const cur = iv.find((s) => now >= s.open && now < s.close);
    if (cur) {
      const isMorning = mkt.sessions.length > 1 && cur.idx < mkt.sessions.length - 1;
      return { state: "open", label: "Open", next: cur.close, nextLabel: isMorning ? "Lunch in" : "Closes in" };
    }
    const nxt = iv.find((s) => s.open > now);
    const prev = [...iv].reverse().find((s) => s.close <= now);
    if (prev && nxt && prev.day === nxt.day) return { state: "lunch", label: "Lunch", next: nxt.open, nextLabel: "Reopens in" };
    const wk = ["Sat", "Sun"].includes(zparts(now, mkt.tz).wd);
    return { state: "closed", label: wk ? "Weekend" : "Closed", next: nxt.open, nextLabel: "Opens in" };
  }

  function dur(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return (d ? `${d}d ` : "") + `${pad(h)}:${pad(m)}:${pad(sec)}`;
  }
  const clock = (now, tz) => new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).format(now);
  const dayLabel = (now, tz) => new Intl.DateTimeFormat("en-US", { timeZone: tz, weekday: "short", month: "short", day: "numeric" }).format(now);
  const tzAbbr = (now, tz) => (new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "short" }).formatToParts(now).find((p) => p.type === "timeZoneName") || {}).value || "";
  const localHM = (ms) => new Intl.DateTimeFormat("en-US", { timeZone: LOCAL_TZ, hour: "numeric", minute: "2-digit" }).format(ms);

  function build() {
    const grid = $("mkt-clocks");
    if (!grid) return false;
    const local = `<div class="clock clock-local">
        <div class="clock-top"><span class="region">Your time</span><span class="badge b-local">Central</span></div>
        <div class="clock-city">Central (CT)</div>
        <div class="clock-time mono" id="clk-local">--:--:--</div>
        <div class="clock-sub" id="clk-local-sub"></div></div>`;
    grid.innerHTML = local + MARKETS.map((m) => `
      <div class="clock" id="clk-${m.id}">
        <div class="clock-top"><span class="region">${m.region}</span><span class="badge" data-badge>—</span></div>
        <div class="clock-city">${m.city} <small>${m.exch}</small></div>
        <div class="clock-time mono" data-time>--:--:--</div>
        <div class="clock-sub"><span data-next></span> <b class="mono" data-cd></b></div>
        <div class="clock-hours">${m.sessions.map((s) => s.join("–")).join(" · ")} local</div>
      </div>`).join("");
    return true;
  }

  // 24h timeline on the Central-time day that contains `now`.
  function timeline(now) {
    const p = zparts(now, LOCAL_TZ);
    const d0 = zonedToUtc(p.y, p.mo, p.d, 0, 0, LOCAL_TZ);
    const nx = new Date(Date.UTC(p.y, p.mo - 1, p.d + 1));
    const d1 = zonedToUtc(nx.getUTCFullYear(), nx.getUTCMonth() + 1, nx.getUTCDate(), 0, 0, LOCAL_TZ);
    const span = d1 - d0; // 23/24/25h on DST days
    const pctX = (t) => ((Math.min(Math.max(t, d0), d1) - d0) / span) * 100;
    const clip = (s) => (s.close > d0 && s.open < d1 ? [Math.max(s.open, d0), Math.min(s.close, d1)] : null);
    const segs = {};
    for (const m of MARKETS) segs[m.id] = intervals(m, now).map(clip).filter(Boolean);

    const union = (ids) => ids.flatMap((id) => segs[id]);
    const ovl = [];
    for (const o of OVERLAPS) for (const [a0, a1] of union(o.a)) for (const [b0, b1] of union(o.b)) {
      const s = Math.max(a0, b0), e = Math.min(a1, b1);
      if (e > s) ovl.push({ s, e, label: o.label, key: o.key });
    }
    const bar = (s, e, cls, title) => `<span class="seg ${cls}" style="left:${pctX(s).toFixed(3)}%;width:${(pctX(e) - pctX(s)).toFixed(3)}%" title="${title}"></span>`;
    const ticks = [0, 3, 6, 9, 12, 15, 18, 21].map((hh) => {
      const t = d0 + hh * H;
      return `<span class="tick${hh % 6 ? " minor" : ""}" style="left:${pctX(t)}%">${hh === 0 ? "12a" : hh < 12 ? hh + "a" : hh === 12 ? "12p" : hh - 12 + "p"}</span>`;
    }).join("");
    const rows = MARKETS.map((m) => `
      <div class="tl-row"><div class="tl-label"><span class="full">${m.city}</span><span class="short">${m.short}</span></div><div class="tl-track">
        ${segs[m.id].map(([s, e]) => bar(s, e, "r-" + m.region.toLowerCase(), `${m.city} ${localHM(s)}–${localHM(e)} CT`)).join("")}
      </div></div>`).join("");
    const bands = ovl.map((o) => `<span class="band${o.key ? " key" : ""}" style="left:${pctX(o.s)}%;width:${pctX(o.e) - pctX(o.s)}%" title="${o.label} ${localHM(o.s)}–${localHM(o.e)} CT"></span>`).join("");
    const ovlRow = `<div class="tl-row"><div class="tl-label">Overlap</div><div class="tl-track">
        ${ovl.map((o) => bar(o.s, o.e, "r-ovl" + (o.key ? " key" : ""), o.label)).join("")}</div></div>`;
    $("mkt-timeline").innerHTML = `
      <div class="tl-axis"><div class="tl-label"></div><div class="tl-track ticks">${ticks}</div></div>
      <div class="tl-body">${bands ? `<div class="tl-bands">${bands}</div>` : ""}${rows}${ovlRow}
        <div class="tl-now" style="left:calc(var(--tl-label) + (100% - var(--tl-label)) * ${pctX(now) / 100})"><span>${localHM(now)}</span></div>
      </div>`;
    const key = ovl.filter((o) => o.key);
    $("mkt-overlap").innerHTML = key.length
      ? `London × New York overlap today: <b class="mono">${key.map((o) => `${localHM(o.s)}–${localHM(o.e)}`).join(", ")} CT</b> — typically the heaviest hours for crypto volume.`
      : `No London × New York overlap today (weekend) — expect thinner liquidity.`;
  }

  let lastMinute = -1;
  function tick() {
    const now = Date.now();
    $("clk-local").textContent = clock(now, LOCAL_TZ);
    $("clk-local-sub").textContent = `${dayLabel(now, LOCAL_TZ)} · ${tzAbbr(now, LOCAL_TZ)}`;
    let openCount = 0;
    for (const m of MARKETS) {
      const el = $("clk-" + m.id);
      const st = status(m, now);
      if (st.state === "open") openCount++;
      el.dataset.state = st.state;
      el.querySelector("[data-time]").textContent = clock(now, m.tz);
      const b = el.querySelector("[data-badge]");
      b.textContent = st.label; b.className = "badge b-" + st.state;
      el.querySelector("[data-next]").textContent = st.nextLabel;
      el.querySelector("[data-cd]").textContent = dur(st.next - now);
      el.title = `${dayLabel(now, m.tz)} ${tzAbbr(now, m.tz)}`;
    }
    const pill = $("mkt-pill");
    if (pill) pill.textContent = openCount ? `${openCount} of ${MARKETS.length} exchanges open` : "All tracked exchanges closed";
    const minute = Math.floor(now / M);
    if (minute !== lastMinute) { lastMinute = minute; timeline(now); }
  }

  function start() {
    if (!build()) return;
    tick();
    setInterval(tick, 1000);
  }
  window.Markets = { status, intervals, zonedToUtc, MARKETS }; // exposed for testing
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
