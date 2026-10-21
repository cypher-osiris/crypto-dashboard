#!/usr/bin/env python3
"""Generate an X (Twitter) post draft + 1200x675 chart card from the dashboard data.

    python3 scripts/make_post.py            # writes posts/YYYY-MM-DD-HHMM.txt + .png (Central time), prints JSON
    python3 scripts/make_post.py --no-image # text only
    python3 scripts/make_post.py --no-thread

Reads data/trades.json and data/prices.json only (no network), so every number is traceable; a built-in check
verifies that each number in the text appears in those files. Drafts are never posted automatically.
posts/ is git-ignored. Needs matplotlib for the PNG (pip install matplotlib).
"""
import json, os, re, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, POSTS = os.path.join(ROOT, "data"), os.path.join(ROOT, "posts")
SITE = "https://cypher-osiris.github.io/crypto-dashboard/"
SITE_SHORT = "cypher-osiris.github.io/crypto-dashboard"
CT = ZoneInfo("America/Chicago")
LIMIT = 280
URL_WEIGHT = 23  # X counts any URL as 23 characters
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coins as coincfg  # noqa: E402  (coin list + groups: data/coins.json)
ORDER = [c["id"] for c in coincfg.coins()]
WATCH = [c["id"] for c in coincfg.coins() if c.get("group") == "watchlist"]
MAX_PRICE_ROWS = 8


def price_ids(A, active, backdrop="bitcoin"):
    """BTC + coins on the slate + the watchlist, max 8 (keeps the card and the prices reply readable)."""
    ids = [backdrop] + [t["coin"] for t in active] + WATCH
    return [i for i in dict.fromkeys(ids) if i in A][:MAX_PRICE_ROWS]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def p(x):
    """Price formatting: plain decimal, ~4 significant digits for live prices, never scientific."""
    if x is None:
        return "—"
    x = float(x)
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 1:
        s = f"{x:.4f}"
    else:
        s = f"{x:.{max(4, 3 - int(f'{abs(x):e}'.split('e')[1]))}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def lvl(x):
    """Trade levels exactly as written in trades.json (shortest repr)."""
    s = repr(float(x))
    return s[:-2] if s.endswith(".0") else s


def pct(x, d=1):
    return ("+" if x > 0 else "−" if x < 0 else "") + f"{abs(x):.{d}f}%"


def xlen(s):
    """Length as X counts it (URLs = 23)."""
    return len(re.sub(r"https?://\S+", "x" * URL_WEIGHT, s))


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def gather():
    prices, tdoc = load("prices.json"), load("trades.json")
    A = prices["assets"]
    trades = {t["id"]: t for t in tdoc["trades"]}
    slate = tdoc.get("slate", {}).get("coins", {})
    active, nosetup = [], []
    for cid in ORDER + [c for c in slate if c not in ORDER]:
        if cid not in slate:
            continue
        tid = slate[cid].get("trade_id")
        t = trades.get(tid) if tid else None
        if t and t["status"] in ("pending", "open"):
            active.append(t)
        elif cid in A:
            nosetup.append(cid)
    closed = [t for t in tdoc["trades"] if t["status"] not in ("pending", "open")]
    closed.sort(key=lambda t: t.get("closed_at") or "")
    return prices, tdoc, A, active, nosetup, closed


def zone(t):
    z = t.get("entry_zone") or {}
    return z.get("low", t["entry"]), z.get("high", t["entry"])


def zone_txt(t):
    lo, hi = zone(t)
    return lvl(lo) if lo == hi else f"{lvl(lo)}–{lvl(hi)}"


def status_txt(t, A):
    sym = A[t["coin"]]["symbol"]
    if t["status"] == "open":
        mark = t.get("mark_price") or A[t["coin"]]["price"]
        return f"${sym} open from {lvl(t['entry'])}, mark {p(mark)}"
    return None


