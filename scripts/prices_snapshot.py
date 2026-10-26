#!/usr/bin/env python3
"""Refresh prices/index.json (the machine-readable /prices/ page) from the LIVE x402 402 quotes. stdlib only.

Every paid route is requested once WITHOUT a payment header (an unpaid GET: the API answers 402 with its quote and
nothing is ever paid or settled). The snapshot records each accepted asset's exact amount and payTo, and fails if a
USD-pegged amount differs from the site's price table (site_pages.TRUST_PRICES): the page can never show a price the
live 402 does not quote.
  python3 scripts/prices_snapshot.py            # write prices/index.json
  python3 scripts/prices_snapshot.py --check    # compare the checked-in snapshot with the live quotes, write nothing
"""
import datetime as dt, json, os, sys, urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_pages as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "prices", "index.json")
API = "https://api.lumitrades.io"
EX = "https%3A%2F%2Fapi.example.com%2Fv1%2Fdata"
# route, path template (as in TRUST_PRICES), the unpaid URL that returns the 402 quote
ROUTES = [
    ("verdict", "GET /v1/verdict?url=", f"/v1/verdict?url={EX}"),
    ("trust_check", "GET /v1/trust/check?url=", f"/v1/trust/check?url={EX}"),
    ("vendor_report", "GET /v1/trust/vendors/{id}/report", "/v1/trust/vendors/{id}/report"),
    ("receipts", "GET /v1/trust/receipts?seller=", "/v1/trust/receipts"),   # bare path: the live 402 quote, no seller named
    ("batch_check", "GET /v1/check/batch?urls=", f"/v1/check/batch?urls={EX},data.example.org"),
]
DECIMALS = {"eip155:8453": 6, "stellar:pubnet": 7}   # atomic units; XRP is in drops (6); XRPL IOUs are decimal strings
CHAIN = {"eip155:8453": "Base", "xrpl:0": "XRP Ledger", "stellar:pubnet": "Stellar"}
FREE = [
    ("Signed check from Lumi's record (same label as /v1/verdict)", "GET /v1/check?url="),
    ("Seller lookup and vendor trust list", "GET /v1/trust/vendors"),
    ("Verify a signed test-buy receipt", "POST /v1/trust/receipts/verify"),
]
PROOF = {
    "test_buy_wallets": f"{API}/v1/check/wallets",
    "signing_keys": f"{API}/v1/check/keys",
    "verify_receipt": f"{API}/v1/trust/receipts/verify",
    "dated_test_buys": "https://lumitrades.io/trust/",
    "how_tested": "https://lumitrades.io/how-it-works/",
    "sample_previews": f"{API}/v1/samples",
    "x402_discovery": f"{API}/.well-known/x402",
}



def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "lumi-site-prices/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _amount(a):
    sym = (a.get("extra") or {}).get("symbol") or ("XRP" if a["asset"] == "XRP" else "USDC")
    raw = str(a["amount"])
    if a["asset"] == "XRP":
        val = f"{int(raw) / 1e6:.6f}".rstrip("0").rstrip(".")
    elif a["network"] in DECIMALS:
        val = f"{int(raw) / 10 ** DECIMALS[a['network']]:.7f}".rstrip("0").rstrip(".")
    else:
        val = raw
    return {"network": a["network"], "chain": CHAIN.get(a["network"], a["network"]), "asset": sym, "amount": val,
            "amount_raw": raw, "pay_to": a["payTo"], "usd_pegged": sym != "XRP"}


def snapshot():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    table = {ep: pr for _, ep, pr in sp.TRUST_PRICES}
    paid, wallets = [], {}
    for route, ep, path in ROUTES:
        probe = path.replace("{id}", sp.BADGE_EXAMPLE)
        status, q = _get(API + probe)
        if status != 402:
            raise SystemExit(f"prices_snapshot: {probe} answered {status}, not a 402 quote")
        usd = table[ep].lstrip("$")
        opts = [_amount(a) for a in q.get("accepts", [])]
        for o in opts:
            if o["usd_pegged"] and float(o["amount"]) != float(usd):
                raise SystemExit(f"prices_snapshot: {ep} quotes {o['amount']} {o['asset']} on {o['chain']}, the site table says ${usd}")
            wallets.setdefault(o["network"], o["pay_to"])
        paid.append({"route": route, "endpoint": ep, "price_usd": usd, "quote_url": API + path,
                     "accepts": opts, "xrp_note": "XRP is quoted at the live XRP/USD rate on every call; the XRP amount here is the quote at as_of."})
    return {
        "kind": "lumi_prices",
        "name": "Lumi Trades: x402 seller trust you can verify",
        "as_of": now.isoformat().replace("+00:00", "Z"),
        "as_of_ct": now.astimezone(ZoneInfo("America/Chicago")).strftime("%b %-d, %Y %-I:%M %p %Z"),
        "method": "Each price is copied from the live x402 402 quote of an unpaid GET to quote_url at as_of. Request quote_url yourself to see the current quote; the quote you pay against is the one that applies.",
        "intent": {"check a seller before paying": f"{API}/v1/verdict?url=<x402 resource URL>"},
        "paid": paid,
        "free": [{"name": n, "endpoint": ep} for n, ep in FREE],
        "pay_to_rule": "Always take Lumi's payTo from the live 402 quote or /.well-known/x402, never from a past transfer.",
        "pay_to": [{"network": n, "chain": CHAIN.get(n, n), "address": a} for n, a in sorted(wallets.items())],
        "proof": PROOF,
        "never_charged": "Bad input is refused before any quote (4xx) and the API answers 503 'Not charged.' when it cannot answer.",
        "disclaimer": "Paying Lumi never changes a score or label. Observations, not a guarantee.",
    }


if __name__ == "__main__":
    snap = snapshot()
    if "--check" in sys.argv:
        old = json.load(open(OUT))
        strip = lambda d: [(p["endpoint"], p["price_usd"], [(o["network"], o["asset"], o["amount"], o["pay_to"]) for o in p["accepts"] if o["usd_pegged"]]) for p in d["paid"]]
        if strip(old) != strip(snap):
            raise SystemExit("prices_snapshot: prices/index.json no longer matches the live 402 quotes; rerun without --check")
        print("prices_snapshot: snapshot matches the live 402 quotes (USD-pegged assets)")
    else:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2)
            f.write("\n")
        print(f"prices_snapshot: wrote {os.path.relpath(OUT, ROOT)} (as of {snap['as_of_ct']})")
