#!/usr/bin/env python3
"""
Refresh market data for the crypto dashboard and evaluate open paper trades.

  python3 scripts/update_prices.py            # normal run
  python3 scripts/update_prices.py --no-fetch # re-evaluate trades using existing data/prices.json

Writes:
  data/prices.json  - current quotes + 30-day hourly history (CoinGecko free public API)
  data/trades.json  - open trades marked won/stopped when target/stop was hit since entry; stats recomputed
  data/log.json     - an automatic log entry is prepended

Does NOT touch data/analysis.json (commentary, levels, projections) - that is edited by hand.
Stdlib only (urllib), so it runs anywhere Python 3.9+ is available.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
API = "https://api.coingecko.com/api/v3"
CENTRAL = ZoneInfo("America/Chicago")

# CoinGecko IDs verified 2026-10-21 via /search and /coins/markets.
# NOTE: AXL is "axelar" (NOT "axelar-network", which resolves to an unrelated ~$1 asset).
COINS = [
    {"id": "hedera-hashgraph", "symbol": "HBAR", "name": "Hedera"},
    {"id": "stellar", "symbol": "XLM", "name": "Stellar"},
    {"id": "ripple", "symbol": "XRP", "name": "XRP"},
    {"id": "zebec-network", "symbol": "ZBCN", "name": "Zebec Network"},
    {"id": "axelar", "symbol": "AXL", "name": "Axelar"},
]
BACKDROP = {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin"}
SLEEP_BETWEEN = 2.5  # seconds between calls; free tier allows ~5-30 calls/min
LOG_MAX = 500


def get(path, params, retries=5):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API}{path}?{qs}"
    headers = {"Accept": "application/json", "User-Agent": "crypto-dashboard/1.0"}
    key = os.environ.get("COINGECKO_DEMO_API_KEY")  # optional free "demo" key
    if key:
        headers["x-cg-demo-api-key"] = key
    delay = 10
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = int(e.headers.get("Retry-After") or delay)
                print(f"  HTTP {e.code} on {path}; sleeping {wait}s (attempt {attempt}/{retries})", file=sys.stderr)
                time.sleep(wait)
                delay = min(delay * 2, 90)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  network error {e}; retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 90)
    raise RuntimeError(f"giving up on {url}")


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
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, p)


def iso(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(s):
    """ISO string (with Z or offset; naive = Central time) -> epoch ms."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CENTRAL)
    return int(dt.timestamp() * 1000)


def sig(x):
    """Round to 6 significant figures (keeps tiny prices like ZBCN readable)."""
    if x is None:
        return None
    return float(f"{x:.6g}")


# ---------------------------------------------------------------- fetching
def fetch_prices():
    all_coins = COINS + [BACKDROP]
    ids = ",".join(c["id"] for c in all_coins)
    print("Fetching quotes ...")
    markets = get("/coins/markets", {
        "vs_currency": "usd", "ids": ids,
        "price_change_percentage": "24h,7d,30d",
    })
    by_id = {m["id"]: m for m in markets}
    missing = [c["id"] for c in all_coins if c["id"] not in by_id]
    if missing:
        raise RuntimeError(f"CoinGecko returned no market data for: {missing} (check IDs)")

    out = {}
    for c in all_coins:
        time.sleep(SLEEP_BETWEEN)
        print(f"Fetching 30d history for {c['id']} ...")
        h = get(f"/coins/{c['id']}/market_chart", {"vs_currency": "usd", "days": 30})
        m = by_id[c["id"]]
        out[c["id"]] = {
            "id": c["id"], "symbol": c["symbol"], "name": c["name"],
            "price": m["current_price"],
            "change_24h": m.get("price_change_percentage_24h_in_currency"),
            "change_7d": m.get("price_change_percentage_7d_in_currency"),
            "change_30d": m.get("price_change_percentage_30d_in_currency"),
            "high_24h": m.get("high_24h"), "low_24h": m.get("low_24h"),
            "market_cap": m.get("market_cap"), "market_cap_rank": m.get("market_cap_rank"),
            "volume_24h": m.get("total_volume"),
            "ath": m.get("ath"), "ath_date": m.get("ath_date"),
            "last_updated": m.get("last_updated"),
            # [epoch_ms, price] roughly hourly for 30 days
            "history": [[int(t), sig(p)] for t, p in h["prices"]],
        }
    now = datetime.now(timezone.utc)
    return {
        "updated_utc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "updated_central": now.astimezone(CENTRAL).strftime("%Y-%m-%d %I:%M %p %Z"),
        "source": "CoinGecko public API (coins/markets + coins/{id}/market_chart?days=30)",
        "backdrop": BACKDROP["id"],
        "coins": [c["id"] for c in COINS],
        "assets": out,
    }


