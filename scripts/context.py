#!/usr/bin/env python3
"""
Market-context snapshot -> data/context.json (fallback for the in-browser live fetch).
  python3 scripts/context.py
Sources (all free, no keys): CoinGecko /global (total mcap, BTC dominance), CoinMarketCap Fear & Greed (the ONLY
Fear & Greed source: if it fails, the last CoinMarketCap value is kept and marked stale, else it is shown as unavailable),
OKX public API (BTC-USDT perpetual funding rate + open interest), Yahoo Finance chart API (USD/JPY + Nikkei 225 for the yen /
carry-trade watch). Each source is optional; failures are recorded.
Afterwards it runs scripts/brief.py (data/brief.json + data/events.json for the Lumi API); a brief failure never breaks context.
"""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "context.json")
UA = {"User-Agent": "crypto-dashboard-context/1.0", "Accept": "application/json"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12) as r:
        return json.loads(r.read().decode())


def cg_global():
    d = get("https://api.coingecko.com/api/v3/global")["data"]
    return {"total_mcap_usd": d["total_market_cap"]["usd"], "total_volume_usd": d["total_volume"]["usd"],
            "mcap_change_24h_pct": d.get("market_cap_change_percentage_24h_usd"),
            "btc_dominance_pct": d["market_cap_percentage"]["btc"], "eth_dominance_pct": d["market_cap_percentage"].get("eth")}


CMC_BANDS = ((20, "Extreme fear"), (40, "Fear"), (60, "Neutral"), (80, "Greed"), (101, "Extreme greed"))


def fng_band(v):
    """CoinMarketCap band label: 0-20 Extreme fear, 20-40 Fear, 40-60 Neutral, 60-80 Greed, 80-100 Extreme greed."""
    return next(lbl for hi, lbl in CMC_BANDS if v < hi)


def _iso(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).isoformat().replace("+00:00", "Z")


def fng_cmc():
    import time
    now = int(time.time())
    d = get(f"https://api.coinmarketcap.com/data-api/v3/fear-greed/chart?start={now - 3 * 86400}&end={now}")["data"]
    hv = d["historicalValues"]; cur = hv["now"]; y = hv.get("yesterday") or {}
    v = int(round(float(cur["score"])))
    return {"value": v, "classification": fng_band(v),
            "previous": int(round(float(y["score"]))) if y.get("score") is not None else None,
            "timestamp": _iso(cur["timestamp"]), "source": "CoinMarketCap"}


def _last_cmc():
    """The previous snapshot's CoinMarketCap reading (data/context.json), or None."""
    try:
        with open(OUT) as fh:
            prev = json.load(fh).get("fear_greed") or {}
    except (OSError, ValueError):
        return None
    return prev if prev.get("source") == "CoinMarketCap" and prev.get("value") is not None else None


def fng():
    """CoinMarketCap Fear & Greed only (no other index, ever). On failure: the last cached CoinMarketCap value marked
    stale (with the time it was taken), else {"error": ..., "source": "CoinMarketCap"} = shown as unavailable."""
    try:
        return fng_cmc()
    except Exception as e:
        last = _last_cmc()
        if last:
            return {**{k: v for k, v in last.items() if k not in ("stale", "error")}, "stale": True,
                    "stale_reason": f"CoinMarketCap unavailable: {e}"}
        return {"error": f"CoinMarketCap unavailable: {e}", "source": "CoinMarketCap"}


def okx():
    f = get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")["data"][0]
    oi = get("https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP")["data"][0]
    return {"instrument": "BTC-USDT-SWAP (OKX)", "funding_rate_pct": float(f["fundingRate"]) * 100,
            "next_funding_time": datetime.fromtimestamp(int(f["fundingTime"]) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "open_interest_btc": float(oi["oiCcy"]), "open_interest_usd": float(oi["oiUsd"])}


def yahoo(symbol, name):
    """Latest quote + last 5 daily closes from Yahoo Finance's public chart endpoint (no key)."""
    from urllib.parse import quote
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range=5d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (crypto-dashboard-context)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        res = json.loads(r.read().decode())["chart"]["result"][0]
    m = res["meta"]; px = float(m["regularMarketPrice"]); prev = m.get("chartPreviousClose")
    closes = [round(float(c), 4) for t, c in zip(res.get("timestamp") or [], (res["indicators"]["quote"][0].get("close") or []))
              if c is not None]
    out = {"name": name, "symbol": symbol, "price": px,
           "change_pct": float(m["regularMarketChangePercent"]) if m.get("regularMarketChangePercent") is not None
           else (round((px / float(prev) - 1) * 100, 4) if prev else None),
           "day_high": m.get("regularMarketDayHigh"), "day_low": m.get("regularMarketDayLow"),
           "week52_high": m.get("fiftyTwoWeekHigh"), "week52_low": m.get("fiftyTwoWeekLow"),
           "closes_5d": closes, "as_of": _iso(m["regularMarketTime"]), "source": "Yahoo Finance"}
    return {k: v for k, v in out.items() if v is not None}


def yen():
    """USD/JPY and the Nikkei 225: the yen carry-trade watch (a fast yen rally forced the Aug 2024 unwind)."""
    out = {}
    for key, sym, name in (("usd_jpy", "JPY=X", "USD/JPY"), ("nikkei", "^N225", "Nikkei 225")):
        try:
            out[key] = yahoo(sym, name)
        except Exception as e:
            out[key] = {"error": str(e)}
    if all("error" in v for v in out.values()):
        raise RuntimeError("yahoo: " + "; ".join(v["error"] for v in out.values()))
    return out


def main():
    jobs = {"global": cg_global, "fear_greed": fng, "derivatives": okx, "yen": yen}
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    with ThreadPoolExecutor(4) as ex:
        futs = {k: ex.submit(f) for k, f in jobs.items()}
        for k, fu in futs.items():
            try:
                out[k] = fu.result()
            except Exception as e:
                out[k] = {"error": str(e)}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh, indent=1)
    os.replace(tmp, OUT)
    print(json.dumps(out, indent=1))
    try:  # brief.json + events.json for the Lumi API (/v1/brief, /v1/events); never fails the context refresh
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "brief.py")],
                       timeout=60, check=False, stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"context: brief.py skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
