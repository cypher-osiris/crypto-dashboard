#!/usr/bin/env python3
"""Keep paper-trade results out of the public data files (the track record is private since Oct 22, 2026).

  python3 scripts/privacy.py              # takes state/lock, then scrubs data/trades.json, data/log.json, data/analysis.json
  python3 scripts/privacy.py --lock-held  # same, for callers that already hold state/lock (scripts/publish.sh)
  python3 scripts/privacy.py --check      # report what would change, write nothing
  add --paths to print the rewritten files on stdout (publish.sh stages them)

What it does:
- data/trades.json: closed ideas lose their exit price, P&L and outcome (status becomes "closed"); the full doc is
  kept in state/trades_full.json (git-ignored) by scripts/track_trades.py (load_trades/save_trades).
- Prose (log entries, analysis commentary, idea reasoning/notes): sentences that state a paper-trade result
  ("T004 ... stopped at 0.00219 (-19.2% at 3x)", "win rate: 0.0%", "closed: 5", ...) are dropped, and tracker lines
  "T005 AXL closed STOPPED at 0.0505 (...)" become "T005 AXL idea closed". Plan prose (risk/targets at 3x) stays.
The same scrub runs where the data is written (track_trades.py, update_prices.py) and again on every publish.
"""
import json
import os
import re
import sys

TID = r"\bT\d{3}[a-z]?\b"
RES = (r"(?:stopped|stop(?:ped)?\s+out|took\s+out|taken\s+out|won(?!['’]t)|lost|closed\s+(?:as\s+)?(?:WON|LOST|STOPPED|EXPIRED|CLOSED)"
       r"|hit\s+(?:its|the)\s+stop|realized|result(?:s|ed)?)")
BAD = [
    re.compile(TID + r"[^()]{0,90}?\b" + RES + r"\b", re.I),
    re.compile(r"\b" + RES + r"\b[^()]{0,70}?" + TID, re.I),
    re.compile(TID + r".{0,120}?\b(?:stopped|won(?!['’]t)|lost)\b.{0,40}?[+\-−]\d", re.I),
    re.compile(r"\b(?:win\s*rate|track\s+record|scorecard|cumulative\s+(?:paper\s+)?P&L|equity\s+curve|hit\s+rate)\b", re.I),
    re.compile(r"\b(?:stopped|won(?!['’]t)|lost|closed)\b.{0,80}?[+\-−]\d+(?:\.\d+)?%\s*(?:at\s*\d+x|on\s+margin)", re.I),
    re.compile(r"\b\d+\s*W\s*/\s*\d+\s*L\b"),
    re.compile(r"^\W*closed:\s*\d+", re.I),
    re.compile(r"\bstays?\s+as\s+recorded\b", re.I),
]
CLOSE_EV = re.compile(r"(" + TID + r") (\(?\w+\)?)(?: (?:long|short) (?:[\d.]+x|spot))? closed (?:as )?(?:WON|LOST|STOPPED|EXPIRED|CLOSED)\b[^;]*?(?=;|\.(?:\s|$)|$)")
SPLIT = re.compile(r"(?<=[.;])\s+")


def scrub_text(text):
    """Text minus any statement of a paper-trade result. Returns '' when nothing is left."""
    if not isinstance(text, str) or not text:
        return text
    t = CLOSE_EV.sub(lambda m: f"{m.group(1)} {m.group(2).strip('()')} idea closed", text)
    segs = SPLIT.split(t)
    keep = []
    for s in segs:
        if any(r.search(s) for r in BAD):
            if keep and keep[-1].endswith(";") and s.rstrip().endswith("."):
                keep[-1] = keep[-1][:-1] + "."  # "a; <dropped>." -> "a."
            continue
        keep.append(s)
    out = " ".join(keep).strip()
    if out.endswith(";"):
        out = out[:-1] + "."
    if re.fullmatch(r"(?:Trade events|Trades):\s*\.?", out):
        return ""
    return out


SKIP_KEYS = {"id", "coin", "status", "direction", "source", "url", "t", "kind", "author", "type", "symbol", "slug"}


def scrub_obj(o, key=None):
    if isinstance(o, dict):
        return {k: (v if k in SKIP_KEYS else scrub_obj(v, k)) for k, v in o.items()}
    if isinstance(o, list):
        return [scrub_obj(v, key) for v in o]
    if isinstance(o, str) and len(o) > 12:
        return scrub_text(o)
    return o


def scrub_log(log):
    out = []
    for e in log.get("entries", []):
        txt = scrub_text(e.get("text", ""))
        if txt:
            out.append({**e, "text": txt})
    return {**log, "entries": out}


def _jdump_analysis(path, obj):
    """data/analysis.json keeps its hand-edit format: indent=1, ASCII escapes, no trailing newline."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def run(check=False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import track_trades as tt
    changed = []
    # trades: merge any hand edits into the private doc, write the public view (scrubbed, no closed outcomes)
    full = tt.load_trades()
    pub_before = tt.load("trades.json", {"trades": []})
    priv_before = None
    if os.path.exists(tt.PRIVATE_TRADES):
        with open(tt.PRIVATE_TRADES) as f:
            priv_before = json.load(f)
    if tt.public_view(full) != pub_before or full != priv_before:
        if check:
            changed.append("state/trades.json (private)")
        else:
            tt.save_trades(full)
    for name, fn in (("log.json", scrub_log), ("analysis.json", scrub_obj)):
        p = os.path.join(tt.DATA, name)
        if not os.path.exists(p):
            continue
        with open(p) as f:
            raw = f.read()
        d = json.loads(raw)
        nd = fn(d)
        if nd != d:
            changed.append("data/" + name)
            if not check:
                if name == "analysis.json":
                    _jdump_analysis(p, nd)
                else:
                    tt.save(name, nd)
    return changed


if __name__ == "__main__":
    check = "--check" in sys.argv
    if "--lock-held" in sys.argv or check:
        ch = run(check)
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import track_trades as tt
        with tt.file_lock():
            ch = run()
    print(("would change: " if check else "privacy: scrubbed ") + (", ".join(ch) if ch else "nothing"), file=sys.stderr)
    if "--paths" in sys.argv:  # for scripts/publish.sh: the files it rewrote, one per line
        print("\n".join(ch))
