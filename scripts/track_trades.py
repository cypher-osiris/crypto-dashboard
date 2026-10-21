#!/usr/bin/env python3
"""
Track pending/open paper trades against fine-grained candles. Run with no arguments:

  python3 scripts/track_trades.py     # prints {"events":[...], ...} JSON; updates data/trades.json (+ data/log.json on events)

This is the ONLY trade-evaluation engine: scripts/update_prices.py delegates to it, so results never conflict.

Candles (only CLOSED candles are used, newer than each trade's last_checked):
  Coinbase Exchange 5m (BTC/XRP/XLM/HBAR/AXL), paginated 300 per request; 1h if the gap is > 7 days
  Kraken OHLC 5m for ZBCN (720 max = 60h; 60m if the gap is longer)
  Fallback: CoinGecko market_chart price points as synthetic candles (o=h=l=c)

Fill / exit rules (conservative, documented in README):
  * pending -> open when a candle's [low, high] touches entry_zone {low, high} (or `entry` if no zone).
    Fill price = the zone edge FIRST TOUCHED: the edge nearest the candle's open (a long waiting above the zone
    fills at zone.high, a short waiting below fills at zone.low); if the candle opens inside the zone, fill at the open.
    The plan is kept in planned_entry; `entry` becomes the fill.
  * In the fill candle only the stop is checked (targets are not credited in the fill candle).
  * Stop and a target inside the same candle -> assume the STOP hit first.
  * Position is split equally across targets; after T1 the stop moves to entry (breakeven) from the NEXT candle
    (disable with "move_stop_to_be": false).
  * pending past `expiry` (legacy `fill_by`) -> cancelled. open past optional `expires` -> closed at that candle's open.
  * Result: stop before any target = "stopped"; all targets = "won"; partial then stop/expiry = "won" if blended
    P&L > 0 else "lost". P&L % is on margin = price move x leverage (no fees/funding).
Missed-it plans (optional `missed_plan` on a trade, see README "Missed-it plans"):
  * type pullback|breakout|flip|none; `trigger_rule` {tf:"1h", kind:"retest_hold"|"close_above"|"close_below", level}
    makes it machine-checkable (pullback defaults to retest_hold on its entry_zone). Triggers use COMPLETED 1h
    candles aggregated from the 5m data, starting with the first full hour after the plan was written.
  * status watching -> armed when the main idea is pending and a 5m close is past missed_it.max_entry (the chase
    side), or when the main idea expired unfilled (flip: when the main idea was stopped, or a 1h close beyond its stop).
  * armed + trigger -> a linked trade "<id>b" (parent_id, source "missed_plan of <id>") is created: open at the trigger
    candle's close if that close is inside the plan zone, else pending in the zone until the plan expiry. A still-pending
    main idea is cancelled ("superseded"), so the one-idea-per-coin rule holds. The linked trade is then tracked like any other.
  * void if the main idea fills first (not for flip); invalidated on a 1h close beyond the plan stop while armed;
    expired at missed_plan.expiry (default: the main idea's expiry).
Idempotent: each trade stores last_checked (ISO) / last_checked_ms = end of the last processed candle; only candles
ending after it are processed, so a second run processes nothing new. Concurrency: holds an exclusive flock on state/lock while reading/writing data files.
"""
import copy
import fcntl
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LOCK = os.path.join(ROOT, "state", "lock")
CENTRAL = ZoneInfo("America/Chicago")
UA = {"User-Agent": "crypto-dashboard-tracker/1.0", "Accept": "application/json"}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coins as coincfg  # noqa: E402  (coin list: data/coins.json)
_CFG = coincfg.coins()
SOURCES = {c["id"]: coincfg.source(c) for c in _CFG}
SYMBOLS = {c["id"]: c["symbol"] for c in _CFG}
SLATE_MAX = coincfg.slate_max()
LOG_MAX = 500


# ------------------------------------------------------------------ utils
@contextmanager
def file_lock(timeout=300):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    fh = open(LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() - t0 > timeout:
                raise TimeoutError("could not acquire state/lock")
            time.sleep(0.5)
    try:
        fh.seek(0); fh.truncate(); fh.write(f"{os.getpid()} {sys.argv[0]} {datetime.now(timezone.utc).isoformat()}\n"); fh.flush()
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def get(url, timeout=10):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode())


