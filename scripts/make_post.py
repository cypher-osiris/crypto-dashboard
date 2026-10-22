#!/usr/bin/env python3
"""Post helper for the Lumi Trades X account. It supplies facts and pictures; the post TEXT is written by a human
or agent following docs/x_voice.md.

    python3 scripts/make_post.py                 # = facts: compact JSON of what's worth posting (stdout)
    python3 scripts/make_post.py facts --pretty
    python3 scripts/make_post.py card [--focus slate|XRP|ripple] [--out file.png]
    python3 scripts/make_post.py check post.txt  # every number in the text must match the data files (exit 1 if not)
    python3 scripts/make_post.py save post.txt [--focus ...] [--kind morning|midday|evening|event|news|weekly]
        -> posts/YYYY-MM-DD-HHMM.txt + .png (Central time), runs check, records the "last post" baseline

Reads data/{trades,prices,analysis,signals,context,coins,config}.json and data/log.json; no network.
"what changed" is measured against the baseline saved by the previous `save` (posts/.last_post.json).
posts/ is git-ignored. The card needs matplotlib (+ fontTools for bold Inter / JetBrains Mono).
"""
import argparse, json, os, re, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, POSTS = os.path.join(ROOT, "data"), os.path.join(ROOT, "posts")
BASELINE = os.path.join(POSTS, ".last_post.json")
SITE = "https://lumitrades.io/"
SITE_SHORT = "lumitrades.io"
BRAND = "Lumi Trades"
CT = ZoneInfo("America/Chicago")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coins as coincfg  # noqa: E402


def load(name, default=None):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def ctfmt(d, f="%a %b %-d, %-I:%M %p %Z"):
    return d.astimezone(CT).strftime(f) if d else None


def sig(x, n=4):
    return None if x is None else float(f"{x:.{n}g}")


def lvl(x):
    s = repr(float(x)); return s[:-2] if s.endswith(".0") else s


def zone(t):
    z = t.get("entry_zone") or {}
    return z.get("low", t["entry"]), z.get("high", t["entry"])


def affiliate():
    a = (load("config.json", {}) or {}).get("affiliate", {})
    u = (a.get("bitunix_url") or "").strip()
    return u if u.startswith("https://") else None


# ---------------------------------------------------------------------------------------------- facts
def missed_plan_facts(t, now_p):
    """Compact view of a trade's missed_plan for writing posts (None if absent)."""
    p = t.get("missed_plan")
    if not p:
        return None
    if p.get("type") == "none":
        return {"type": "none", "status": "no chase", "why": (p.get("reasoning") or "")[:220]}
    z = p.get("entry_zone") or {}
    lo, hi = z.get("low"), z.get("high")
    d = p.get("direction") or ({"long": "short", "short": "long"}[t["direction"]] if p.get("type") == "flip" else t["direction"])
    out = {"type": p.get("type"), "status": p.get("status", "watching"), "trigger": p.get("trigger"), "zone": [lo, hi],
           "stop": p.get("stop"), "target": p.get("target"), "lev": p.get("leverage") or t.get("leverage"), "size_note": p.get("size_note")}
    if None not in (lo, hi, p.get("stop"), p.get("target")):
        worst, best = (hi, lo) if d == "long" else (lo, hi)
        f = lambda e: round(abs(p["target"] - e) / abs(e - p["stop"]), 2)  # noqa: E731
        out["rr_worst_best"] = [f(worst), f(best)]
        if now_p is not None and out["status"] in ("watching", "armed"):
            out["now_vs_plan_zone"] = "in plan zone" if lo <= now_p <= hi else (
                f"{(now_p / hi - 1) * 100:.1f}% above plan zone" if now_p > hi else f"{(1 - now_p / lo) * 100:.1f}% below plan zone")
    if p.get("linked_id"):
        out["linked_id"] = p["linked_id"]
    return out