def build(now):
    prices, tdoc, A, active, nosetup, closed = gather()
    st = tdoc.get("stats", {})
    day = now.strftime("%b %-d")
    sym = lambda cid: A[cid]["symbol"]
    pend = [t for t in active if t["status"] == "pending"]
    opn = [t for t in active if t["status"] == "open"]

    # ---- record line (honest, includes losses) ----
    won, lost, n_closed = st.get("won", 0), st.get("lost_or_stopped", 0), st.get("closed", 0)
    rec_short = f"Closed so far: {won}W/{lost}L, {pct(st.get('cumulative_pnl_pct', 0))} on margin." if n_closed else "No closed trades yet."
    state = []
    if opn: state.append(f"{len(opn)} open")
    if pend: state.append(f"{len(pend)} waiting for entry" if opn else ("None filled yet" if len(pend) == len(active) else f"{len(pend)} pending"))
    state_txt = (", ".join(state) + ". ") if state else ""

    # ---- main post: try richest first, fall back until it fits ----
    def line(t, with_t1=True, with_stop=True):
        d = "long" if t["direction"] == "long" else "short"
        s = f"${sym(t['coin'])} {d} {zone_txt(t) if t['status'] == 'pending' else 'from ' + lvl(t['entry'])}"
        if with_stop: s += f", stop {lvl(t.get('current_stop') or t['stop'])}"
        if with_t1: s += f", T1 {lvl(t['targets'][0])}"
        return s

    head = f"Paper-trade slate, {day} (3x):" if all(int(t.get("leverage", 3)) == 3 for t in active) else f"Paper-trade slate, {day}:"
    foot = f"Paper trades, NFA\n{SITE}"
    variants = []
    if active:
        for t1, stp in ((True, True), (False, True), (False, False)):
            body = "\n".join(line(t, t1, stp) for t in active)
            variants.append(f"{head}\n{body}\n{state_txt}{rec_short}\n{foot}")
        variants.append(f"{head} " + " ".join(f"${sym(t['coin'])}" for t in active) + f" (levels on the site).\n{state_txt}{rec_short}\n{foot}")
    else:
        tags = " ".join(f"${sym(c)}" for c in nosetup[:4])
        variants.append(f"No paper-trade setups on {day} — {tags} all flat for now. {rec_short}\n{foot}")
    main = next((v for v in variants if len(v) <= LIMIT), variants[-1])

    # ---- thread ----
    thread = []
    if active:
        rows = []
        for t in active:
            tg = "/".join(lvl(x) for x in t["targets"])
            stp = lvl(t.get("current_stop") or t["stop"])
            exp = parse_ts(t.get("expiry"))
            r = f"${sym(t['coin'])} {t['direction']} {t.get('leverage', 3)}x — "
            r += (f"zone {zone_txt(t)}" if t["status"] == "pending" else f"filled {lvl(t['entry'])}") + f", stop {stp}, targets {tg}"
            if t["status"] == "pending" and (t.get("missed_it") or {}).get("max_entry") is not None:
                r += f"; skip past {lvl(t['missed_it']['max_entry'])}"
            if exp and t["status"] == "pending":
                r += f"; expires {exp.astimezone(CT).strftime('%b %-d')}"
            rows.append(r + ".")
        t1 = "Levels:\n" + "\n".join(rows)
        if len(t1) > LIMIT:  # drop expiry, then skip-limits
            t1 = "Levels:\n" + "\n".join(re.sub(r"; expires [^.;]+", "", r) for r in rows)
        if len(t1) > LIMIT:
            t1 = "Levels:\n" + "\n".join(re.sub(r"; skip past [^.;]+", "", re.sub(r"; expires [^.;]+", "", r)) for r in rows)
        thread.append(t1)
    # prices + no-setup
    pr = [f"${A[c]['symbol']} {p(A[c]['price'])} ({pct(A[c]['change_24h'])})" for c in price_ids(A, active, prices.get("backdrop", "bitcoin")) if A[c].get("price") is not None]
    pt = parse_ts(prices.get("updated_utc"))
    t2 = f"Prices ({pt.astimezone(CT).strftime('%b %-d %-I:%M %p %Z') if pt else 'snapshot'}; 24h change):\n" + "\n".join(pr)
    ns = [c for c in nosetup if c in WATCH] or nosetup
    if ns:
        t2 += "\nNo setup: " + ", ".join(f"${sym(c)}" for c in ns) + " — waiting for cleaner levels rather than forcing trades."
    if len(t2) > LIMIT:
        t2 = t2.split("\nNo setup:")[0]
    while len(t2) > LIMIT and t2.count("\n") > 2:
        t2 = t2.rsplit("\n", 1)[0]
    thread.append(t2)
    # honest record
    if closed:
        cl = []
        for t in closed[-3:]:
            d = parse_ts(t.get("closed_at"))
            res = t["status"] + (f" {pct(t['pnl_pct'])}" if t.get("pnl_pct") is not None else "")
            cl.append(f"{t['id']} ${sym(t['coin'])} {t['direction']} {t.get('leverage', '?')}x: {res}" + (f" ({d.astimezone(CT).strftime('%b %-d')})" if d else ""))
        t3 = (f"Track record (all closed trades, losses included):\n" + "\n".join(cl) +
              f"\nWin rate {st.get('win_rate_pct', 0):.0f}% ({won}/{n_closed}), cumulative {pct(st.get('cumulative_pnl_pct', 0))} on margin. Tiny sample — judge it later, not now.")
        if len(t3) > LIMIT:
            t3 = t3.replace(" Tiny sample — judge it later, not now.", "")
        thread.append(t3)
    aff = affiliate()
    if aff:  # one link per post: site URL in the main post, the affiliate link only in the last reply
        thread.append("Paper trades only, no real money, NFA. Leverage cuts both ways; stops get hit. "
                      f"If you trade crypto, Bitunix (affiliate; we may earn a commission at no cost to you): {aff}")
    else:
        thread.append(f"Paper trades only, no real money, NFA. Leverage cuts both ways; stops get hit. Live levels, signals and the full log: {SITE}")
    thread = thread[:4]
    return {"main": main, "thread": thread if len(thread) >= 2 else [], "prices": prices, "tdoc": tdoc, "A": A,
            "active": active, "nosetup": nosetup, "closed": closed}


