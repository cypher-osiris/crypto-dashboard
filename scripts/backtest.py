#!/usr/bin/env python3
"""
Backtest the dashboard's signal system (same indicator math and composite score as scripts/signals.py).

  python3 scripts/backtest.py            # fetch (cached in state/cache for 12h), backtest, write data/backtest.json
  python3 scripts/backtest.py --refresh  # ignore the candle cache

History (free, no keys): Coinbase Exchange 1h (365 days, paginated 300/request; 4h built from 1h) and 1d (~730 days)
for BTC/XRP/XLM/HBAR/AXL; Kraken OHLC for ZBCN (720 bars per interval: 1h ~30 days, 4h ~120 days, 1d ~2 years).

No lookahead: every indicator value at bar i uses only candles <= i (causal recursions, verified against
signals.analyze()); signals act at the CLOSE of bar i, entries fill at the OPEN of bar i+1; the composite at a 4h close
uses the last CLOSED daily bar (the live dashboard uses the forming daily candle - a small, conservative difference).
Forward returns are close-to-close. Events are transitions INTO a condition (first bar), to limit overlap.
"""
import json
import math
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import signals as S  # noqa: E402  (same math)

CACHE = os.path.join(ROOT, "state", "cache")
OUT = os.path.join(ROOT, "data", "backtest.json")
WEIGHTS_OUT = os.path.join(ROOT, "data", "signal_weights.json")
UA = {"User-Agent": "crypto-dashboard-backtest/1.0", "Accept": "application/json"}
H = 3600
LEV, FEE = 3, 0.0006           # 3x, 0.06% per side on notional
ATR_STOP, ATR_TGT = 1.5, 3.0
COMPONENTS = ["rsi", "macd", "ema", "ema200", "bb", "stochrsi", "volume"]
CANDIDATES = {  # weightings compared out-of-sample (equal = what signals.py uses today)
    "equal": {k: 1.0 for k in ["rsi", "macd", "ema", "ema200", "bb", "stochrsi", "volume"]},
    "drop_trend_volume": {"rsi": 1, "macd": 1, "ema": 0, "ema200": 1, "bb": 1, "stochrsi": 1, "volume": 0},
    "mean_reversion_only": {"rsi": 1, "macd": 0, "ema": 0, "ema200": 0, "bb": 1, "stochrsi": 1, "volume": 0},
    "trend_only": {"rsi": 0, "macd": 1, "ema": 1, "ema200": 1, "bb": 0, "stochrsi": 0, "volume": 0},
}
MAXPTS = {"rsi": 1, "macd": 1.5, "ema": 1, "ema200": 1, "bb": 0.5, "stochrsi": 0.5, "volume": 0.5}


# ============================================================== data
def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 * (k + 1)); continue
            raise
        except Exception:
            time.sleep(1 + k)
    raise RuntimeError("failed: " + url)


def iso(sec):
    return datetime.fromtimestamp(sec, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def coinbase_hist(prod, gran, days):
    end = int(time.time()) // gran * gran
    start = end - days * 86400
    out, t, empties = {}, end, 0
    while t > start:
        s = max(start, t - 300 * gran)
        rows = get(f"https://api.exchange.coinbase.com/products/{prod}/candles?granularity={gran}&start={iso(s)}&end={iso(t)}")
        if not rows:
            empties += 1
            if empties >= 2:
                break
        for r in rows:
            out[r[0]] = [int(r[0]), r[3], r[2], r[1], r[4], r[5]]
        t = s
        time.sleep(0.12)
    now = time.time()
    return [c for c in sorted(out.values()) if c[0] + gran <= now]  # closed candles only


def kraken_hist(pair, iv):
    d = get(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={iv}")
    rows = next(v for k, v in d["result"].items() if k != "last")
    now = time.time()
    return [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])] for r in rows if int(r[0]) + iv * 60 <= now]