def load(name, default):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def save(name, obj):
    p = os.path.join(DATA, name)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CENTRAL)
    return int(dt.timestamp() * 1000)


def sig(x):
    return None if x is None else float(f"{x:.6g}")


# ------------------------------------------------------------------ candles
# normalized: (start_ms, end_ms, open, high, low, close), closed candles only, ascending
def coinbase(product, since_ms, now_ms):
    gran = 300 if now_ms - since_ms <= 7 * 864e5 else 3600
    out, start = {}, since_ms - since_ms % (gran * 1000)
    while start < now_ms:
        end = min(start + 300 * gran * 1000, now_ms)
        rows = get(f"https://api.exchange.coinbase.com/products/{product}/candles?granularity={gran}"
                   f"&start={iso(start)}&end={iso(end)}")
        for t, lo, hi, o, c, v in rows:
            out[t] = (t * 1000, (t + gran) * 1000, o, hi, lo, c)
        start = end
        if start < now_ms:
            time.sleep(0.15)
    return [c for c in sorted(out.values()) if c[1] <= now_ms], f"coinbase {gran // 60}m"


def kraken(pair, since_ms, now_ms):
    iv = 5 if now_ms - since_ms <= 55 * 3600e3 else 60
    d = get(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={iv}&since={int(since_ms / 1000) - iv * 60}")
    if d.get("error"):
        raise RuntimeError(d["error"])
    rows = next(v for k, v in d["result"].items() if k != "last")
    c = [(int(r[0]) * 1000, (int(r[0]) + iv * 60) * 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]
    return [x for x in c if x[1] <= now_ms], f"kraken {iv}m"


def coingecko(cid, since_ms, now_ms):
    days = max(1, int((now_ms - since_ms) / 864e5) + 1)
    d = get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=usd&days={days}")
    pts = d["prices"]
    c = [(int(pts[i][0]), int(pts[i + 1][0]), pts[i][1], max(pts[i][1], pts[i + 1][1]), min(pts[i][1], pts[i + 1][1]), pts[i + 1][1])
         for i in range(len(pts) - 1)]
    return c, "coingecko points"


def candles_for(cid, since_ms, now_ms):
    src, prod = SOURCES.get(cid, (None, None))
    try:
        if src == "coinbase":
            return coinbase(prod, since_ms, now_ms)
        if src == "kraken":
            return kraken(prod, since_ms, now_ms)
    except Exception as e:  # noqa: BLE001
        print(f"  {cid}: {src} failed ({e}); falling back to CoinGecko", file=sys.stderr)
    return coingecko(cid, since_ms, now_ms)


# ------------------------------------------------------------------ evaluation
def pnl_pct(direction, entry, exit_price, leverage):
    move = (exit_price - entry) / entry
    return round((-move if direction == "short" else move) * leverage * 100, 2)


def blended(t, last_exit):
    n = len(t["targets"])
    legs = [h["price"] for h in t.get("targets_hit", [])] + [last_exit] * (n - len(t.get("targets_hit", [])))
    return round(sum(pnl_pct(t["direction"], t["entry"], p, t.get("leverage", 3)) for p in legs) / n, 2)


def evaluate(t, candles, now_ms):
    """Advance one trade through candles. Returns list of event dicts. Mutates t."""
    ev = []
    if t.get("status") not in ("pending", "open"):
        return ev
    d = t["direction"]
    long_ = d == "long"
    lc = t.get("last_checked_ms") or parse_ts(t["opened_at"])
    deadline = t.get("expiry") or t.get("fill_by")
    cancel_ms = parse_ts(deadline) if deadline else None
    max_hold = parse_ts(t["expires"]) if t.get("expires") else None
    z = t.get("entry_zone") or {}
    zlo, zhi = z.get("low", t["entry"]), z.get("high", t["entry"])

    def close(status, ms, price):
        t["exit_price"] = sig(price)
        t["pnl_pct"] = blended(t, price)
        if status is None:
            status = "won" if t["pnl_pct"] > 0 else "lost"
        t["status"], t["closed_at"] = status, iso(ms)
        ev.append({"type": status, "price": t["exit_price"], "time": t["closed_at"], "pnl_pct": t["pnl_pct"]})

    for (s, e, o, h, l, c) in candles:
        if e <= lc:  # candle fully processed in an earlier run (idempotency)
            continue
        if t["status"] == "pending":
            if cancel_ms and s >= cancel_ms:
                t["status"], t["closed_at"] = "cancelled", iso(cancel_ms)
                ev.append({"type": "cancelled", "time": t["closed_at"], "reason": "expiry reached unfilled"})
                lc = e
                break
            if l <= zhi and h >= zlo:
                fill = o if zlo <= o <= zhi else (zhi if o > zhi else zlo)
                t.setdefault("planned_entry", t["entry"])
                t.update(status="open", entry=sig(fill), filled_at=iso(s))
                ev.append({"type": "filled", "price": t["entry"], "time": t["filled_at"], "zone": [zlo, zhi]})
                stop = t.get("current_stop", t["stop"])
                if (l <= stop) if long_ else (h >= stop):
                    close("stopped", s, stop)
                    lc = e
                    break
            lc = e
            continue
        # open
        if max_hold and s >= max_hold:
            close(None, s, o)
            lc = e
            break
        stop = t.get("current_stop", t["stop"])
        hits = t.setdefault("targets_hit", [])
        tg = sorted(t["targets"], reverse=not long_)
        if (l <= stop) if long_ else (h >= stop):  # conservative: stop wins ties with targets
            close("stopped" if not hits else None, s, stop)
            lc = e
            break
        new_hit = False
        while len(hits) < len(tg):
            x = tg[len(hits)]
            if (h >= x) if long_ else (l <= x):
                hits.append({"price": x, "at": iso(s)})
                ev.append({"type": f"target{len(hits)}_hit", "price": x, "time": iso(s)})
                new_hit = True
            else:
                break
        if len(hits) == len(tg):
            close("won", s, tg[-1])
            lc = e
            break
        if new_hit and t.get("move_stop_to_be", True):
            t["current_stop"] = t["entry"]
        lc = e

    if t["status"] == "pending" and cancel_ms and now_ms >= cancel_ms:
        t["status"], t["closed_at"] = "cancelled", iso(cancel_ms)
        ev.append({"type": "cancelled", "time": t["closed_at"], "reason": "expiry reached unfilled"})
    t["last_checked_ms"] = int(lc)
    t["last_checked"] = iso(lc)
    if candles:
        t["mark_price"] = sig(candles[-1][5])
    if t["status"] == "open" and candles:
        t["unrealized_pnl_pct"] = blended(t, candles[-1][5])
    else:
        t.pop("unrealized_pnl_pct", None)
    if t["status"] not in ("pending", "open"):
        t.pop("mark_price", None)
    return ev


# ------------------------------------------------------------------ missed-it plans
HOUR = 3600 * 1000
LIVE_PLAN = ("watching", "armed")


def plan_rr(plan, direction):
    """(worst, best) reward:risk from the plan zone edges to its target. None if incomplete."""
    z = plan.get("entry_zone") or {}
    try:
        lo, hi, stop, tgt = float(z["low"]), float(z["high"]), float(plan["stop"]), float(plan["target"])
    except (KeyError, TypeError, ValueError):
        return None
    worst, best = (hi, lo) if direction == "long" else (lo, hi)
    f = lambda e: abs(tgt - e) / abs(e - stop) if e != stop else 0.0  # noqa: E731
    return round(f(worst), 2), round(f(best), 2)


def plan_direction(t, plan):
    if plan.get("direction") in ("long", "short"):
        return plan["direction"]
    if plan.get("type") == "flip":
        return "short" if t["direction"] == "long" else "long"
    return t["direction"]


def plan_rule(plan):
    r = dict(plan.get("trigger_rule") or {})
    if not r.get("kind") and plan.get("type") == "pullback":
        r["kind"] = "retest_hold"
    r.setdefault("tf", "1h")
    return r if r.get("kind") in ("retest_hold", "close_above", "close_below") else None


def plan_issues(t):
    """Validation messages for one trade's missed_plan (used for slate_warnings)."""
    plan = t.get("missed_plan")
    if not plan:
        return [] if t.get("parent_id") else [f"{t['id']}: no missed_plan"]
    typ = plan.get("type")
    if typ == "none":
        return [] if plan.get("reasoning") else [f"{t['id']}: missed_plan type none needs a reasoning"]
    out = []
    if typ not in ("pullback", "breakout", "flip"):
        return [f"{t['id']}: missed_plan.type must be pullback|breakout|flip|none"]
    for k in ("trigger", "entry_zone", "stop", "target", "reasoning"):
        if plan.get(k) in (None, "", {}):
            out.append(f"{t['id']}: missed_plan.{k} missing")
    rr = plan_rr(plan, plan_direction(t, plan))
    if rr and rr[0] < 1.5:
        out.append(f"{t['id']}: missed_plan R:R {rr[0]} < 1.5 from the worst entry - use type none")
    if not plan_rule(plan):
        out.append(f"{t['id']}: missed_plan has no machine-checkable trigger_rule (tracked manually)")
    return out


def hour_buckets(candles):
    """Aggregate candles into complete 1h buckets: (start, end, o, h, l, c, [sub-candles])."""
    if not candles:
        return []
    last_end = candles[-1][1]
    b = {}
    for c in candles:
        b.setdefault(c[0] - c[0] % HOUR, []).append(c)
    out = []
    for hs in sorted(b):
        cs = b[hs]
        if hs + HOUR > last_end:  # hour not complete yet
            continue
        out.append((hs, hs + HOUR, cs[0][2], max(x[3] for x in cs), min(x[4] for x in cs), cs[-1][5], cs))
    return out


def scan_plan(t, plan, candles, now_ms, sim):
    """Advance a live missed_plan through complete hours. `sim` = the main trade evaluated on the same candles
    (a copy). Returns (events, trigger) where trigger = (end_ms, close) or None. Mutates plan."""
    ev = []
    typ, rule = plan.get("type"), plan_rule(plan)
    pdir = plan_direction(t, plan)
    long_main, long_plan = t["direction"] == "long", pdir == "long"
    mi = (t.get("missed_it") or {}).get("max_entry")
    z = plan["entry_zone"]
    zlo, zhi, pstop = float(z["low"]), float(z["high"]), float(plan["stop"])
    exp = plan.get("expiry") or t.get("expiry") or t.get("fill_by")
    exp_ms = parse_ts(exp) if exp else None
    fill_ms = parse_ts(sim["filled_at"]) if sim.get("filled_at") else None
    cancel_ms = parse_ts(sim["closed_at"]) if sim.get("status") == "cancelled" and sim.get("closed_at") else None
    stop_ms = parse_ts(sim["closed_at"]) if sim.get("status") in ("stopped", "lost") and sim.get("closed_at") else None
    lc = plan.get("last_checked_ms") or 0

    def note(kind, ms, **k):
        ev.append({"type": kind, "time": iso(ms), **k})
    for (hs, he, o, h, l, c, subs) in hour_buckets(candles):
        if he <= lc:
            continue
        if exp_ms and hs >= exp_ms:
            plan["status"], plan["ended_at"] = "expired", iso(exp_ms); note("missed_plan_expired", exp_ms); lc = he; break
        if typ != "flip" and fill_ms is not None and fill_ms < he and plan["status"] in LIVE_PLAN:
            plan["status"], plan["ended_at"] = "void", iso(fill_ms); plan["void_reason"] = "main idea filled"; note("missed_plan_void", fill_ms, reason="main idea filled"); lc = he; break
        if plan["status"] == "watching":
            arm_at = None
            if typ == "flip":
                if stop_ms is not None and stop_ms < he:
                    arm_at = max(stop_ms, hs)
                elif (c < t["stop"]) if long_main else (c > t["stop"]):
                    arm_at = he
            else:
                if mi is not None:
                    for sc in subs:
                        if (sc[5] > mi) if long_main else (sc[5] < mi):
                            arm_at = sc[1]; break
                if arm_at is None and cancel_ms is not None and cancel_ms < he:
                    arm_at = max(cancel_ms, hs)
            if arm_at is not None:
                plan["status"], plan["armed_at"] = "armed", iso(arm_at)
                note("missed_plan_armed", arm_at, reason="main idea stopped" if typ == "flip" else ("main idea expired" if cancel_ms and cancel_ms <= arm_at else f"price past the missed-it limit {mi}"))
        if plan["status"] == "armed" and rule:
            if (c < pstop) if long_plan else (c > pstop):
                plan["status"], plan["ended_at"] = "invalidated", iso(he); note("missed_plan_invalidated", he, price=sig(c)); lc = he; break
            k = rule["kind"]
            fired = (k == "close_above" and c > float(rule["level"])) or (k == "close_below" and c < float(rule["level"])) or \
                    (k == "retest_hold" and ((l <= zhi and c >= zlo) if long_plan else (h >= zlo and c <= zhi)))
            if fired:
                lc = he
                plan["last_checked_ms"], plan["last_checked"] = int(lc), iso(lc)
                return ev, (he, c)
        lc = he
    if plan["status"] in LIVE_PLAN and exp_ms and now_ms >= exp_ms and lc >= exp_ms:
        plan["status"], plan["ended_at"] = "expired", iso(exp_ms); note("missed_plan_expired", exp_ms)
    if lc:
        plan["last_checked_ms"], plan["last_checked"] = int(lc), iso(lc)
    return ev, None


def linked_trade(t, plan, trig_ms, close):
    z = plan["entry_zone"]
    zlo, zhi = float(z["low"]), float(z["high"])
    pdir = plan_direction(t, plan)
    lt = {
        "id": plan.get("linked_id") or (t["id"] + "b"), "coin": t["coin"], "direction": pdir,
        "leverage": plan.get("leverage", 3), "entry": sig((zlo + zhi) / 2), "entry_zone": {"low": zlo, "high": zhi},
        "stop": plan["stop"], "targets": [plan["target"]], "opened_at": iso(trig_ms),
        "expiry": plan.get("expiry") or t.get("expiry") or t.get("fill_by"), "status": "pending", "move_stop_to_be": False,
        "parent_id": t["id"], "plan_type": plan.get("type"), "trigger": plan.get("trigger"), "size_note": plan.get("size_note"),
        "reasoning": f"MISSED-IT PLAN of {t['id']} ({plan.get('type')}), triggered: {plan.get('trigger')}. {plan.get('reasoning', '')}",
        "source": f"missed_plan of {t['id']} (auto-activated by track_trades.py)",
        "last_checked_ms": int(trig_ms), "last_checked": iso(trig_ms),
    }
    for k in ("market", "timeframe", "timeframe_note", "expires"):  # spot/position ideas keep their nature
        if t.get(k):
            lt[k] = t[k]
    if zlo <= close <= zhi:
        lt.update(status="open", entry=sig(close), planned_entry=sig((zlo + zhi) / 2), filled_at=iso(trig_ms))
    return lt


def compute_stats(trades):
    closed = sorted([t for t in trades if t["status"] in ("won", "lost", "stopped")], key=lambda t: t["closed_at"])
    wins = sum(1 for t in closed if t["status"] == "won")
    cum, curve = 0.0, []
    for t in closed:
        cum += t["pnl_pct"]
        curve.append({"t": t["closed_at"], "trade_id": t["id"], "cum_pnl_pct": round(cum, 2)})
    active = [t for t in trades if t["status"] in ("pending", "open")]
    per, warn = {}, []
    for t in active:
        per.setdefault(t["coin"], []).append(t["id"])
    warn += [f"{c}: {len(v)} active ideas ({', '.join(v)}) - max 1 per coin" for c, v in per.items() if len(v) > 1]
    if len(active) > SLATE_MAX:
        warn.append(f"{len(active)} active ideas - max {SLATE_MAX}")
    for t in active:
        warn += plan_issues(t)
        if t.get("market") == "spot" or t.get("leverage") == 1:  # spot = 1x, long only
            if t.get("direction") != "long" or t.get("leverage", 3) != 1:
                warn.append(f"{t['id']}: spot ideas must be long at leverage 1")
            mp = t.get("missed_plan") or {}
            if mp.get("type") not in (None, "none") and (mp.get("leverage", 3) != 1 or mp.get("type") == "flip"):
                warn.append(f"{t['id']}: spot idea's missed_plan must be leverage 1 and not a flip (no shorts)")
    return {
        "total": len(trades), "open": sum(1 for t in trades if t["status"] == "open"),
        "pending": sum(1 for t in trades if t["status"] == "pending"), "closed": len(closed), "won": wins,
        "lost_or_stopped": len(closed) - wins,
        "win_rate_pct": round(100 * wins / len(closed), 1) if closed else None,
        "cumulative_pnl_pct": round(cum, 2),
        "note": "Cumulative P&L is the simple sum of per-trade % returns at each trade's leverage (equal size per trade).",
        "equity_curve": curve, "slate_warnings": warn,
    }


def lev_txt(lev):
    """'spot' for 1x (no leverage, long only), else '3x' etc."""
    return "spot" if lev == 1 else f"{lev}x"


def describe(e, t, sym):
    lev = t.get("leverage", 3)
    k = e["type"]
    if k == "filled":
        return f"{t['id']} {sym} {t['direction']} {lev_txt(lev)} FILLED at {e['price']} (zone {e['zone'][0]}–{e['zone'][1]})"
    if k.startswith("target"):
        return f"{t['id']} {sym}: target {k[6]} hit at {e['price']}" + (" — stop moved to breakeven" if k == "target1_hit" and t.get("move_stop_to_be", True) else "")
    if k == "cancelled":
        return f"{t['id']} {sym}: " + (e.get("reason") or "expired unfilled") + ", cancelled"
    if k.startswith("missed_plan_"):
        p = t.get("missed_plan") or {}
        what = {"armed": "missed-it plan ARMED (" + str(e.get("reason")) + "); watching: " + str(p.get("trigger")),
                "triggered": f"missed-it plan TRIGGERED ({p.get('trigger')}) -> {e.get('linked_id')} "
                             + ("opened at " + str(e.get("price")) if e.get("linked_status") == "open" else f"pending in {e.get('zone')}"),
                "void": "missed-it plan void (" + str(e.get("reason")) + ")",
                "invalidated": f"missed-it plan invalidated (1h close {e.get('price')} beyond its stop)",
                "expired": "missed-it plan expired"}[k[12:]]
        return f"{t['id']} {sym}: {what}"
    return f"{t['id']} {sym} closed {k.upper()} at {e['price']} ({e['pnl_pct']:+.2f}% at {lev_txt(lev)})"


def run(lock_held=False, log_events=True):
    """Evaluate all active trades. Returns the result dict. Safe to call from update_prices.py."""
    if not lock_held:
        with file_lock():
            return run(lock_held=True, log_events=log_events)
    now_ms = int(time.time() * 1000)
    tdoc = load("trades.json", {"trades": []})
    for t in tdoc["trades"]:  # initialise new missed plans: scanning starts at the first full hour after now
        p = t.get("missed_plan")
        if p and "status" not in p:
            p["status"] = "n/a" if p.get("type") == "none" else "watching"
            if p["status"] == "watching":
                p["last_checked_ms"] = now_ms - now_ms % HOUR + HOUR
                p["last_checked"] = iso(p["last_checked_ms"])
    planned = [t for t in tdoc["trades"] if (t.get("missed_plan") or {}).get("status") in LIVE_PLAN]
    planned_ids = {t["id"] for t in planned}
    active = [t for t in tdoc["trades"] if t.get("status") in ("pending", "open") or t["id"] in planned_ids]
    coins = sorted({t["coin"] for t in active})

    def since_of(t):
        a = t.get("last_checked_ms") or parse_ts(t["opened_at"])
        if t["id"] in planned_ids:
            a = min(a, t["missed_plan"]["last_checked_ms"]) if t.get("status") in ("pending", "open") else t["missed_plan"]["last_checked_ms"]
        return a
    since = {c: min(since_of(t) for t in active if t["coin"] == c) for c in coins}
    fetched, errors = {}, {}

    def job(c):
        try:
            return c, candles_for(c, since[c], now_ms)
        except Exception as e:  # noqa: BLE001
            return c, e
    with ThreadPoolExecutor(max_workers=6) as ex:
        for c, res in ex.map(job, coins):
            if isinstance(res, Exception):
                errors[c] = str(res)
            else:
                fetched[c] = res
    events = []
    sym = SYMBOLS
    new_trades = []

    def emit(t, evs, src):
        for e in evs:
            e.update(id=t["id"], coin=t["coin"], symbol=sym.get(t["coin"], t["coin"]), source=src)
            e["text"] = describe(e, t, e["symbol"])
            events.append(e)
    for t in active:
        if t["coin"] not in fetched:
            continue
        candles, src = fetched[t["coin"]]
        plan = t.get("missed_plan") or {}
        trig = None
        if plan.get("status") in LIVE_PLAN and plan.get("type") != "none" and not plan_issues(t):  # invalid plans are never auto-activated
            sim = copy.deepcopy(t)
            if sim.get("status") in ("pending", "open"):
                evaluate(sim, candles, now_ms)
            pev, trig = scan_plan(t, plan, candles, now_ms, sim)
            if trig:
                trig_ms, close = trig
                # main idea up to the trigger only, then superseded if it is still pending
                if t.get("status") in ("pending", "open"):
                    emit(t, evaluate(t, [c for c in candles if c[1] <= trig_ms], trig_ms), src)
                if t.get("status") == "pending":
                    t["status"], t["closed_at"], t["cancel_reason"] = "cancelled", iso(trig_ms), "superseded by missed-it plan"
                    t.pop("mark_price", None)
                    pev.append({"type": "cancelled", "time": iso(trig_ms), "reason": "superseded by its missed-it plan"})
                if t.get("status") in ("pending", "open"):  # main filled in the trigger hour after all: keep it, void the plan
                    plan["status"], plan["ended_at"] = "void", iso(trig_ms); plan["void_reason"] = "main idea filled"
                    pev.append({"type": "missed_plan_void", "time": iso(trig_ms), "reason": "main idea filled"})
                else:
                    lt = linked_trade(t, plan, trig_ms, close)
                    plan.update(status="triggered", triggered_at=iso(trig_ms), linked_id=lt["id"])
                    pev.append({"type": "missed_plan_triggered", "time": iso(trig_ms), "linked_id": lt["id"], "linked_status": lt["status"],
                                "price": sig(close), "zone": [lt["entry_zone"]["low"], lt["entry_zone"]["high"]]})
                    new_trades.append(lt)
                    sc = ((tdoc.get("slate") or {}).get("coins") or {}).get(t["coin"])
                    if sc is not None and sc.get("trade_id") == t["id"]:
                        sc["trade_id"] = lt["id"]
            emit(t, pev, src)
        if not trig and t.get("status") in ("pending", "open"):
            emit(t, evaluate(t, candles, now_ms), src)
    for lt in new_trades:
        tdoc["trades"].append(lt)
        candles, src = fetched[lt["coin"]]
        emit(lt, evaluate(lt, candles, now_ms), src)
        active.append(lt)
    events.sort(key=lambda e: e.get("time") or "")
    tdoc["stats"] = compute_stats(tdoc["trades"])
    tdoc["tracked_utc"] = iso(now_ms)
    save("trades.json", tdoc)
    if events and log_events:
        log = load("log.json", {"entries": []})
        log["entries"].insert(0, {"t": iso(now_ms), "kind": "auto", "author": "track_trades.py", "text": "Trade events: " + "; ".join(e["text"] for e in events) + "."})
        log["entries"] = log["entries"][:LOG_MAX]
        save("log.json", log)
    return {"checked_utc": iso(now_ms), "events": events, "publish": bool(events),
            "active": [{"id": t["id"], "symbol": sym.get(t["coin"]), "status": t["status"], "mark": t.get("mark_price"),
                        "unrealized_pnl_pct": t.get("unrealized_pnl_pct"), "last_checked": t.get("last_checked"),
                        "missed_plan": (t.get("missed_plan") or {}).get("status")} for t in active],
            "sources": {c: v[1] for c, v in fetched.items()}, "errors": errors,
            "slate_warnings": tdoc["stats"]["slate_warnings"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