def gather(now=None):
    now = now or datetime.now(timezone.utc)
    P, TD = load("prices.json"), load("trades.json")
    AN, SG, CX, LOG = load("analysis.json", {}), load("signals.json", {}), load("context.json", {}), load("log.json", {"entries": []})
    A = P["assets"]; cfg = coincfg.coins(); sym = {c["id"]: c["symbol"] for c in cfg}
    sym.update({k: v["symbol"] for k, v in A.items()})
    watch = [c["id"] for c in cfg if c.get("group") == "watchlist"]
    trades = {t["id"]: t for t in TD["trades"]}
    slate_map = (TD.get("slate") or {}).get("coins", {})
    base = None
    if os.path.exists(BASELINE):
        try: base = json.load(open(BASELINE))
        except ValueError: base = None

    # slate
    slate, no_setup = [], []
    for cid in [c["id"] for c in cfg]:
        e = slate_map.get(cid) or {}
        t = trades.get(e.get("trade_id")) if e.get("trade_id") else None
        if not t or t["status"] not in ("pending", "open"):
            if cid in A: no_setup.append({"sym": sym[cid], "watchlist": cid in watch, "why": (e.get("note") or "")[:160]})
            continue
        lo, hi = zone(t); now_p = A[t["coin"]]["price"]; long_ = t["direction"] == "long"
        row = {"id": t["id"], "sym": sym[t["coin"]], "coin": t["coin"], "side": t["direction"], "lev": t.get("leverage"), "conviction": t.get("conviction"), "leverage_reason": t.get("leverage_reason"), "status": t["status"],
               "zone": [lo, hi], "stop": t.get("current_stop") or t["stop"], "targets": t["targets"], "now": now_p,
               "missed_it_max": (t.get("missed_it") or {}).get("max_entry"), "expires": ctfmt(ts(t.get("expiry")))}
        if t["status"] == "pending":
            if lo <= now_p <= hi: row["vs_zone"] = "in zone"
            elif now_p > hi: row["vs_zone"] = f"{(now_p / hi - 1) * 100:.1f}% above zone"
            else: row["vs_zone"] = f"{(1 - now_p / lo) * 100:.1f}% below zone"
            mx = row["missed_it_max"]
            if mx is not None:
                row["past_missed_it"] = (now_p > mx) if long_ else (now_p < mx)
        else:
            row["entry"] = t["entry"]; row["unrealized_pct"] = t.get("unrealized_pnl_pct")
        if t.get("parent_id"):
            row["missed_plan_of"] = t["parent_id"]; row["plan_type"] = t.get("plan_type"); row["size_note"] = t.get("size_note")
        mp = missed_plan_facts(t, now_p)
        if mp:
            row["missed_plan"] = mp
        slate.append(row)

    # trade events (from trades.json timestamps) since the baseline / last 24h
    since = ts(base["at"]) if base else now - timedelta(hours=24)
    events = []
    for t in TD["trades"]:
        s_ = sym.get(t["coin"], t["coin"])
        if t.get("filled_at") and ts(t["filled_at"]) > since:
            events.append({"at": ctfmt(ts(t["filled_at"])), "id": t["id"], "sym": s_, "type": "filled", "price": t["entry"], "side": t["direction"]})
        for k, h in enumerate(t.get("targets_hit") or []):
            if h.get("at") and ts(h["at"]) > since:
                events.append({"at": ctfmt(ts(h["at"])), "id": t["id"], "sym": s_, "type": f"T{k + 1} hit", "price": h["price"]})
        if t.get("closed_at") and ts(t["closed_at"]) > since and t["status"] not in ("pending", "open"):
            ev = {"at": ctfmt(ts(t["closed_at"])), "id": t["id"], "sym": s_, "type": t["status"], "price": t.get("exit_price"), "pnl_pct": t.get("pnl_pct")}
            if t.get("cancel_reason"): ev["reason"] = t["cancel_reason"]
            events.append(ev)
        mp = t.get("missed_plan") or {}
        for k, typ in (("armed_at", "missed_plan armed"), ("triggered_at", "missed_plan triggered"), ("ended_at", f"missed_plan {mp.get('status')}")):
            if mp.get(k) and ts(mp[k]) > since:
                ev = {"at": ctfmt(ts(mp[k])), "id": t["id"], "sym": s_, "type": typ, "plan": mp.get("type"), "trigger": mp.get("trigger")}
                if k == "triggered_at": ev["linked_id"] = mp.get("linked_id")
                events.append(ev)
    # new ideas since baseline
    new_ideas = [r["id"] for r in slate if base and r["id"] not in base.get("slate_ids", [])]

    # movers
    ch = sorted([(v.get("change_24h") or 0, k) for k, v in A.items()], reverse=True)
    mv = lambda k: {"sym": sym[k], "price": sig(A[k]["price"]), "pct_24h": round(A[k]["change_24h"] or 0, 1)}
    movers = {"up": [mv(k) for c, k in ch[:3] if c > 0], "down": [mv(k) for c, k in ch[::-1][:2] if c < 0]}
    since_moves = None
    if base:
        d = [((A[k]["price"] / p - 1) * 100, k) for k, p in base.get("prices", {}).items() if k in A and p]
        d.sort(key=lambda x: -abs(x[0]))
        since_moves = [{"sym": sym[k], "from": sig(base["prices"][k]), "to": sig(A[k]["price"]), "pct": round(x, 1)} for x, k in d[:3]]

    # record
    st = TD.get("stats", {})
    closed = sorted([t for t in TD["trades"] if t["status"] not in ("pending", "open", "cancelled")], key=lambda t: t.get("closed_at") or "")
    last = closed[-1] if closed else None
    record = {"closed": st.get("closed", 0), "won": st.get("won", 0), "lost": st.get("lost_or_stopped", 0),
              "win_rate_pct": st.get("win_rate_pct"), "cum_pnl_pct": st.get("cumulative_pnl_pct"),
              "last_closed": {"id": last["id"], "sym": sym.get(last["coin"]), "side": last["direction"], "lev": last.get("leverage"),
                              "status": last["status"], "pnl_pct": last.get("pnl_pct"), "closed": ctfmt(ts(last.get("closed_at")), "%b %-d")} if last else None}

    # news: freshest 1-2 catalysts (news <= 2 days old, events within the next 10 days), watchlist + BTC first
    cats = []
    for cid, blk in [("bitcoin", AN.get("backdrop", {}))] + list((AN.get("coins") or {}).items()):
        if cid == "bitcoin" and blk is not AN.get("backdrop"):
            continue
        for c in blk.get("catalysts") or []:
            d = datetime.fromisoformat(c["date"]).replace(tzinfo=CT)
            age = (now.astimezone(CT) - d).days
            if (c.get("kind") == "news" and 0 <= age <= 2) or (c.get("kind") == "event" and -10 <= age <= 0):
                prio = (0 if cid in watch or cid == "bitcoin" else 1, abs(age))
                cats.append((prio, {"sym": sym.get(cid, cid), "date": c["date"], "kind": c.get("kind"), "text": c["text"], "source": c.get("source"), "url": c.get("url")}))
    cats.sort(key=lambda x: x[0])
    news = [c for _, c in cats[:2]]

    # signals: strongest / weakest composite
    sc = [(v.get("score"), k) for k, v in (SG.get("coins") or {}).items() if v.get("score") is not None]
    sc.sort()
    sigs = {"strongest": {"sym": sym.get(sc[-1][1]), "label": SG["coins"][sc[-1][1]]["label"], "score": round(sc[-1][0], 2)},
            "weakest": {"sym": sym.get(sc[0][1]), "label": SG["coins"][sc[0][1]]["label"], "score": round(sc[0][0], 2)}} if sc else None

    btc = A.get("bitcoin", {}); bd = AN.get("backdrop", {})
    fg = (CX or {}).get("fear_greed") or {}
    return {
        "now": ctfmt(now), "data_as_of": {"prices": ctfmt(ts(P.get("updated_utc"))), "slate": ctfmt(ts((TD.get("slate") or {}).get("as_of"))),
                                           "tracked": ctfmt(ts(TD.get("tracked_utc"))), "analysis": ctfmt(ts(AN.get("as_of")))},
        "last_post": ctfmt(ts(base["at"])) if base else None,
        "since_last_post": {"trade_events": events, "new_ideas": new_ideas, "biggest_moves": since_moves} if base else None,
        "trade_events_24h" if not base else "trade_events": events,
        "slate": slate, "no_setup": [n["sym"] for n in no_setup], "no_setup_notes_watchlist": [n for n in no_setup if n["watchlist"]],
        "btc": {"price": sig(btc.get("price"), 5), "pct_24h": round(btc.get("change_24h") or 0, 1), "support": bd.get("support"), "resistance": bd.get("resistance")},
        "movers_24h": movers, "record": record, "news": news, "signals": sigs,
        "sentiment": {"fear_greed": fg.get("value"), "label": fg.get("classification"), "prev": fg.get("previous")} if fg else None,
        "links": {"site": SITE, "affiliate": affiliate()},
        "post_kinds": ["morning", "midday", "evening", "event", "news", "weekly", "missed"],
        "voice": "docs/x_voice.md",
    }