def fetch(coin, refresh):
    cid, sym, src, prod = coin
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{cid}.json")
    if not refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < 12 * 3600:
        with open(path) as f:
            return json.load(f)
    if src == "coinbase":
        h1 = coinbase_hist(prod, 3600, 365)
        d = {"source": "Coinbase Exchange", "1h": h1, "4h": S.resample(h1, 14400), "1d": coinbase_hist(prod, 86400, 730)}
    else:
        d = {"source": "Kraken", "1h": kraken_hist(prod, 60), "4h": kraken_hist(prod, 240), "1d": kraken_hist(prod, 1440)}
    with open(path, "w") as f:
        json.dump(d, f)
    return d


# ============================================================== causal per-bar series (mirrors signals.analyze)
def series(c, tf):
    n = len(c)
    cl = [x[4] for x in c]
    rs = S.rsi_series(cl)
    e12, e26 = S.ema_series(cl, 12), S.ema_series(cl, 26)
    first = next((i for i in range(n) if e12[i] is not None and e26[i] is not None), None)
    valid = [e12[i] - e26[i] for i in range(first, n)] if first is not None else []
    sg = S.ema_series(valid, 9)
    hist = [m - s if s is not None else None for m, s in zip(valid, sg)]
    e20, e50 = S.ema_series(cl, 20), S.ema_series(cl, 50)
    e200 = S.ema_series(cl, 200) if tf == "1d" else [None] * n
    # Bollinger stats for each window END (exclusive index)
    bbm, bbs = [None] * (n + 1), [None] * (n + 1)
    for end in range(20, n + 1):
        w = cl[end - 20:end]; m = sum(w) / 20
        bbm[end], bbs[end] = m, (sum((x - m) ** 2 for x in w) / 20) ** 0.5
    bwv = [None] * (n + 1)
    for end in range(20, n + 1):
        bwv[end] = 4 * bbs[end] / bbm[end] if bbm[end] else 0
    # Stoch RSI on rv = rs[14:]
    r0 = next((i for i in range(n) if rs[i] is not None), n)
    rv = rs[r0:]
    raw = [None] * len(rv)
    for j in range(13, len(rv)):
        w = rv[j - 13:j + 1]; lo, hi = min(w), max(w)
        raw[j] = 0.5 if hi == lo else (rv[j] - lo) / (hi - lo)
    kser = [None] * len(rv)
    for j in range(15, len(rv)):
        kser[j] = (raw[j] + raw[j - 1] + raw[j - 2]) / 3
    dser = [None] * len(rv)
    for j in range(17, len(rv)):
        dser[j] = (kser[j] + kser[j - 1] + kser[j - 2]) / 3
    vol = [x[5] for x in c]
    out = []
    for i in range(n):
        price = cl[i]; comp = {}; raw_ind = {}
        v = rs[i]
        if v is not None:
            comp["rsi"] = 1 if v <= 30 else -1 if v >= 70 else 0.5 if v >= 50 else -0.5
            raw_ind["rsi"] = v
        if first is not None and i - first + 1 >= 12:
            j = i - first
            h = hist[j]; cross = None
            for k in range(1, 4):
                a, b = hist[j - k], hist[j - k + 1]
                if a is not None and b is not None and (a <= 0 < b or a >= 0 > b):
                    cross = "bullish" if b > 0 else "bearish"; break
            comp["macd"] = (1 if h > 0 else -1) + (0.5 if cross == "bullish" else -0.5 if cross == "bearish" else 0)
            raw_ind["hist"] = h
        if e20[i] is not None and e50[i] is not None:
            a, b = e20[i], e50[i]
            comp["ema"] = 1 if price > a > b else -1 if price < a < b else (0.5 if price > b else -0.5)
            raw_ind["e20"], raw_ind["e50"] = a, b
        if tf == "1d" and e200[i] is not None:
            comp["ema200"] = 1 if price > e200[i] else -1
        if i + 1 >= 20:
            end = i + 1; m, sd = bbm[end], bbs[end]
            up, lo = m + 2 * sd, m - 2 * sd
            pb = (price - lo) / (up - lo) if up > lo else 0.5
            hb = [bwv[e] for e in range(max(20, end - 120), end + 1)]
            squeeze = len(hb) >= 40 and bwv[end] <= sorted(hb)[int(len(hb) * 0.2)]
            comp["bb"] = -0.5 if pb > 1 else 0.5 if pb < 0 else 0
            raw_ind["pb"], raw_ind["squeeze"] = pb, squeeze
        j = i - r0
        if 0 <= j and j + 1 >= 20 and kser[j] is not None and dser[j] is not None:
            K, D = kser[j] * 100, dser[j] * 100
            comp["stochrsi"] = 0.5 if K < 20 and K > D else -0.5 if K > 80 and K < D else 0
        if i >= 21 and all(vol[k] is not None for k in range(i - 21, i)):
            avg = sum(vol[i - 21:i - 1]) / 20
            if avg:
                ratio = vol[i - 1] / avg; up_c = c[i - 1][4] >= c[i - 1][1]
                comp["volume"] = (0.5 if up_c else -0.5) if ratio >= 1.5 else 0
                raw_ind["vratio"], raw_ind["vgreen"] = ratio, up_c
        mx = sum(MAXPTS[k] for k in comp)
        score = sum(comp.values()) / mx if mx else 0
        out.append({"t": c[i][0], "close": price, "comp": comp, "raw": raw_ind, "score": score, "ok": i + 1 >= 35})
    return out


