#!/usr/bin/env python3
"""
Mechanical technical-indicator signals for the dashboard coins.

  python3 scripts/signals.py          # no arguments needed; prints JSON to stdout, writes data/signals.json
  python3 scripts/signals.py --quiet  # write file only (prints a one-line summary to stderr)

Standalone (stdlib only), fast (~2-5 s: all candle requests run in parallel, 10 s timeouts).
Candles: Coinbase Exchange (coinbase pairs in data/coins.json) and Kraken (kraken pairs, e.g. ZBCN); CoinGecko market_chart fallback.
Timeframes: 1h, 4h (built from 1h on Coinbase, native on Kraken), 1d.
Indicators: RSI(14), MACD(12,26,9), EMA20/50 (+EMA200 on 1d), Bollinger(20,2) %B + squeeze,
volume vs 20-period average (last CLOSED candle), Stochastic RSI(14,14,3,3).
The same scoring is implemented in assets/signals.js (keep them in sync).
These are mechanical indicator readings, NOT predictions or advice.
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "signals.json")
UA = {"User-Agent": "crypto-dashboard-signals/1.0", "Accept": "application/json"}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coins as coincfg  # noqa: E402  (coin list: data/coins.json)
COINS = [(c["id"], c["symbol"]) + coincfg.source(c) for c in coincfg.coins()]  # id, symbol, source, product
TF_WEIGHTS = {"1h": 0.25, "4h": 0.35, "1d": 0.40}
LABELS = [(0.5, "Strong Buy"), (0.15, "Buy"), (-0.15, "Neutral"), (-0.5, "Sell")]  # else Strong Sell


def get(url, timeout=10, retries=3):
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:  # public rate limits (Coinbase ~10 req/s): brief backoff
            if e.code not in (429, 500, 502, 503, 504) or i == retries - 1:
                raise
            time.sleep(0.6 * (i + 1))


# ---------------------------------------------------------------- candles
# normalized candle: [t_sec, open, high, low, close, volume] ascending
def coinbase(product, gran):
    rows = get(f"https://api.exchange.coinbase.com/products/{product}/candles?granularity={gran}")
    return sorted([[int(r[0]), r[3], r[2], r[1], r[4], r[5]] for r in rows])


def kraken(pair, interval):
    d = get(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}")
    if d.get("error"):
        raise RuntimeError(d["error"])
    rows = next(v for k, v in d["result"].items() if k != "last")
    return [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])] for r in rows]


def coingecko(cid, days):
    d = get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=usd&days={days}")
    # price points only -> synthetic candles with o=h=l=c, no volume
    return [[int(t / 1000), p, p, p, p, None] for t, p in d["prices"]]


def resample(c, secs):
    out = {}
    for t, o, h, l, cl, v in c:
        k = t - t % secs
        if k not in out:
            out[k] = [k, o, h, l, cl, v]
        else:
            b = out[k]
            b[2], b[3], b[4] = max(b[2], h), min(b[3], l), cl
            b[5] = None if v is None or b[5] is None else b[5] + v
    rows = sorted(out.values())
    # drop a leading partial bucket
    if len(rows) > 1 and c and c[0][0] % secs:
        rows = rows[1:]
    return rows


def fetch(coin):
    cid, sym, src, prod = coin
    tfs, used = {}, src
    try:
        if src == "coinbase":
            h1 = coinbase(prod, 3600)
            tfs = {"1h": h1, "4h": resample(h1, 14400), "1d": coinbase(prod, 86400)}
        else:
            tfs = {"1h": kraken(prod, 60), "4h": kraken(prod, 240), "1d": kraken(prod, 1440)}
    except Exception as e:  # fallback
        used = f"coingecko (fallback: {src} failed: {e})"
        h = coingecko(cid, 30)
        tfs = {"1h": resample(h, 3600), "4h": resample(h, 14400), "1d": resample(coingecko(cid, 365), 86400)}
    return cid, sym, used, tfs


# ---------------------------------------------------------------- indicators
def ema_series(vals, n):
    out = [None] * len(vals)
    if len(vals) < n:
        return out
    k = 2 / (n + 1)
    e = sum(vals[:n]) / n
    out[n - 1] = e
    for i in range(n, len(vals)):
        e = vals[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi_series(vals, n=14):
    out = [None] * len(vals)
    if len(vals) <= n:
        return out
    gains = [max(vals[i] - vals[i - 1], 0) for i in range(1, len(vals))]
    losses = [max(vals[i - 1] - vals[i], 0) for i in range(1, len(vals))]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    out[n] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(vals)):
        ag = (ag * (n - 1) + gains[i - 1]) / n
        al = (al * (n - 1) + losses[i - 1]) / n
        out[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def r(x, d=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, d)


def sig(x):
    return None if x is None else float(f"{x:.6g}")


def analyze(candles, tf):
    closes = [c[4] for c in candles]
    price = closes[-1]
    res, pts, mx = {}, 0.0, 0.0

    # RSI
    rs = rsi_series(closes)
    v = rs[-1]
    if v is not None:
        p = 1 if v <= 30 else -1 if v >= 70 else 0.5 if v >= 50 else -0.5
        st = "oversold" if v <= 30 else "overbought" if v >= 70 else "bullish momentum" if v >= 50 else "bearish momentum"
        res["rsi"] = {"value": r(v, 1), "state": st, "points": p}
        pts += p; mx += 1

    # MACD
    e12, e26 = ema_series(closes, 12), ema_series(closes, 26)
    macd = [a - b if a is not None and b is not None else None for a, b in zip(e12, e26)]
    valid = [m for m in macd if m is not None]
    if len(valid) >= 9 + 3:
        sg = ema_series(valid, 9)
        hist = [m - s if s is not None else None for m, s in zip(valid, sg)]
        hnow = hist[-1]
        cross = None
        for i in range(1, 4):
            a, b = hist[-i - 1], hist[-i]
            if a is not None and b is not None and (a <= 0 < b or a >= 0 > b):
                cross = "bullish" if b > 0 else "bearish"
                break
        p = (1 if hnow > 0 else -1) + (0.5 if cross == "bullish" else -0.5 if cross == "bearish" else 0)
        st = ("fresh bullish cross" if cross == "bullish" else "fresh bearish cross" if cross == "bearish"
              else "above signal" if hnow > 0 else "below signal")
        res["macd"] = {"value": sig(valid[-1]), "signal": sig(sg[-1]), "hist": sig(hnow), "cross": cross, "state": st, "points": p}
        pts += p; mx += 1.5

    # EMA trend
    e20, e50 = ema_series(closes, 20)[-1], ema_series(closes, 50)[-1]
    if e20 is not None and e50 is not None:
        if price > e20 > e50:
            p, st = 1, "price > EMA20 > EMA50 (uptrend)"
        elif price < e20 < e50:
            p, st = -1, "price < EMA20 < EMA50 (downtrend)"
        else:
            p, st = (0.5, "mixed, above EMA50") if price > e50 else (-0.5, "mixed, below EMA50")
        res["ema"] = {"ema20": sig(e20), "ema50": sig(e50), "state": st, "points": p}
        pts += p; mx += 1
    if tf == "1d":
        e200 = ema_series(closes, 200)[-1]
        if e200 is not None:
            p = 1 if price > e200 else -1
            res["ema200"] = {"ema200": sig(e200), "state": "above EMA200" if p > 0 else "below EMA200", "points": p}
            pts += p; mx += 1

    # Bollinger
    if len(closes) >= 20:
        def bb_at(end):
            w = closes[end - 20:end]
            m = sum(w) / 20
            sd = (sum((x - m) ** 2 for x in w) / 20) ** 0.5
            return m, sd
        m, sd = bb_at(len(closes))
        up, lo = m + 2 * sd, m - 2 * sd
        pb = (price - lo) / (up - lo) if up > lo else 0.5
        bw = (up - lo) / m if m else 0
        hist_bw = []
        for end in range(max(20, len(closes) - 120), len(closes) + 1):
            mm, ss = bb_at(end)
            hist_bw.append(4 * ss / mm if mm else 0)
        squeeze = len(hist_bw) >= 40 and bw <= sorted(hist_bw)[int(len(hist_bw) * 0.2)]
        p = -0.5 if pb > 1 else 0.5 if pb < 0 else 0
        st = ("above upper band (stretched)" if pb > 1 else "below lower band (stretched)" if pb < 0
              else "upper half" if pb >= 0.5 else "lower half") + (" · squeeze" if squeeze else "")
        res["bb"] = {"pct_b": r(pb, 2), "bandwidth_pct": r(bw * 100, 2), "upper": sig(up), "lower": sig(lo), "squeeze": squeeze, "state": st, "points": p}
        pts += p; mx += 0.5

    # Stochastic RSI (14,14,3,3)
    rv = [x for x in rs if x is not None]
    if len(rv) >= 14 + 6:
        raw = []
        for i in range(13, len(rv)):
            w = rv[i - 13:i + 1]
            lo_, hi_ = min(w), max(w)
            raw.append(0.5 if hi_ == lo_ else (rv[i] - lo_) / (hi_ - lo_))
        k = [sum(raw[i - 2:i + 1]) / 3 for i in range(2, len(raw))]
        d = [sum(k[i - 2:i + 1]) / 3 for i in range(2, len(k))]
        K, D = k[-1] * 100, d[-1] * 100
        p = 0.5 if K < 20 and K > D else -0.5 if K > 80 and K < D else 0
        st = ("oversold, turning up" if p > 0 else "overbought, turning down" if p < 0
              else "oversold" if K < 20 else "overbought" if K > 80 else "neutral")
        res["stochrsi"] = {"k": r(K, 1), "d": r(D, 1), "state": st, "points": p}
        pts += p; mx += 0.5

    # Volume vs 20-period average (last closed candle)
    vols = [c[5] for c in candles[:-1]]
    if len(vols) >= 21 and all(v is not None for v in vols[-21:]):
        avg = sum(vols[-21:-1]) / 20
        last = candles[-2]
        ratio = vols[-1] / avg if avg else None
        if ratio is not None:
            up_c = last[4] >= last[1]
            p = (0.5 if up_c else -0.5) if ratio >= 1.5 else 0
            st = (f"high volume on {'green' if up_c else 'red'} candle" if ratio >= 1.5
                  else "low volume" if ratio < 0.6 else "normal volume")
            res["volume"] = {"ratio": r(ratio, 2), "state": st, "points": p}
            pts += p; mx += 0.5

    score = pts / mx if mx else 0
    return {"price": sig(price), "candle_time": datetime.fromtimestamp(candles[-1][0], timezone.utc).isoformat().replace("+00:00", "Z"),
            "bars": len(candles), "indicators": res, "points": round(pts, 2), "max_points": mx, "score": round(score, 3)}


def label(score):
    for thr, name in LABELS:
        if score >= thr:
            return name
    return "Strong Sell"


def main():
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda c: (c, safe_fetch(c)), COINS))
    coins = {}
    for coin, got in results:
        cid, sym = coin[0], coin[1]
        if isinstance(got, Exception):
            coins[cid] = {"symbol": sym, "error": str(got)}
            continue
        _, _, used, tfs = got
        out, tot, wsum = {}, 0.0, 0.0
        for tf, w in TF_WEIGHTS.items():
            c = tfs.get(tf) or []
            if len(c) < 35:
                continue
            a = analyze(c, tf)
            a["label"] = label(a["score"])
            out[tf] = a
            tot += a["score"] * w
            wsum += w
        sc = round(tot / wsum, 3) if wsum else None
        coins[cid] = {"symbol": sym, "source": used, "price": out.get("1h", {}).get("price"),
                      "score": sc, "label": label(sc) if sc is not None else "n/a", "timeframes": out}
    doc = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "elapsed_s": round(time.time() - t0, 2),
        "disclaimer": "Mechanical indicator readings only - not predictions or financial advice.",
        "method": {"timeframe_weights": TF_WEIGHTS,
                   "labels": "score >= 0.5 Strong Buy; >= 0.15 Buy; > -0.15 Neutral; > -0.5 Sell; else Strong Sell",
                   "points": "RSI +-1/+-0.5, MACD hist +-1 (+-0.5 fresh cross), EMA stack +-1 (+-0.5 mixed), EMA200 +-1 (1d), "
                             "Bollinger %B outside bands +-0.5, StochRSI turn +-0.5, volume >=1.5x avg +-0.5; score = points / max"},
        "coins": coins,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, OUT)
    if "--quiet" in sys.argv:
        print("signals: " + ", ".join(f"{v['symbol']} {v.get('label')} ({v.get('score')})" for v in coins.values())
              + f" in {doc['elapsed_s']}s", file=sys.stderr)
    else:
        print(json.dumps(doc, indent=1))


def safe_fetch(c):
    try:
        return fetch(c)
    except Exception as e:
        return e


if __name__ == "__main__":
    main()