# ---------------------------------------------------------------------------------------------- number check
NUM = re.compile(r"(?<![\w.])[$]?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s?([kK]))?(%)?")


def allowed_values():
    vals = []
    def walk(o):
        if isinstance(o, bool) or o is None: return
        if isinstance(o, (int, float)): vals.append(float(o)); return
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
        elif isinstance(o, str):
            for m in NUM.finditer(o):
                v = float(m.group(1).replace(",", "")); vals.append(v * (1000 if m.group(2) else 1))
    P = load("prices.json")
    for a in P["assets"].values():
        walk({k: a.get(k) for k in ("price", "change_24h", "change_7d", "change_30d", "high_24h", "low_24h", "market_cap_rank")})
        h = [p for _, p in a.get("history", [])]
        if h: walk([min(h), max(h), min(h[-168:]), max(h[-168:])])
    TD = load("trades.json"); walk(TD["trades"]); walk(TD.get("stats", {}))
    AN = load("analysis.json", {}); walk(AN.get("backdrop", {})); walk(AN.get("coins", {}))
    walk(load("context.json", {})); walk(gather())
    return vals


def check_text(text):
    """Each number must equal a data value at the precision written (e.g. '84.7K' ok for 84657; '1.39' for 1.3904)."""
    t = re.sub(r"https?://\S+", " ", text)
    t = re.sub(r"\b(T\d{3}[a-z]?|T[12])\b", " ", t)                                   # trade ids / T1 T2
    t = re.sub(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w* \d{1,2}(\s?[-–]\s?\d{1,2})?\b", " ", t)
    t = re.sub(r"\b\d{1,2}(:\d{2})?\s?(am|pm|AM|PM)\b|\b\d{1,2}:\d{2}\b", " ", t)  # times
    t = re.sub(r"\b\d+(h|d|w)\b|\b\d+-day\b|\b\d+x\b|\b20\d\d\b|\b\d+/\d+\b", " ", t)  # timeframes, leverage, years, x/y counts
    vals = allowed_values(); res = []
    for m in NUM.finditer(t):
        raw = m.group(0).strip(); s = m.group(1).replace(",", "")
        v = float(s) * (1000 if m.group(2) else 1)
        dec = len(s.split(".")[1]) if "." in s else 0
        unit = (10 ** -dec) * (1000 if m.group(2) else 1)
        if not m.group(2) and dec == 0 and v >= 1000:      # "85,000" style round numbers: allow rounding to the last non-zero digit
            unit = 10 ** (len(s) - len(s.rstrip("0")))
        tol = unit / 2 + 1e-12
        ok = any(abs(abs(x) - v) <= tol for x in vals)
        if not ok and v < 10 and dec == 0 and not m.group(3):  # small bare integers (counts like "3 ideas")
            ok = True
        res.append((raw, ok))
    return [r for r, ok in res if not ok], len(res)

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




# ---------------------------------------------------------------------------------------------- card
BG, PANEL, LINE, TXT, MUTED, DIM = "#070b12", "#0d1420", "#1c2636", "#eef2f8", "#9aa7b8", "#5f6d82"
GREEN, RED, CYAN, AMBER = "#22c55e", "#f43f5e", "#22d3ee", "#f5b041"


def pfmt(x):
    if x is None: return "—"
    if x >= 1000: return f"${x:,.0f}"
    if x >= 1:
        t = f"{x:.4g}"
        return f"${x:,.2f}" if x >= 100 or len(t.split(".")[-1] if "." in t else "") < 2 else f"${t}"
    return f"${sig(x, 4):g}" if x >= 0.001 else f"${sig(x, 3)}"


def pick_focus(F, want):
    if want and want.lower() == "slate": return "slate"
    P = load("prices.json"); ids = {v["symbol"].lower(): k for k, v in P["assets"].items()}
    if want:
        w = want.lower()
        if w in P["assets"]: return w
        if w in ids: return ids[w]
        raise SystemExit(f"unknown --focus {want}")
    ev = F.get("trade_events") or F.get("trade_events_24h") or []
    if ev: return ids[ev[-1]["sym"].lower()]
    if F["slate"]:
        def dist(r):
            lo, hi = r["zone"]; p = r["now"]
            return 0 if lo <= p <= hi else min(abs(p / hi - 1), abs(1 - p / lo))
        return min(F["slate"], key=dist)["coin"]
    return "bitcoin"


def card(path, focus=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
    sans, mono = font_setup(fm)
    F = gather(); P = load("prices.json"); A = P["assets"]
    focus = pick_focus(F, focus)
    W, H = 1200, 675
    fig = plt.figure(figsize=(12, 6.75), dpi=100, facecolor=BG)
    g = fig.add_axes([0, 0, 1, 1]); g.axis("off"); g.set_xlim(0, W); g.set_ylim(H, 0)
    yy, xx = np.mgrid[0:1:150j, 0:1:260j]
    glow = np.exp(-((xx - 0.05) ** 2 / 0.10 + (yy - 0.0) ** 2 / 0.18)) * 0.5 + np.exp(-((xx - 1.0) ** 2 / 0.08 + (yy - 1.0) ** 2 / 0.12)) * 0.25
    g.imshow(glow, extent=(0, W, H, 0), cmap=matplotlib.colors.LinearSegmentedColormap.from_list("g", [BG, "#0f2a3d"]), aspect="auto", zorder=0)
    T = lambda x, y, s, **k: g.text(x, y, s, **{"color": TXT, "family": sans, "va": "center", **k})
    # frame: brand top-left, NFA top-right, URL bottom-left
    T(64, 58, BRAND.upper(), fontsize=13, weight="bold", color=CYAN)
    T(64 + 13 * 0.62 * len(BRAND) * 1.25 + 14, 58, "· public paper-trading experiment", fontsize=11.5, color=DIM)
    T(W - 64, 58, "paper trades · NFA", fontsize=11.5, color=AMBER, ha="right")
    T(64, H - 46, SITE_SHORT, fontsize=11.5, color=DIM)
    T(W - 64, H - 46, F["data_as_of"]["prices"] or "", fontsize=11, color=DIM, ha="right")

    if focus == "slate":
        T(64, 132, "Today's game plan", fontsize=34, weight="bold")
        rows = F["slate"][:4]
        if not rows:
            T(64, 300, "No setups. Sitting on hands.", fontsize=30, color=MUTED)
        step = min(100, 360 / max(1, len(rows))); y = 205 + (380 - step * len(rows)) / 2 + step / 2
        for r in rows:
            long_ = r["side"] == "long"
            T(64, y, r["sym"], fontsize=36, weight="bold")
            pill = "LONG" if long_ else "SHORT"
            g.add_patch(FancyBboxPatch((250, y - 17), 92, 34, boxstyle="round,pad=0,rounding_size=17", fc=(GREEN if long_ else RED) + "26", ec=GREEN if long_ else RED, lw=1.2))
            T(296, y, pill, fontsize=13, weight="bold", color=GREEN if long_ else RED, ha="center")
            lo, hi = r["zone"]
            T(380, y, (f"{pfmt(lo)}–{lvl(hi)}" if lo != hi else pfmt(lo)) if r["status"] == "pending" else f"in at {pfmt(r.get('entry'))}", fontsize=27, family=mono)
            T(W - 64, y - 12, f"now {pfmt(r['now'])}", fontsize=19, family=mono, ha="right")
            T(W - 64, y + 16, r.get("vs_zone") or r["status"], fontsize=13, color=MUTED, ha="right")
            y += step
    else:
        a = A[focus]; r = next((x for x in F["slate"] if x["coin"] == focus), None)
        T(64, 170, a["symbol"], fontsize=76, weight="bold")
        T(64, 262, pfmt(a["price"]), fontsize=46, family=mono)
        c24 = a.get("change_24h") or 0; col = GREEN if c24 >= 0 else RED
        g.add_patch(FancyBboxPatch((64, 306), 150, 40, boxstyle="round,pad=0,rounding_size=20", fc=col + "22", ec=col, lw=1.2))
        T(139, 326, f"{c24:+.1f}% 24h", fontsize=15, weight="bold", color=col, ha="center", family=mono)
        if r:
            lo, hi = r["zone"]; long_ = r["side"] == "long"
            head = f"{'Long' if long_ else 'Short'} idea · " + ("spot" if r['lev'] == 1 else f"{r['lev']}x")
            sub = (f"waiting for {lvl(lo)}–{lvl(hi)}" if r["status"] == "pending" else f"in at {lvl(r['entry'])}")
            T(64, 410, head, fontsize=21, weight="bold", color=GREEN if long_ else RED)
            T(64, 446, sub, fontsize=19, color=MUTED)
            if r.get("vs_zone"): T(64, 478, r["vs_zone"], fontsize=15, color=DIM)
        else:
            T(64, 410, "No trade on this one", fontsize=21, weight="bold", color=MUTED)
        # chart: last 7 days, hourly
        h = a.get("history", [])[-169:]
        xs = np.array([t / 1000 for t, _ in h]); ys = np.array([p for _, p in h])
        ax = fig.add_axes([500 / W, 1 - 560 / H, 520 / W, 440 / H]); ax.set_facecolor("none")
        for sp in ax.spines.values(): sp.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        lv = []
        if r:
            lv = [r["zone"][0], r["zone"][1], r["stop"], r["targets"][0]]
        lo_y, hi_y = min(list(ys) + lv), max(list(ys) + lv); pad = (hi_y - lo_y) * 0.08
        ax.set_ylim(lo_y - pad, hi_y + pad); ax.set_xlim(xs[0], xs[-1] + (xs[-1] - xs[0]) * 0.02)
        lc = GREEN if ys[-1] >= ys[0] else RED
        ax.plot(xs, ys, color=TXT, lw=2.4, solid_capstyle="round", zorder=3)
        ax.fill_between(xs, ys, lo_y - pad, color=lc, alpha=0.08, zorder=1)
        ax.plot([xs[-1]], [ys[-1]], "o", ms=9, color=TXT, mec=BG, mew=2, zorder=4)
        if r:
            ax.axhspan(r["zone"][0], r["zone"][1], color=CYAN, alpha=0.22, lw=0, zorder=2)
            ax.axhline(r["stop"], color=RED, lw=1.6, ls=(0, (6, 4)), zorder=2)
            ax.axhline(r["targets"][0], color=GREEN, lw=1.6, ls=(0, (6, 4)), zorder=2)
            import matplotlib.transforms as mtr
            tr = mtr.blended_transform_factory(ax.transAxes, ax.transData)
            ys_l = {"zone": (sum(r["zone"]) / 2, CYAN, "zone"), "stop": (r["stop"], RED, "stop"), "t1": (r["targets"][0], GREEN, "T1")}
            # keep labels at least ~7% of the axis apart
            span = (hi_y - lo_y + 2 * pad); placed = []
            for k, (y, c, name) in sorted(ys_l.items(), key=lambda kv: kv[1][0]):
                if placed and y - placed[-1] < span * 0.07: y = placed[-1] + span * 0.07
                placed.append(y)
                ax.text(1.03, y, name, color=c, fontsize=14, family=sans, weight="bold", va="center", ha="left", transform=tr, clip_on=False)
        T(520, 590, "last 7 days", fontsize=11, color=DIM)
    fig.savefig(path, dpi=100, facecolor=BG)
    plt.close(fig)
    return focus


# ---------------------------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="facts", choices=["facts", "card", "check", "save"])
    ap.add_argument("text", nargs="?", help="post text file for check/save ('-' = stdin)")
    ap.add_argument("--focus", help="slate, or a coin symbol/id for the card (default: latest event coin, else the idea nearest its zone)")
    ap.add_argument("--out", help="card output path")
    ap.add_argument("--kind", default="post", help="post kind label stored with the draft")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--no-card", action="store_true")
    a = ap.parse_args()
    if a.cmd == "facts":
        print(json.dumps(gather(), indent=1 if a.pretty else None, ensure_ascii=False, separators=None if a.pretty else (",", ":")))
        return 0
    if a.cmd == "card":
        out = a.out or os.path.join(POSTS, datetime.now(CT).strftime("%Y-%m-%d-%H%M") + "-card.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        f = card(out, a.focus); print(json.dumps({"card": out, "focus": f})); return 0
    if not a.text:
        raise SystemExit("check/save need a text file (or '-')")
    text = sys.stdin.read() if a.text == "-" else open(a.text, encoding="utf-8").read()
    posts = [p.strip() for p in re.split(r"\n-{3,}\n", text.strip()) if p.strip()]   # thread parts separated by a '---' line
    bad, n = check_text(text)
    lens = [len(re.sub(r"https?://\S+", "x" * 23, p)) for p in posts]
    report = {"posts": len(posts), "x_lengths": lens, "over_280": [i + 1 for i, l in enumerate(lens) if l > 280],
              "numbers_checked": n, "numbers_not_in_data": bad}
    if a.cmd == "check":
        print(json.dumps(report, ensure_ascii=False)); return 1 if bad or report["over_280"] else 0
    now = datetime.now(timezone.utc); stem = now.astimezone(CT).strftime("%Y-%m-%d-%H%M")
    os.makedirs(POSTS, exist_ok=True)
    txt, png = os.path.join(POSTS, stem + ".txt"), os.path.join(POSTS, stem + ".png")
    focus = None if a.no_card else card(png, a.focus)
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(posts) + "\n\n")
        f.write(f"=== notes (not for posting) ===\nkind: {a.kind}\nwritten: {ctfmt(now)}\ncard: {png if focus else '-'} (focus: {focus})\n"
                f"check: {json.dumps(report, ensure_ascii=False)}\nReview before posting; nothing is posted automatically.\n")
    P = load("prices.json"); TD = load("trades.json")
    json.dump({"at": now.isoformat(timespec="seconds").replace("+00:00", "Z"), "file": txt,
               "prices": {k: v["price"] for k, v in P["assets"].items()},
               "trades": {t["id"]: t["status"] for t in TD["trades"]},
               "slate_ids": [r["id"] for r in gather(now)["slate"]]}, open(BASELINE, "w"))
    print(json.dumps({"text": txt, "card": png if focus else None, "focus": focus, **report}, ensure_ascii=False))
    return 1 if bad or report["over_280"] else 0


if __name__ == "__main__":
    sys.exit(main())
