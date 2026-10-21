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
Idempotent: each trade stores last_checked (ISO) / last_checked_ms = end of the last processed candle; only candles
ending after it are processed, so a second run processes nothing new. Concurrency: holds an exclusive flock on state/lock while reading/writing data files.
"""
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
    return {
        "total": len(trades), "open": sum(1 for t in trades if t["status"] == "open"),
        "pending": sum(1 for t in trades if t["status"] == "pending"), "closed": len(closed), "won": wins,
        "lost_or_stopped": len(closed) - wins,
        "win_rate_pct": round(100 * wins / len(closed), 1) if closed else None,
        "cumulative_pnl_pct": round(cum, 2),
        "note": "Cumulative P&L is the simple sum of per-trade % returns at each trade's leverage (equal size per trade).",
        "equity_curve": curve, "slate_warnings": warn,
    }


def describe(e, t, sym):
    lev = t.get("leverage", 3)
    k = e["type"]
    if k == "filled":
        return f"{t['id']} {sym} {t['direction']} {lev}x FILLED at {e['price']} (zone {e['zone'][0]}–{e['zone'][1]})"
    if k.startswith("target"):
        return f"{t['id']} {sym}: target {k[6]} hit at {e['price']}" + (" — stop moved to breakeven" if k == "target1_hit" and t.get("move_stop_to_be", True) else "")
    if k == "cancelled":
        return f"{t['id']} {sym}: expired unfilled, cancelled"
    return f"{t['id']} {sym} closed {k.upper()} at {e['price']} ({e['pnl_pct']:+.2f}% at {lev}x)"


def run(lock_held=False, log_events=True):
    """Evaluate all active trades. Returns the result dict. Safe to call from update_prices.py."""
    if not lock_held:
        with file_lock():
            return run(lock_held=True, log_events=log_events)
    now_ms = int(time.time() * 1000)
    tdoc = load("trades.json", {"trades": []})
    active = [t for t in tdoc["trades"] if t.get("status") in ("pending", "open")]
    coins = sorted({t["coin"] for t in active})
    since = {c: min(t.get("last_checked_ms") or parse_ts(t["opened_at"]) for t in active if t["coin"] == c) for c in coins}
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
    for t in active:
        if t["coin"] not in fetched:
            continue
        candles, src = fetched[t["coin"]]
        for e in evaluate(t, candles, now_ms):
            e.update(id=t["id"], coin=t["coin"], symbol=sym.get(t["coin"], t["coin"]), source=src)
            e["text"] = describe(e, t, e["symbol"])
            events.append(e)
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
                        "unrealized_pnl_pct": t.get("unrealized_pnl_pct"), "last_checked": t.get("last_checked")} for t in active],
            "sources": {c: v[1] for c, v in fetched.items()}, "errors": errors,
            "slate_warnings": tdoc["stats"]["slate_warnings"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