# ---------------------------------------------------------- trade evaluation
def pnl_pct(direction, entry, exit_price, leverage):
    move = (exit_price - entry) / entry
    if direction == "short":
        move = -move
    return round(move * leverage * 100, 2)


def evaluate_trade(t, history, now_ms):
    """
    Walk the price history from the trade's open time (or last check) forward.
    Rules (documented in README):
      * Position is split equally across targets (scale-out).
      * Stop hit before any target            -> status "stopped" (loss at stop).
      * After target 1 fills, stop moves to entry (breakeven) unless move_stop_to_be is false.
      * All targets hit                       -> status "won".
      * Some targets hit, then (BE) stop hit  -> status "won" if blended P&L > 0, else "lost".
      * Optional "expires" timestamp: at expiry, remaining size closes at market -> won/lost by P&L sign.
    Uses CoinGecko hourly points, so intrahour wicks are not seen (conservative + approximate).
    """
    if t.get("status") == "pending":
        # Pending idea: fills the first time price trades into entry_zone {low, high}
        # (or through `entry` if no zone). Fill price = the touching price, clamped to the zone
        # edge nearest the previous price. Cancels at `expiry` (alias: legacy `fill_by`).
        start = max(parse_ts(t["opened_at"]), t.get("last_checked_ms", 0))
        deadline = t.get("expiry") or t.get("fill_by")
        cancel = parse_ts(deadline) if deadline else None
        z = t.get("entry_zone") or {}
        zlo, zhi = z.get("low", t["entry"]), z.get("high", t["entry"])
        prev = None
        for ts, price in history:
            if ts <= start:
                prev = price
                continue
            if cancel and ts > cancel:
                t.update(status="cancelled", closed_at=iso(cancel))
                return True
            lo, hi = (min(prev, price), max(prev, price)) if prev is not None else (price, price)
            if lo <= zhi and hi >= zlo:  # path touched the zone
                if zlo <= price <= zhi:
                    fill = price
                elif prev is not None:
                    fill = zhi if prev > zhi else zlo if prev < zlo else prev
                else:
                    fill = min(max(price, zlo), zhi)
                t.setdefault("planned_entry", t["entry"])
                t.update(status="open", filled_at=iso(ts), entry=sig(fill), last_checked_ms=ts - 1)
                break
            prev = price
        else:
            if history:
                t["last_checked_ms"] = int(history[-1][0])
            if cancel and now_ms > cancel:
                t.update(status="cancelled", closed_at=iso(cancel))
                return True
            if history:
                t["mark_price"] = sig(history[-1][1])
            return False
        # fall through: evaluate the freshly opened trade from its fill time
    if t.get("status") != "open":
        return False
    d, lev = t["direction"], t.get("leverage", 3)
    entry, targets = t["entry"], sorted(t["targets"], reverse=(t["direction"] == "short"))
    n = len(targets)
    hits = t.setdefault("targets_hit", [])
    stop = t.get("current_stop", t["stop"])
    start = max(parse_ts(t.get("filled_at") or t["opened_at"]), t.get("last_checked_ms", 0))
    expires = parse_ts(t["expires"]) if t.get("expires") else None
    changed = False

    def close(status, ts, last_exit):
        legs = [h["price"] for h in hits] + [last_exit] * (n - len(hits))
        pnl = round(sum(pnl_pct(d, entry, p, lev) for p in legs) / n, 2)
        if status is None:
            status = "won" if pnl > 0 else "lost"
        t.update(status=status, closed_at=iso(ts), exit_price=sig(last_exit), pnl_pct=pnl)

    for ts, price in history:
        if ts <= start:
            continue
        if expires and ts > expires:
            close(None, expires, price)
            changed = True
            break
        stop_hit = price <= stop if d == "long" else price >= stop
        if stop_hit:
            close("stopped" if not hits else None, ts, stop)
            changed = True
            break
        while len(hits) < n:
            tgt = targets[len(hits)]
            if (price >= tgt) if d == "long" else (price <= tgt):
                hits.append({"price": tgt, "at": iso(ts)})
                changed = True
                if t.get("move_stop_to_be", True):
                    stop = entry
                    t["current_stop"] = entry
            else:
                break
        if len(hits) == n:
            close("won", ts, targets[-1])
            break

    if history:
        t["last_checked_ms"] = int(history[-1][0])
    if t["status"] == "open" and history:
        last = history[-1][1]
        legs = [h["price"] for h in hits] + [last] * (n - len(hits))
        t["unrealized_pnl_pct"] = round(sum(pnl_pct(d, entry, p, lev) for p in legs) / n, 2)
        t["mark_price"] = sig(last)
    else:
        t.pop("unrealized_pnl_pct", None)
        t.pop("mark_price", None)
    return changed