def verify(text, prices, tdoc):
    """Every number in the text must come from prices.json / trades.json (or be a date/count/label)."""
    vals = set()
    def add(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            for s in (lvl(x), p(x), f"{abs(x):.1f}", f"{abs(x):.0f}", str(abs(x))):
                vals.add(s.replace(",", ""))
    def walk(o):
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
        else: add(o)
    for a in prices["assets"].values():
        walk({k: a.get(k) for k in ("price", "change_24h")})
    for t in tdoc["trades"]:
        walk({k: t.get(k) for k in ("entry", "stop", "current_stop", "targets", "entry_zone", "pnl_pct", "leverage", "mark_price")})
        walk((t.get("missed_it") or {}).get("max_entry"))
    walk({k: tdoc["stats"].get(k) for k in ("won", "lost_or_stopped", "closed", "win_rate_pct", "cumulative_pnl_pct")})
    t = re.sub(r"https?://\S+", "", text)
    t = re.sub(r"\b(T\d{3}|T[12])\b", "", t)                       # trade ids / target labels
    t = re.sub(r"\b\d+x\b", lambda m: m.group(0) if m.group(0)[:-1] in vals else "BADLEV", t)
    t = re.sub(r"\b[A-Z][a-z]{2} \d{1,2}\b(, \d{4})?", "", t)        # dates like Oct 21
    t = re.sub(r"\d{1,2}:\d{2} [AP]M \w+", "", t)                   # times
    t = re.sub(r"\b\d+W/\d+L\b", lambda m: "" if all(x in vals for x in re.findall(r"\d+", m.group(0))) else "BADREC", t)
    t = re.sub(r"\(\d+/\d+\)", lambda m: "" if all(x in vals for x in re.findall(r"\d+", m.group(0))) else "BADREC", t)
    t = re.sub(r"\b\d+ (open|pending|waiting)", "", t)
    t = re.sub(r"\b(24h|1h|4h|1d)\b", "", t)
    bad = ["leverage/record mismatch"] if ("BADLEV" in t or "BADREC" in t) else []
    for n in re.findall(r"\d[\d,]*\.?\d*", t):
        n = n.replace(",", "").rstrip(".")
        if n and n not in vals:
            bad.append(n)
    return bad


def find_font(prefix):
    for root, _, files in os.walk("/usr/share/fonts"):
        for fn in sorted(files):
            if fn.startswith(prefix) and fn.endswith(".ttf") and "Italic" not in fn:
                return os.path.join(root, fn)
    return None


def font_setup(fm):
    """Inter / JetBrains Mono ship as variable fonts here; matplotlib can't pick weights from those, so cut static
    Regular/Bold instances once into state/fonts (needs fontTools). Falls back to DejaVu."""
    out = {}
    cache = os.path.join(ROOT, "state", "fonts")
    for fam, prefix, fallback in (("Inter", "Inter-", "DejaVu Sans"), ("JetBrains Mono", "JetBrainsMono-", "DejaVu Sans Mono")):
        src = find_font(prefix)
        out[fam] = fallback
        if not src:
            continue
        try:
            from fontTools.ttLib import TTFont
            from fontTools.varLib import instancer
            os.makedirs(cache, exist_ok=True)
            for w, style in ((400, "Regular"), (700, "Bold")):
                dst = os.path.join(cache, f"{prefix}{style}.ttf")
                if not os.path.exists(dst):
                    f = TTFont(src)
                    axes = {a.axisTag: a.defaultValue for a in f["fvar"].axes} if "fvar" in f else {}
                    if "wght" in axes:
                        axes["wght"] = w
                    inst = instancer.instantiateVariableFont(f, axes) if axes else f
                    inst["OS/2"].usWeightClass = w
                    if style == "Bold":
                        inst["OS/2"].fsSelection = (inst["OS/2"].fsSelection | 0x20) & ~0x40
                        inst["head"].macStyle |= 1
                    for rec in inst["name"].names:
                        if rec.nameID in (1, 16):
                            rec.string = fam
                        elif rec.nameID in (2, 17):
                            rec.string = style
                    inst.save(dst)
                fm.fontManager.addfont(dst)
            out[fam] = fam
        except Exception:
            try:
                fm.fontManager.addfont(src); out[fam] = fam
            except Exception:
                pass
    return out["Inter"], out["JetBrains Mono"]


def affiliate():
    try:
        a = load("config.json").get("affiliate", {})
    except Exception:
        return None
    u = (a.get("bitunix_url") or "").strip()
    return u if u.startswith("https://") else None


def card(path, d, now):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.patches import FancyBboxPatch, Rectangle
    sans, mono = font_setup(fm)
    BG, PANEL, LINE, TXT, MUTED, DIM = "#070b12", "#0d1420", "#1c2636", "#e6edf6", "#9aa7b8", "#64748b"
    GREEN, RED, CYAN, AMBER, VIOLET = "#22c55e", "#f43f5e", "#22d3ee", "#f5b041", "#a78bfa"
    A, active = d["A"], d["active"]
    fig = plt.figure(figsize=(12, 6.75), dpi=100, facecolor=BG)
    W, H = 1200, 675
    def T(x, y, s, **k):
        k.setdefault("color", TXT); k.setdefault("family", sans)
        fig.text(x / W, 1 - y / H, s, **k)
    # background glow
    g = fig.add_axes([0, 0, 1, 1]); g.axis("off"); g.set_xlim(0, 1); g.set_ylim(0, 1)
    import numpy as np
    yy, xx = np.mgrid[0:1:200j, 0:1:300j]
    glow = np.exp(-((xx - 0.1) ** 2 / 0.08 + (yy - 1.0) ** 2 / 0.12)) * 0.35 + np.exp(-((xx - 0.95) ** 2 / 0.05 + (yy - 0.0) ** 2 / 0.1)) * 0.2
    g.imshow(glow, extent=(0, 1, 0, 1), origin="lower", cmap=matplotlib.colors.LinearSegmentedColormap.from_list("g", [BG, "#0e2a3a"]), aspect="auto", zorder=0)
    g.set_xlim(0, W); g.set_ylim(H, 0)
    for im in g.images: im.set_extent((0, W, H, 0))
    def box(x, y, w, h):  # pixel coordinates, true rounded corners
        g.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=12", fc=PANEL, ec=LINE, lw=1, zorder=1))
    # header
    T(40, 46, "Crypto Dashboard", fontsize=24, weight="bold", va="center")
    T(40, 78, f"Paper-trade slate · {now.strftime('%b %-d, %Y · %-I:%M %p %Z')}", fontsize=12.5, color=MUTED, va="center")
    T(1160, 46, "PAPER TRADES · NFA", fontsize=11, color=AMBER, ha="right", va="center", weight="bold",
      bbox=dict(boxstyle="round,pad=0.45", fc="#2a1f0a", ec=AMBER, lw=0.8))
    _pt = parse_ts(d["prices"].get("updated_utc"))
    T(1160, 78, f"prices as of {_pt.astimezone(CT).strftime('%b %-d, %-I:%M %p %Z') if _pt else '—'}", fontsize=10, color=DIM, ha="right", va="center")
    # slate rows
    top, gap = 108, 12
    n = max(1, min(5, len(active)))
    row_h = min(145, (560 - top - gap * (n - 1)) / n)
    for i, t in enumerate(active[:5]):
        y0 = top + i * (row_h + gap)
        box(40, y0, 760, row_h)
        a = A[t["coin"]]; long_ = t["direction"] == "long"
        mid = y0 + row_h / 2
        T(62, mid - 22, a["symbol"], fontsize=18, weight="bold", va="center")
        T(62, mid + 4, f"{'LONG' if long_ else 'SHORT'} {t.get('leverage', 3)}x", fontsize=11, weight="bold", va="center",
          color=GREEN if long_ else RED, family=mono)
        T(62, mid + 24, f"{t['id']} · {t['status']}", fontsize=9, color=DIM, va="center", family=mono)
        # ladder
        lo, hi = zone(t); stop = t.get("current_stop") or t["stop"]; tg = t["targets"]; px = a["price"]
        pts = [lo, hi, stop, px] + list(tg)
        mn, mx = min(pts), max(pts); pad = (mx - mn) * 0.07 or mx * 0.01
        ax = fig.add_axes([215 / W, 1 - (mid + 26) / H, 555 / W, 52 / H]); ax.axis("off")
        ax.set_xlim(mn - pad, mx + pad); ax.set_ylim(0, 1)
        ax.plot([mn - pad * 0.5, mx + pad * 0.5], [0.42, 0.42], color=LINE, lw=2, solid_capstyle="round")
        ax.add_patch(Rectangle((lo, 0.27), max(hi - lo, (mx - mn) * 0.006), 0.30, color=CYAN, alpha=0.35, lw=0))
        ax.plot([lo, lo], [0.27, 0.57], color=CYAN, lw=1); ax.plot([hi, hi], [0.27, 0.57], color=CYAN, lw=1)
        ax.plot([stop], [0.42], marker="|", ms=16, mew=2.4, color=RED)
        for x in tg:
            ax.plot([x], [0.42], marker="|", ms=16, mew=2.4, color=GREEN)
        ax.plot([px], [0.42], marker="o", ms=7.5, color=TXT, mec=BG, mew=1.5, zorder=5)
        lab = lambda x, s, c, yy, ha="center": ax.text(x, yy, s, color=c, fontsize=8.6, ha=ha, va="center", family=mono)
        lab((lo + hi) / 2, f"zone {zone_txt(t)}", CYAN, 0.92)
        lab(stop, f"stop {lvl(stop)}", RED, -0.08)
        for k, x in enumerate(tg):
            lab(x, f"T{k + 1} {lvl(x)}", GREEN, -0.08 if k % 2 == 0 else 0.92)
        lab(px, f"now {p(px)}", TXT, 0.92 if abs(px - (lo + hi) / 2) > (mx - mn) * 0.25 else -0.08)
        ax.set_clip_on(False)
        for txt in ax.texts: txt.set_clip_on(False)
    if not active:
        T(420, 260, "No active setups right now", fontsize=18, color=MUTED, ha="center")
    # right panel: prices
    px0 = 830
    box(px0, 108, 330, 452)
    T(px0 + 20, 132, "PRICES · 24H", fontsize=10, color=DIM, weight="bold", va="center")
    order = price_ids(A, active, d["prices"].get("backdrop", "bitcoin"))
    step = 34 if len(order) <= 6 else 28
    for j, cid in enumerate(order):
        a = A[cid]; yy = 168 + j * step
        T(px0 + 20, yy, a["symbol"], fontsize=12.5, weight="bold", va="center")
        T(px0 + 205, yy, p(a["price"]), fontsize=12, va="center", ha="right", family=mono)
        ch = a.get("change_24h") or 0
        T(px0 + 310, yy, pct(ch), fontsize=11, va="center", ha="right", family=mono, color=GREEN if ch > 0 else RED if ch < 0 else MUTED)
    st = d["tdoc"].get("stats", {})
    yy = 168 + len(order) * step + 6
    fig.add_artist(matplotlib.lines.Line2D([(px0 + 20) / W, (px0 + 310) / W], [1 - yy / H] * 2, color=LINE, lw=1))
    T(px0 + 20, yy + 24, "TRACK RECORD (CLOSED)", fontsize=10, color=DIM, weight="bold", va="center")
    if st.get("closed"):
        cum = st.get("cumulative_pnl_pct", 0)
        T(px0 + 20, yy + 52, f"{st.get('won', 0)}W / {st.get('lost_or_stopped', 0)}L", fontsize=14, weight="bold", va="center", family=mono)
        T(px0 + 310, yy + 52, f"{pct(cum)}", fontsize=14, weight="bold", va="center", ha="right", family=mono, color=GREEN if cum > 0 else RED if cum < 0 else MUTED)
        T(px0 + 20, yy + 76, "sum of % on margin · losses included", fontsize=9, color=DIM, va="center")
    else:
        T(px0 + 20, yy + 52, "no closed trades yet", fontsize=12, color=MUTED, va="center")
    ns = [A[c]["symbol"] for c in d["nosetup"]]
    if ns:
        line1 = "No setup: " + ", ".join(ns[:6]); line2 = ", ".join(ns[6:])
        T(px0 + 20, yy + 100, line1 + ("," if line2 else ""), fontsize=10, color=MUTED, va="center")
        if line2: T(px0 + 20, yy + 118, line2, fontsize=10, color=MUTED, va="center")
    # footer
    fig.add_artist(matplotlib.lines.Line2D([40 / W, 1160 / W], [1 - 600 / H] * 2, color=LINE, lw=1))
    T(40, 630, SITE_SHORT, fontsize=13, color=CYAN, va="center", weight="bold")
    lx = 560
    for s, c in (("■ entry zone", CYAN), ("| stop", RED), ("| targets", GREEN), ("● now", TXT)):
        T(lx, 630, s, fontsize=10, color=c, va="center"); lx += 26 + 8.2 * len(s)
    T(1160, 630, "Paper trades, not financial advice", fontsize=10, color=DIM, va="center", ha="right")
    fig.savefig(path, dpi=100, facecolor=BG)
    plt.close(fig)


def main():
    args = sys.argv[1:]
    now = datetime.now(timezone.utc).astimezone(CT)
    d = build(now)
    os.makedirs(POSTS, exist_ok=True)
    stem = now.strftime("%Y-%m-%d-%H%M")
    txt_path, png_path = os.path.join(POSTS, stem + ".txt"), os.path.join(POSTS, stem + ".png")
    thread = [] if "--no-thread" in args else d["thread"]
    parts = [d["main"]] + thread
    problems = []
    for i, s in enumerate(parts):
        if len(s) > LIMIT:
            problems.append(f"post {i + 1} is {len(s)} chars (> {LIMIT})")
        bad = verify(s, d["prices"], d["tdoc"])
        if bad:
            problems.append(f"post {i + 1}: numbers not found in data: {bad}")
    out = [f"=== MAIN POST ({len(d['main'])} chars; {xlen(d['main'])} as counted by X) ===", d["main"], ""]
    if thread:
        out.append(f"=== OPTIONAL THREAD ({len(thread)} replies) ===")
        for i, s in enumerate(thread):
            out += [f"--- reply {i + 1}/{len(thread)} ({len(s)} chars; {xlen(s)} on X) ---", s, ""]
    out += ["=== NOTES (not for posting) ===",
            f"generated {now.strftime('%Y-%m-%d %H:%M %Z')} from data/trades.json (slate as of {d['tdoc'].get('slate', {}).get('as_of')}, tracked {d['tdoc'].get('tracked_utc')}) and data/prices.json ({d['prices'].get('updated_utc')})",
            f"image: {png_path if '--no-image' not in args else '(skipped)'}",
            "number check: " + ("OK — every number appears in trades.json/prices.json" if not problems else "; ".join(problems)),
            "Draft only — review before posting. Prices in the post are a snapshot; re-run right before posting."]
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    img = None
    if "--no-image" not in args:
        card(png_path, d, now); img = png_path
    print(json.dumps({"text": txt_path, "image": img, "main_chars": len(d["main"]), "thread": len(thread),
                      "problems": problems}, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
