#!/usr/bin/env python3
"""
Market-context snapshot -> data/context.json (fallback for the in-browser live fetch).
  python3 scripts/context.py
Sources (all free, no keys): CoinGecko /global (total mcap, BTC dominance), alternative.me Fear & Greed,
OKX public API (BTC-USDT perpetual funding rate + open interest). Each source is optional; failures are recorded.
"""
import json
import os
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


def fng():
    d = get("https://api.alternative.me/fng/?limit=2")["data"]
    return {"value": int(d[0]["value"]), "classification": d[0]["value_classification"],
            "previous": int(d[1]["value"]) if len(d) > 1 else None,
            "timestamp": datetime.fromtimestamp(int(d[0]["timestamp"]), timezone.utc).isoformat().replace("+00:00", "Z")}


def okx():
    f = get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")["data"][0]
    oi = get("https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP")["data"][0]
    return {"instrument": "BTC-USDT-SWAP (OKX)", "funding_rate_pct": float(f["fundingRate"]) * 100,
            "next_funding_time": datetime.fromtimestamp(int(f["fundingTime"]) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "open_interest_btc": float(oi["oiCcy"]), "open_interest_usd": float(oi["oiUsd"])}


def main():
    jobs = {"global": cg_global, "fear_greed": fng, "derivatives": okx}
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    with ThreadPoolExecutor(3) as ex:
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


if __name__ == "__main__":
    main()