def verify(c, tf, ser, samples=25):
    """Prove the per-bar series equals signals.analyze() on truncated history (no lookahead, same math)."""
    idx = random.Random(7).sample(range(60, len(c)), min(samples, max(0, len(c) - 60)))
    worst = 0
    for i in idx:
        a = S.analyze(c[:i + 1], tf)
        worst = max(worst, abs(a["score"] - round(ser[i]["score"], 3)))
    return worst


# ============================================================== events & forward returns
def atr(c, n=14):
    out = [None] * len(c)
    trs = []
    for i in range(len(c)):
        h, l = c[i][2], c[i][3]
        pc = c[i - 1][4] if i else c[i][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if i == n - 1:
            out[i] = sum(trs) / n
        elif i >= n:
            out[i] = (out[i - 1] * (n - 1) + trs[i]) / n
    return out


def events_for(ser, tf):
    """dict name -> (direction, [bar indices]) using transitions into the condition."""
    E = {}

    def add(name, d, cond):
        idx = [i for i in range(1, len(ser)) if ser[i]["ok"] and cond(i) and not cond(i - 1)]
        E[name] = (d, idx)
    g = lambda i, k: ser[i]["raw"].get(k)  # noqa: E731
    add("RSI ≤30 (oversold)", 1, lambda i: g(i, "rsi") is not None and g(i, "rsi") <= 30)
    add("RSI ≥70 (overbought)", -1, lambda i: g(i, "rsi") is not None and g(i, "rsi") >= 70)
    add("MACD bullish cross", 1, lambda i: g(i, "hist") is not None and g(i, "hist") > 0)
    add("MACD bearish cross", -1, lambda i: g(i, "hist") is not None and g(i, "hist") < 0)
    add("EMA20 crosses above EMA50", 1, lambda i: g(i, "e20") is not None and g(i, "e20") > g(i, "e50"))
    add("EMA20 crosses below EMA50", -1, lambda i: g(i, "e20") is not None and g(i, "e20") < g(i, "e50"))
    add("EMA uptrend stack", 1, lambda i: ser[i]["comp"].get("ema") == 1)
    add("EMA downtrend stack", -1, lambda i: ser[i]["comp"].get("ema") == -1)
    if tf == "1d":
        add("Price above EMA200", 1, lambda i: ser[i]["comp"].get("ema200") == 1)
        add("Price below EMA200", -1, lambda i: ser[i]["comp"].get("ema200") == -1)
    add("Close below lower Bollinger", 1, lambda i: g(i, "pb") is not None and g(i, "pb") < 0)
    add("Close above upper Bollinger", -1, lambda i: g(i, "pb") is not None and g(i, "pb") > 1)
    add("StochRSI turns up <20", 1, lambda i: ser[i]["comp"].get("stochrsi") == 0.5)
    add("StochRSI turns down >80", -1, lambda i: ser[i]["comp"].get("stochrsi") == -0.5)
    add("Volume ≥1.5× on green", 1, lambda i: ser[i]["comp"].get("volume") == 0.5)
    add("Volume ≥1.5× on red", -1, lambda i: ser[i]["comp"].get("volume") == -0.5)
    add("Bollinger squeeze (no direction)", 0, lambda i: bool(g(i, "squeeze")))
    add(f"{tf} score ≥ Buy", 1, lambda i: ser[i]["score"] >= 0.15)
    add(f"{tf} score ≤ Sell", -1, lambda i: ser[i]["score"] <= -0.15)
    return E


def fwd(closes, i, bars):
    j = i + bars
    return closes[j] / closes[i] - 1 if j < len(closes) else None


def measure(d, idx, closes, bars):
    rets = [r for r in (fwd(closes, i, bars) for i in idx) if r is not None]
    allr = [r for r in (fwd(closes, i, bars) for i in range(len(closes))) if r is not None]
    if not allr:
        return None
    base = sum(allr) / len(allr)
    n = len(rets)
    if n == 0:
        return {"n": 0}
    if d == 0:  # direction-free: does it precede bigger moves?
        a = sum(abs(r) for r in rets) / n
        b = sum(abs(r) for r in allr) / len(allr)
        return {"n": n, "avg_abs_move_pct": round(a * 100, 3), "base_abs_move_pct": round(b * 100, 3), "ratio": round(a / b, 2) if b else None}
    dr = [d * r for r in rets]
    avg = sum(dr) / n
    sd = (sum((x - avg) ** 2 for x in dr) / (n - 1)) ** 0.5 if n > 1 else 0
    edge = avg - d * base
    hit = sum(1 for x in dr if x > 0) / n
    base_hit = sum(1 for r in allr if d * r > 0) / len(allr)
    t = edge / (sd / math.sqrt(n)) if sd > 0 and n > 1 else 0
    return {"n": n, "hit_rate": round(hit, 3), "base_hit_rate": round(base_hit, 3), "avg_ret_pct": round(avg * 100, 3),
            "edge_pct": round(edge * 100, 3), "t": round(t, 2)}


# ============================================================== composite on the 4h grid
def composite(data, sers):
    """At each 4h close: 1h bar ending then, the 4h bar, the last CLOSED 1d bar; weights renormalized like signals.py."""
    h1 = {x["t"]: x for x in sers.get("1h", [])}
    d1 = sers.get("1d", [])
    d1_t = [x["t"] for x in d1]
    out = []
    import bisect
    for k, b4 in enumerate(sers["4h"]):
        T = b4["t"] + 4 * H  # close time
        parts = {}
        x1 = h1.get(T - H)
        if x1 and x1["ok"]:
            parts["1h"] = x1["score"]
        if b4["ok"]:
            parts["4h"] = b4["score"]
        j = bisect.bisect_right(d1_t, T - 86400) - 1  # daily bar whose close (t+1d) <= T
        if j >= 0 and d1[j]["ok"]:
            parts["1d"] = d1[j]["score"]
        if not parts:
            out.append(None); continue
        w = sum(S.TF_WEIGHTS[tf] for tf in parts)
        out.append(sum(S.TF_WEIGHTS[tf] * v for tf, v in parts.items()) / w)
    return out


# ============================================================== strategy simulation
def simulate(sig_bars, c_sig, c_path, tf_secs, time_stop_bars, label):
    """sig_bars: list of (bar_index, direction). Enter at next bar open; ATR stop/target; path on finer candles."""
    a = atr(c_sig)
    path_t = [x[0] for x in c_path]
    import bisect
    eq, trades, curve = 1.0, [], []
    busy_until = -1
    for i, d in sig_bars:
        if i + 1 >= len(c_sig) or c_sig[i][0] <= busy_until or a[i] is None:
            continue
        entry_t = c_sig[i + 1][0]
        entry = c_sig[i + 1][1]
        stop = entry - d * ATR_STOP * a[i]; tgt = entry + d * ATR_TGT * a[i]
        liq = entry * (1 - d / LEV)
        stop_beyond_liq = (stop <= liq) if d > 0 else (stop >= liq)
        end_t = entry_t + time_stop_bars * tf_secs
        k = bisect.bisect_left(path_t, entry_t)
        exit_p, exit_t, why = None, None, None
        while k < len(c_path) and c_path[k][0] < end_t:
            t, o, h, l, cl = c_path[k][:5]
            adverse = l if d > 0 else h
            if stop_beyond_liq and ((adverse <= liq) if d > 0 else (adverse >= liq)):
                exit_p, exit_t, why = liq, t, "liquidated"; break
            if (adverse <= stop) if d > 0 else (adverse >= stop):
                exit_p, exit_t, why = stop, t, "stop"; break
            fav = h if d > 0 else l
            if (fav >= tgt) if d > 0 else (fav <= tgt):
                exit_p, exit_t, why = tgt, t, "target"; break
            k += 1
        if exit_p is None:
            if k >= len(c_path):
                break  # not enough future data: drop the open trade (no lookahead into missing data)
            exit_p, exit_t, why = c_path[k][1], c_path[k][0], "time"
        move = d * (exit_p / entry - 1)
        r = max(-1.0, LEV * move - LEV * FEE * 2)   # return on margin, after fees
        eq += r                                      # fixed margin (= starting capital), no compounding
        trades.append({"t": entry_t, "dir": d, "ret": r, "why": why})
        if eq <= 0:                                  # ruin: account gone, stop trading
            eq = 0.0
            curve.append((exit_t, eq))
            break
        curve.append((exit_t, eq))
        busy_until = exit_t
    n = len(trades)
    wins = [x["ret"] for x in trades if x["ret"] > 0]; losses = [x["ret"] for x in trades if x["ret"] <= 0]
    peak, mdd = 1.0, 0.0
    for _, e in curve:
        peak = max(peak, e); mdd = min(mdd, (e - peak) / peak)  # drawdown in % of the running peak
    return {"name": label, "trades": n, "win_rate": round(len(wins) / n, 3) if n else None,
            "total_return_pct": round((eq - 1) * 100, 1), "max_drawdown_pct": round(mdd * 100, 1),
            "ruined": any(e <= 0 for _, e in curve),
            "avg_trade_pct": round(sum(x["ret"] for x in trades) / n * 100, 2) if n else None,
            "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
            "exits": {w: sum(1 for x in trades if x["why"] == w) for w in ("target", "stop", "time", "liquidated")},
            "curve": curve}


def hold_curve(c, t0, t1):
    pts = [x for x in c if t0 <= x[0] <= t1]
    if not pts:
        return {"total_return_pct": None, "max_drawdown_pct": None, "curve": []}
    p0 = pts[0][1]
    curve = [(x[0], x[4] / p0) for x in pts]
    peak, mdd = 1, 0
    for _, e in curve:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    return {"total_return_pct": round((curve[-1][1] - 1) * 100, 1), "max_drawdown_pct": round(mdd * 100, 1), "curve": curve}


def thin(curve, n=160):
    if len(curve) <= n:
        return [[int(t), round(v, 4)] for t, v in curve]
    step = len(curve) / n
    return [[int(curve[int(i * step)][0]), round(curve[int(i * step)][1], 4)] for i in range(n)] + [[int(curve[-1][0]), round(curve[-1][1], 4)]]


def step_curve(trade_curve, t0, t1):
    pts = [(t0, 1.0)] + [(t, e) for t, e in trade_curve]
    if pts[-1][0] < t1:
        pts.append((t1, pts[-1][1]))
    return pts


# ============================================================== component IC for weights (in-sample / out-of-sample)
def ic(xs, ys):
    n = len(xs)
    if n < 30:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5; sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else None


def main():
    refresh = "--refresh" in sys.argv
    t0 = time.time()
    with ThreadPoolExecutor(6) as ex:
        datas = dict(zip([c[0] for c in S.COINS], ex.map(lambda c: fetch(c, refresh), S.COINS)))
    print(f"data fetched in {time.time() - t0:.1f}s", file=sys.stderr)
    res = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "coins": {},
           "assumptions": {"leverage": LEV, "fee_per_side_pct": FEE * 100, "stop_atr": ATR_STOP, "target_atr": ATR_TGT,
                           "time_stop": "72h for 4h strategies, 10 days for daily", "sizing": "fixed margin = starting capital every trade (3x notional), NO compounding, one position per coin; equity = 1 + sum of per-trade returns on margin",
                           "entry": "open of the bar after the signal", "path": "1h candles when available (else the signal timeframe); stop assumed first if stop and target share a candle",
                           "events": "transitions into a condition; forward returns close-to-close; t-stat ignores overlap (optimistic)"}}
    horizons = {"1h": {"4h": 4, "24h": 24, "72h": 72}, "4h": {"4h": 1, "24h": 6, "72h": 18}, "1d": {"24h": 1, "72h": 3}}
    ic_rows = []
    for cid, sym, src, prod in S.COINS:
        d = datas[cid]
        sers, cov, ver = {}, {}, {}
        for tf in ("1h", "4h", "1d"):
            c = d[tf]
            if len(c) < 60:
                continue
            sers[tf] = series(c, tf)
            ver[tf] = verify(c, tf, sers[tf])
            cov[tf] = {"bars": len(c), "from": iso(c[0][0]), "to": iso(c[-1][0])}
        ind = {}
        for tf, ser in sers.items():
            closes = [x["close"] for x in ser]
            for name, (dirn, idx) in events_for(ser, tf).items():
                row = {"tf": tf, "signal": name, "direction": dirn}
                for hn, bars in horizons[tf].items():
                    row[hn] = measure(dirn, idx, closes, bars)
                ind.setdefault(tf, []).append(row)
            # component IC rows (score components vs 24h forward return), split 70/30 in time
            b24 = horizons[tf]["24h"]
            split = int(len(ser) * 0.7)
            for part, rng in (("is", range(0, split)), ("oos", range(split, len(ser)))):
                for wname, w in CANDIDATES.items():
                    xs, ys = [], []
                    for i in rng:
                        if not ser[i]["ok"]:
                            continue
                        f = fwd(closes, i, b24)
                        cp = ser[i]["comp"]
                        den = sum(w[k] * MAXPTS[k] for k in cp)
                        if f is None or not den:
                            continue
                        xs.append(sum(w[k] * v for k, v in cp.items()) / den); ys.append(f)
                    ic_rows.append({"coin": sym, "tf": tf, "part": part, "comp": "w:" + wname, "ic": ic(xs, ys), "n": len(xs)})
                for comp in COMPONENTS + ["score"]:
                    xs, ys = [], []
                    for i in rng:
                        if not ser[i]["ok"]:
                            continue
                        f = fwd(closes, i, b24)
                        v = ser[i]["score"] if comp == "score" else ser[i]["comp"].get(comp)
                        if f is None or v is None:
                            continue
                        xs.append(v); ys.append(f)
                    ic_rows.append({"coin": sym, "tf": tf, "part": part, "comp": comp, "ic": ic(xs, ys), "n": len(xs)})
        # composite labels + strategies on the 4h grid
        comp_score = composite(d, sers)
        c4 = d["4h"]
        closes4 = [x[4] for x in c4]
        lab = lambda s: None if s is None else S.label(s)  # noqa: E731
        comp_ev = {}
        for name, dirn, cond in [("Composite Strong Buy", 1, lambda s: s is not None and s >= 0.5), ("Composite ≥ Buy", 1, lambda s: s is not None and s >= 0.15),
                                 ("Composite ≤ Sell", -1, lambda s: s is not None and s <= -0.15), ("Composite Strong Sell", -1, lambda s: s is not None and s <= -0.5)]:
            idx = [i for i in range(1, len(comp_score)) if cond(comp_score[i]) and not cond(comp_score[i - 1])]
            comp_ev[name] = (dirn, idx)
        comp_rows = []
        for name, (dirn, idx) in comp_ev.items():
            row = {"tf": "composite (4h grid)", "signal": name, "direction": dirn}
            for hn, bars in horizons["4h"].items():
                row[hn] = measure(dirn, idx, closes4, bars)
            comp_rows.append(row)
        path = d["1h"] if len(d["1h"]) > 100 else c4
        strong = sorted([(i, 1) for i in comp_ev["Composite Strong Buy"][1]] + [(i, -1) for i in comp_ev["Composite Strong Sell"][1]])
        mild = sorted([(i, 1) for i in comp_ev["Composite ≥ Buy"][1]] + [(i, -1) for i in comp_ev["Composite ≤ Sell"][1]])
        ev4 = events_for(sers["4h"], "4h")
        macd4 = sorted([(i, 1) for i in ev4["MACD bullish cross"][1]] + [(i, -1) for i in ev4["MACD bearish cross"][1]])
        first_ok = next((i for i, s in enumerate(comp_score) if s is not None), 0)
        T0, T1 = c4[first_ok][0], c4[-1][0]
        strats = [simulate(strong, c4, path, 4 * H, 18, "Composite Strong Buy/Sell (4h)"),
                  simulate(mild, c4, path, 4 * H, 18, "Composite Buy/Sell (4h)"),
                  simulate(macd4, c4, path, 4 * H, 18, "4h MACD cross")]
        cd = d["1d"]; sd = sers["1d"]
        dev = events_for(sd, "1d")
        dsig = sorted([(i, 1) for i in dev["1d score ≥ Buy"][1]] + [(i, -1) for i in dev["1d score ≤ Sell"][1]])
        dstrat = simulate(dsig, cd, cd, 86400, 10, "Daily score Buy/Sell (1d, long history)")
        hold4 = hold_curve(path, T0, T1)
        holdd = hold_curve(cd, cd[35][0] if len(cd) > 35 else cd[0][0], cd[-1][0])
        for s_ in strats:
            s_["curve"] = thin(step_curve(s_["curve"], T0, T1))
        dstrat["curve"] = thin(step_curve(dstrat["curve"], holdd["curve"][0][0] if holdd["curve"] else 0, cd[-1][0]))
        res["coins"][cid] = {
            "symbol": sym, "source": d["source"], "coverage": cov, "verify_max_score_diff": ver,
            "indicators": ind, "composite": comp_rows,
            "strategies": strats + [dstrat],
            "hold": {"4h_period": {k: v for k, v in hold4.items() if k != "curve"} | {"curve": thin(hold4["curve"])},
                     "daily_period": {k: v for k, v in holdd.items() if k != "curve"} | {"curve": thin(holdd["curve"])}},
            "period": {"composite_from": iso(T0), "composite_to": iso(T1)},
        }
        print(f"{sym}: done ({', '.join(f'{k}:{v}' for k, v in ver.items())} max diff vs signals.analyze)", file=sys.stderr)

    # ---------------- weights proposal (in-sample) + out-of-sample check
    def mean_ic(part, comp, tf=None):
        v = [r["ic"] for r in ic_rows if r["part"] == part and r["comp"] == comp and r["ic"] is not None and (tf is None or r["tf"] == tf)]
        return (sum(v) / len(v), len(v), sum(1 for x in v if x > 0)) if v else (None, 0, 0)
    comp_table = []
    for comp in COMPONENTS + ["score"]:
        mi, ni, pi = mean_ic("is", comp); mo, no, po = mean_ic("oos", comp)
        comp_table.append({"component": comp, "is_mean_ic": None if mi is None else round(mi, 4), "is_positive": f"{pi}/{ni}",
                           "oos_mean_ic": None if mo is None else round(mo, 4), "oos_positive": f"{po}/{no}"})
    # proposal: weight ∝ max(0, in-sample mean IC) normalized to mean 1 over kept components
    pos = {r["component"]: max(0.0, r["is_mean_ic"] or 0) for r in comp_table if r["component"] != "score"}
    tot = sum(pos.values())
    kept = [k for k, v in pos.items() if v > 0]
    proposed = {k: round(v / tot * len(kept), 2) if tot else 1.0 for k, v in pos.items()}
    # OOS: does the weighted score beat the equal score?
    res["weights"] = {"components": comp_table, "proposed_weights": proposed, "method":
                      "Information coefficient (Pearson corr.) of each score component with the 24h forward return, per coin and timeframe; "
                      "in-sample = first 70% of each series, out-of-sample = last 30%. Proposed weight ∝ max(0, in-sample mean IC)."}
    cand = []
    for wname in CANDIDATES:
        mo, no, po = mean_ic("oos", "w:" + wname); mi, ni, pi = mean_ic("is", "w:" + wname)
        cand.append({"weights": wname, "is_mean_ic": None if mi is None else round(mi, 4), "is_positive": f"{pi}/{ni}",
                     "oos_mean_ic": None if mo is None else round(mo, 4), "oos_positive": f"{po}/{no}"})
    res["weights"]["candidates_oos"] = cand
    best = max(cand, key=lambda r: r["oos_mean_ic"] if r["oos_mean_ic"] is not None else -9)
    pos_n, tot_n = map(int, best["oos_positive"].split("/"))
    solid = best["weights"] != "equal" and (best["oos_mean_ic"] or 0) >= 0.02 and tot_n and pos_n / tot_n >= 0.7
    res["weights"]["evidence_solid"] = bool(solid)
    res["weights"]["solid_rule"] = "a non-equal weighting must reach out-of-sample mean IC >= 0.02 AND be positive in >= 70% of coin/timeframe series"

    # ranked indicator table per coin (24h horizon) + multiple-testing tally
    tests = sig_pos = sig_neg = 0
    for cid, c in res["coins"].items():
        rows = []
        for tf, lst in c["indicators"].items():
            for r in lst:
                m = r.get("24h")
                if not m or not m.get("n") or r["direction"] == 0:
                    continue
                rows.append({"tf": tf, "signal": r["signal"], "n": m["n"], "hit": m["hit_rate"], "base_hit": m["base_hit_rate"],
                             "edge_pct": m["edge_pct"], "t": m["t"], "small_sample": m["n"] < 30})
                if m["n"] >= 30:
                    tests += 1
                    if m["t"] >= 2: sig_pos += 1
                    if m["t"] <= -2: sig_neg += 1
        for r in c["composite"]:
            m = r.get("24h")
            if m and m.get("n"):
                rows.append({"tf": "composite", "signal": r["signal"], "n": m["n"], "hit": m["hit_rate"], "base_hit": m["base_hit_rate"],
                             "edge_pct": m["edge_pct"], "t": m["t"], "small_sample": m["n"] < 30})
        c["ranked"] = sorted(rows, key=lambda r: (r["small_sample"], -(r["t"] or 0)))
    res["multiple_testing"] = {"tests_with_n_ge_30": tests, "t_ge_2": sig_pos, "t_le_minus_2": sig_neg,
                               "expected_by_chance_each_side": round(tests * 0.023, 1),
                               "note": "With this many tests, ~2.3% per side would clear |t|>=2 by luck alone; overlapping forward windows make t-stats optimistic."}
    res["elapsed_s"] = round(time.time() - t0, 1)
    with open(OUT, "w") as f:
        json.dump(res, f, separators=(",", ":"))
    print(json.dumps({"written": OUT, "elapsed_s": res["elapsed_s"], "components": comp_table, "proposed": proposed,
                      "candidates_oos": cand, "evidence_solid": res["weights"]["evidence_solid"], "multiple_testing": res["multiple_testing"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