def compute_stats(trades):
    closed = sorted([t for t in trades if t["status"] in ("won", "lost", "stopped")],
                    key=lambda t: t["closed_at"])
    wins = sum(1 for t in closed if t["status"] == "won")
    cum, curve = 0.0, []
    for t in closed:
        cum += t["pnl_pct"]
        curve.append({"t": t["closed_at"], "trade_id": t["id"], "cum_pnl_pct": round(cum, 2)})
    return {
        "total": len(trades),
        "open": sum(1 for t in trades if t["status"] == "open"),
        "pending": sum(1 for t in trades if t["status"] == "pending"),
        "closed": len(closed),
        "won": wins,
        "lost_or_stopped": len(closed) - wins,
        "win_rate_pct": round(100 * wins / len(closed), 1) if closed else None,
        "cumulative_pnl_pct": round(cum, 2),
        "note": "Cumulative P&L is the simple sum of per-trade % returns at each trade's leverage (equal size per trade).",
        "equity_curve": curve,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="reuse existing data/prices.json")
    args = ap.parse_args()

    if args.no_fetch:
        prices = load("prices.json", None)
        if not prices:
            sys.exit("no data/prices.json to reuse")
    else:
        prices = fetch_prices()
        save("prices.json", prices)
        print("Wrote data/prices.json")

    tdoc = load("trades.json", {"trades": []})
    now_ms = int(time.time() * 1000)
    notes = []
    sym = {k: v["symbol"] for k, v in prices["assets"].items()}
    for t in tdoc["trades"]:
        a = prices["assets"].get(t["coin"])
        if not a:
            notes.append(f"{t['id']}: no price data for {t['coin']}")
            continue
        before = (t["status"], len(t.get("targets_hit", [])))
        evaluate_trade(t, a["history"], now_ms)
        after = (t["status"], len(t.get("targets_hit", [])))
        if after != before:
            if before[0] == "pending" and t["status"] == "open":
                notes.append(f"{t['id']} ({sym[t['coin']]}): entry {t['entry']} filled")
            elif t["status"] == "cancelled":
                notes.append(f"{t['id']} ({sym[t['coin']]}): not filled in time, cancelled")
            elif t["status"] == "open":
                notes.append(f"{t['id']} ({sym[t['coin']]}): target {after[1]} hit")
            else:
                notes.append(f"{t['id']} ({sym[t['coin']]}) closed as {t['status'].upper()} "
                             f"at {t['exit_price']} ({t['pnl_pct']:+.2f}% at {t.get('leverage', 3)}x)")
    tdoc["stats"] = compute_stats(tdoc["trades"])
    # Slate rules: max one active (pending/open) idea per coin, max 5 active overall.
    active = [t for t in tdoc["trades"] if t["status"] in ("pending", "open")]
    warn = []
    per = {}
    for t in active:
        per.setdefault(t["coin"], []).append(t["id"])
    warn += [f"{c}: {len(v)} active ideas ({', '.join(v)}) - max 1 per coin" for c, v in per.items() if len(v) > 1]
    if len(active) > 5:
        warn.append(f"{len(active)} active ideas - max 5")
    tdoc["stats"]["slate_warnings"] = warn
    for w in warn:
        print("WARNING:", w, file=sys.stderr)
    tdoc["evaluated_utc"] = prices["updated_utc"]
    save("trades.json", tdoc)
    print("Wrote data/trades.json")

    log = load("log.json", {"entries": []})
    quotes = ", ".join(
        f"{prices['assets'][i]['symbol']} {prices['assets'][i]['price']:.6g} ({prices['assets'][i]['change_24h'] or 0:+.1f}%)"
        for i in [prices["backdrop"]] + prices["coins"])
    s = tdoc["stats"]
    msg = (f"Re-evaluated trades on existing data (no fetch); prices as of {prices['updated_central']}: {quotes}." if args.no_fetch
           else f"Prices refreshed: {quotes}.")
    if notes:
        msg += " Trades: " + "; ".join(notes) + "."
    msg += f" Open trades: {s['open']}; pending: {s['pending']}; closed: {s['closed']}; win rate: " + \
           (f"{s['win_rate_pct']}%" if s["win_rate_pct"] is not None else "n/a") + "."
    log["entries"].insert(0, {"t": prices["updated_utc"], "kind": "auto", "author": "update_prices.py", "text": msg})
    log["entries"] = log["entries"][:LOG_MAX]
    save("log.json", log)
    print("Wrote data/log.json")
    print(msg)


if __name__ == "__main__":
    main()
