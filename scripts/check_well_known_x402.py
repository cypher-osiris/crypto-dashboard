#!/usr/bin/env python3
"""Validate /.well-known/x402 (pointer to api.lumitrades.io). Offline by default; --live also compares the
featured prices with the API's live unpaid 402 quotes (USDC on Base, 6 decimals). Never pays anything."""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = {"/v1/trust/check": "/v1/trust/check?url=https://api.example.com/v1/data", "/v1/verdict": "/v1/verdict?url=https://api.example.com/v1/data", "/v1/lite/{coin}": "/v1/lite/XRP"}


def load():
    a = open(os.path.join(ROOT, ".well-known/x402")).read()
    b = open(os.path.join(ROOT, ".well-known/x402.json")).read()
    assert a == b, ".well-known/x402 and .well-known/x402.json differ"
    return json.loads(a)


def check(d):
    assert d.get("kind") == "pointer" and d.get("version") == 1
    for k in ("x402", "resources_host", "openapi"):
        assert str(d.get(k, "")).startswith("https://api.lumitrades.io"), k
    assert d["x402"].endswith("/.well-known/x402")
    feat = d.get("featured") or []
    assert feat, "featured is empty"
    for f in feat:
        assert f["url"].startswith("https://api.lumitrades.io/v1/"), f["url"]
        float(f["price_usd"])
    return feat


def live_usdc(path):
    req = urllib.request.Request("https://api.lumitrades.io" + path, headers={"User-Agent": "lumitrades-site-check"})
    try:
        urllib.request.urlopen(req, timeout=20)
        raise AssertionError(f"{path}: expected 402")
    except urllib.error.HTTPError as e:
        assert e.code == 402, f"{path}: HTTP {e.code}"
        body = json.loads(e.read())
    base = [a for a in body["accepts"] if a["network"] == "eip155:8453"][0]
    return int(base["amount"]) / 1e6


if __name__ == "__main__":
    feat = check(load())
    print("JSON ok:", len(feat), "featured routes")
    if "--live" in sys.argv:
        bad = 0
        for f in feat:
            path = f["url"].replace("https://api.lumitrades.io", "")
            got = live_usdc(PROBE[path])
            ok = abs(got - float(f["price_usd"])) < 1e-9
            bad += not ok
            print(("ok  " if ok else "DIFF"), path, "file", f["price_usd"], "live", f"{got:g}")
        sys.exit(1 if bad else 0)
