#!/usr/bin/env python3
"""
Suggest an optional breakdown (short) / breakout (long) entry for a trade idea, for strong trends only.

  python3 scripts/alt_entry.py                 # every pending idea: prints a proposal or why none is offered
  python3 scripts/alt_entry.py T009            # one idea
  python3 scripts/alt_entry.py --idea '{"coin":"stellar","direction":"short","entry_zone":{"low":0.18,"high":0.1815},
                                        "stop":0.1845,"targets":[0.17,0.166],"leverage":2,"conviction":"medium"}'
                                               # a draft idea before it is added to data/trades.json
  python3 scripts/alt_entry.py T009 --apply    # write the proposal into that PENDING idea (under state/lock)

Read-only unless --apply. Uses data/signals.json (trend gate), data/analysis.json (levels) and live 1h candles
(ATR for the stop buffer; falls back to a 0.6% buffer if the fetch fails). The tracker (track_trades.py) fills it.

Rules (kept conservative; see README "Breakdown / breakout entry"):
  * Trend gate = a strong DAILY trend on the idea's side (all three): 1d EMA stack (short: price < EMA20 < EMA50),
    1d price beyond EMA200, 1d signal label Sell/Strong Sell (long: Buy/Strong Buy). The 4h is not required: a
    pullback short is usually set up while the 4h bounces, and the breakdown close itself is the short-term confirmation.
    Otherwise no alt entry: the idea stays pullback-only, exactly as before.
  * Level ("base"): the nearest of the analysis.json supports and the 24h 1h-swing low below price (long: resistances /
    24h swing high above price) that lies between the entry zone and T1. Trigger = a COMPLETED 1h close beyond it
    (never a wick).
  * Stop: back on the other side of the level by max(0.75 x 1h ATR(14), 0.3% of the level).
  * max_fill: the worst 1h close still accepted = where R:R to T1 is still 1.5 (and at most 1 ATR past the level).
    If even a fill AT the level gives R:R < 1.5, nothing is offered.
  * Size: one leverage step below the idea (min 2x for leveraged ideas since 1x = spot; spot ideas stay 1x) and within
    the ~25%-of-margin stop cap; conviction one step lower. Shown as "smaller size" on the card.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import track_trades as tt  # noqa: E402

ROOT = os.path.dirname(HERE)
GATE_SHORT, GATE_LONG = ("Sell", "Strong Sell"), ("Buy", "Strong Buy")
DOWN_CONV = {"high": "medium", "medium": "low", "low": "low"}


def load(name):
    with open(os.path.join(ROOT, "data", name)) as f:
        return json.load(f)


def decimals(p):
    return max(0, 3 - math.floor(math.log10(abs(p)))) if p else 4


def rnd(x, dec, up):
    f = 10 ** dec
    return (math.ceil(x * f - 1e-9) if up else math.floor(x * f + 1e-9)) / f


def trend_gate(coin, direction, sig):
    c = (sig.get("coins") or {}).get(coin) or {}
    tf = c.get("timeframes") or {}
    d1, h4 = tf.get("1d") or {}, tf.get("4h") or {}
    ind = d1.get("indicators") or {}
    ema, e200 = (ind.get("ema") or {}).get("state", ""), (ind.get("ema200") or {}).get("state", "")
    short = direction == "short"
    checks = {
        "1d EMA stack": ("downtrend" in ema) if short else ("uptrend" in ema),
        "1d vs EMA200": ("below" in e200) if short else ("above" in e200),
        "1d label": d1.get("label") in (GATE_SHORT if short else GATE_LONG),
    }
    txt = f"1d {d1.get('label')} ({ema}; {e200}); 4h {h4.get('label')} - signals.json {sig.get('generated_utc')}"
    return all(checks.values()), [k for k, v in checks.items() if not v], txt, c.get("price")


def fetch_1h(coin):
    """Closed 1h candles [t, o, h, l, c, v] (signals.py sources), or None."""
    try:
        import signals as sg
        tup = next(x for x in sg.COINS if x[0] == coin)
        return sg.fetch(tup)[3]["1h"][:-1]
    except Exception:  # noqa: BLE001
        return None


def atr_swing(c1h, short):
    """(ATR(14) on 1h, 24h swing low (short) / high (long)) from closed 1h candles."""
    if not c1h or len(c1h) < 16:
        return None, None
    c = c1h[-15:]
    trs = [max(b[2] - b[3], abs(b[2] - a[4]), abs(b[3] - a[4])) for a, b in zip(c, c[1:])]
    last = c1h[-24:]
    return sum(trs) / len(trs), (min(x[3] for x in last) if short else max(x[2] for x in last))


def propose(t, sig, ana, price=None, c1h=None):
    """Returns {"offered": bool, "reason"/"alt_entry", ...} for one idea dict (pending or draft)."""
    coin, d = t["coin"], t["direction"]
    short = d == "short"
    ok, failed, trend, sprice = trend_gate(coin, d, sig)
    price = price or sprice
    if not ok:
        return {"offered": False, "reason": f"trend gate not met ({', '.join(failed)}): {trend}"}
    z = t.get("entry_zone") or {"low": t["entry"], "high": t["entry"]}
    t1 = float(t["targets"][0])
    if price is None:
        return {"offered": False, "reason": "no price"}
    if (price <= t1) if short else (price >= t1):
        return {"offered": False, "reason": f"price {price} is already past T1 {t1}: nothing left to enter for"}
    a = (ana.get("coins") or {}).get(coin) or {}
    edge = float(z["low"]) if short else float(z["high"])
    atr, swing = atr_swing(c1h if c1h is not None else fetch_1h(coin), short)
    lv = [float(x) for x in (a.get("support") if short else a.get("resistance")) or []]
    if swing:
        lv.append(float(f"{swing:.4g}"))
    if short:
        cands = sorted({x for x in lv if t1 < x < min(edge, price * 0.999)}, reverse=True)
    else:
        cands = sorted({x for x in lv if max(edge, price * 1.001) < x < t1})
    if not cands:
        return {"offered": False, "reason": f"no {'support' if short else 'resistance'} level (analysis.json or 24h swing {swing}) between the zone/price and T1 {t1}"}
    tried = []
    for lvl in cands:
        dec = decimals(lvl)
        buf = max(0.75 * atr, 0.003 * lvl) if atr else 0.006 * lvl
        stop = rnd(lvl + buf if short else lvl - buf, dec, up=short)
        # worst fill with R:R >= 1.5: short (f - t1) / (stop - f) >= 1.5  ->  f >= (t1 + 1.5 stop) / 2.5
        f_rr = (t1 + tt.ALT_MIN_RR * stop) / (1 + tt.ALT_MIN_RR)
        f_ext = lvl - (atr or 0.006 * lvl) if short else lvl + (atr or 0.006 * lvl)
        mf = max(f_rr, f_ext) if short else min(f_rr, f_ext)
        mf = rnd(mf, dec, up=short)  # rounded toward the level (conservative)
        if not ((mf < lvl * 0.999) if short else (mf > lvl * 1.001)):
            tried.append(f"{lvl}: R:R to T1 < {tt.ALT_MIN_RR} even near the level (stop {stop})")
            continue
        L0 = tt.lev_of(t)
        stop_pct = abs(mf - stop) / mf * 100
        # one step smaller; 1x means spot (long only), so leveraged ideas keep at least 2x
        floor_ = 1 if (L0 == 1 or t.get("market") == "spot") else 2
        L = max(floor_, min(L0 - 1, int(tt.STOP_LOSS_CAP_PCT // stop_pct)))
        side = "below" if short else "above"
        typ = "breakdown" if short else "breakout"
        alt = {
            "type": typ,
            "trigger": f"1h close {side} {lvl} ({'loses the support' if short else 'clears the resistance'}); fills at that close if it is not past {mf}",
            "trigger_rule": {"tf": "1h", "kind": "close_below" if short else "close_above", "level": lvl},
            "max_fill": mf, "stop": stop, "leverage": L,
            "conviction": DOWN_CONV.get(t.get("conviction") or "medium", "low"),
            "leverage_reason": f"{typ.capitalize()} entry: smaller than the pullback entry ({tt.lev_txt(L)} vs {tt.lev_txt(L0)}); stop {stop_pct:.1f}% from the worst fill -> {stop_pct * L:.1f}% of margin.",
            "size_note": "smaller size than the pullback entry: chasing a break, not fading into resistance" if short else "smaller size than the pullback entry: chasing a break, not buying support",
            "trend": trend, "level_source": "analysis.json" if lvl in [float(x) for x in (a.get("support") if short else a.get("resistance")) or []] else "24h 1h swing " + ("low" if short else "high"),
            "reasoning": (f"Strong {'down' if short else 'up'}trend ({trend.split(' - ')[0]}). If price {'falls' if short else 'runs'} without retesting "
                          f"{z['low']}-{z['high']}, a 1h close {side} the {lvl} {'support' if short else 'resistance'} is the entry. Stop {stop} = back "
                          f"{'above' if short else 'below'} the broken level ({'0.75x 1h ATR' if atr else '0.6%'} buffer). R:R to T1 {t1} from the worst fill {mf}: "
                          f"{tt.alt_rr(t, {'max_fill': mf, 'stop': stop})}."),
        }
        if t.get("expiry"):
            alt["expiry"] = t["expiry"]
        chk = dict(t, status="pending", alt_entry=alt, id=t.get("id", "draft"))
        issues = tt.alt_issues(chk)
        if issues:
            tried.append(f"{lvl}: {'; '.join(issues)}")
            continue
        return {"offered": True, "alt_entry": alt, "rr_to_t1_worst": tt.alt_rr(chk), "atr_1h": tt.sig(atr) if atr else None,
                "card_line": f"Or on a 1h close {side} {lvl} (fills to {mf}) · stop {stop} · {tt.lev_txt(L)}, smaller size",
                "other_levels_tried": tried}
    return {"offered": False, "reason": "no level gives R:R >= 1.5 to T1: " + " | ".join(tried)}


def main(argv):
    sig, ana = load("signals.json"), load("analysis.json")
    if "--idea" in argv:
        idea = json.loads(argv[argv.index("--idea") + 1])
        idea.setdefault("id", "draft")
        print(json.dumps(propose(idea, sig, ana), indent=1, ensure_ascii=False))
        return 0
    ids = [a for a in argv if not a.startswith("--")]
    apply = "--apply" in argv
    if apply and len(ids) != 1:
        print("--apply needs exactly one trade id", file=sys.stderr)
        return 2
    trades = load("trades.json")["trades"]
    sel = [t for t in trades if (t["id"] in ids if ids else t.get("status") == "pending")]
    out = {t["id"]: (propose(t, sig, ana) if t.get("status") == "pending" else {"offered": False, "reason": f"status {t.get('status')}: only pending ideas"})
           for t in sel}
    if apply:
        tid = ids[0]
        res = out.get(tid) or {}
        if not res.get("offered"):
            print(json.dumps(out, indent=1, ensure_ascii=False))
            print(f"not applied: {res.get('reason', 'unknown id')}", file=sys.stderr)
            return 1
        with tt.file_lock():
            doc = tt.load_trades()
            t = next(x for x in doc["trades"] if x["id"] == tid)
            if t.get("status") != "pending" or t.get("alt_entry"):
                print(f"not applied: {tid} is {t.get('status')} / already has an alt_entry", file=sys.stderr)
                return 1
            t["alt_entry"] = res["alt_entry"]
            tt.save_trades(doc)
        print(f"applied alt_entry to {tid}; run python3 scripts/track_trades.py and check slate_warnings", file=sys.stderr)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
