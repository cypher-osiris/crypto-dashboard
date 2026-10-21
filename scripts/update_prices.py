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

# Coin list lives in data/coins.json (CoinGecko ids verified 2026-10-21; AXL is "axelar", NOT "axelar-network").
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coins as coincfg  # noqa: E402
COINS = [{"id": c["id"], "symbol": c["symbol"], "name": c["name"], "group": c.get("group")} for c in coincfg.coins()]
BACKDROP_ID = coincfg.backdrop()
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


def save(name, obj, compact=False):
    p = os.path.join(DATA, name)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        if compact:  # prices.json: 12 coins x 30 days of history -> keep it small for page load
            json.dump(obj, f, separators=(",", ":"))
        else:
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
    all_coins = COINS + ([] if any(c["id"] == BACKDROP_ID for c in COINS) else [{"id": BACKDROP_ID, "symbol": "BTC", "name": "Bitcoin", "group": None}])
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
            "id": c["id"], "symbol": c["symbol"], "name": c["name"], "group": c.get("group"),
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
        "backdrop": BACKDROP_ID,
        "coins": [c["id"] for c in COINS],
        "groups": [dict(g, coins=[c["id"] for c in COINS if c.get("group") == g["id"]]) for g in coincfg.config().get("groups", [])],
        "assets": out,
    }


# ---------------------------------------------------------- trade evaluation
# Delegated to scripts/track_trades.py (single engine, fine-grained candles) so results never conflict.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track_trades  # noqa: E402


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
        save("prices.json", prices, compact=True)
        print("Wrote data/prices.json")

    with track_trades.file_lock():
        res = track_trades.run(lock_held=True, log_events=True)
        tdoc = load("trades.json", {"trades": []})
        notes = [e["text"] for e in res["events"]]
        if res["errors"]:
            notes.append("tracking errors: " + "; ".join(f"{k}: {v}" for k, v in res["errors"].items()))
        for w in tdoc["stats"].get("slate_warnings", []):
            print("WARNING:", w, file=sys.stderr)
        print("Trades evaluated by track_trades.py")
        log = load("log.json", {"entries": []})
        quotes = ", ".join(
            f"{prices['assets'][i]['symbol']} {prices['assets'][i]['price']:.6g} ({prices['assets'][i]['change_24h'] or 0:+.1f}%)"
            for i in dict.fromkeys([prices["backdrop"]] + prices["coins"]))
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
