#!/usr/bin/env python3
"""
Daily brief + event calendar for the Lumi API (api.lumitrades.io /v1/brief, /v1/events) -> data/brief.json, data/events.json.
  python3 scripts/brief.py            (context.py runs it after every context refresh; stdlib only, no network)
Inputs (all optional; a missing input is simply left out, nothing is invented):
  - newsletter: newest dated *.md in $LUMI_NEWSLETTER_DIR (default ../newsletter next to this repo): subject, preview, TL;DR and the
    "What happened" / "Levels I'm watching" / "What's next" bullets (markdown, links kept).
  - news:   $LUMI_NEWS_JSON   (default ../shorts/notes/news.json): the sourced "Institutional Watch" items of the 12:30 PM Short
            (schema: ../shorts/notes/README.md; old keys why/coins and new keys why_it_matters/tokens both read).
  - events: $LUMI_EVENTS_JSON (default ../shorts/notes/events.json): sourced, dated macro/crypto events (at_ct = America/Chicago).
    Rows are converted to UTC and kept for 3 days after they happen; the API filters upcoming vs. recent at request time.
Only facts already published in the newsletter/Shorts are copied. Personal-holdings wording is dropped here, and the API's
privacy filter (PRIVATE_NAMES) runs again on every paid response.
"""
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(ROOT)
NEWSLETTER_DIR = os.environ.get("LUMI_NEWSLETTER_DIR", os.path.join(WS, "newsletter"))
NEWS_JSON = os.environ.get("LUMI_NEWS_JSON", os.path.join(WS, "shorts", "notes", "news.json"))
EVENTS_JSON = os.environ.get("LUMI_EVENTS_JSON", os.path.join(WS, "shorts", "notes", "events.json"))
CT = ZoneInfo("America/Chicago")
NOW = datetime.now(timezone.utc)
KEEP_SECTIONS = {"what happened": "what_happened", "levels i'm watching": "levels", "levels i’m watching": "levels",
                 "what's next": "whats_next", "what’s next": "whats_next"}
PERSONAL = re.compile(r"\b(my|our|personal)\s+(own\s+)?(holdings?|bags?|stack|portfolio|positions?)\b|\buser[- ]specified\b", re.I)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def newsletter():
    files = sorted(f for f in glob.glob(os.path.join(NEWSLETTER_DIR, "*.md")) if re.match(r"\d{4}-\d{2}-\d{2}", os.path.basename(f)))
    if not files:
        return None
    path = files[-1]
    text = open(path, encoding="utf-8").read()
    fm = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
        text = text[m.end():]
    out = {"date": fm.get("date") or os.path.basename(path)[:10], "subject": fm.get("subject"), "preview": fm.get("preview")}
    t = re.search(r"\*\*TL;DR:\*\*\s*(.+)", text)
    if t:
        out["tldr"] = t.group(1).strip()
    sec = None
    for line in text.splitlines():
        h = re.match(r"^##\s+(.+)", line)
        if h:
            sec = KEEP_SECTIONS.get(h.group(1).strip().lower())
            continue
        b = re.match(r"^\s*[-*]\s+(.+)", line)
        if sec and b and not PERSONAL.search(b.group(1)):
            out.setdefault(sec, []).append(b.group(1).strip())
    out["source"] = "Trade with Lumi newsletter"
    return {k: v for k, v in out.items() if v}


def news():
    d = load(NEWS_JSON)
    if not d or not isinstance(d.get("items"), list) or d.get("sample"):
        return None  # sample files hold placeholder items, never publish them
    items = []
    for it in d["items"]:
        if not it.get("headline") or not it.get("source_url"):
            continue  # only sourced items
        it = dict(it, why=it.get("why_it_matters") or it.get("why"), coins=it.get("tokens") or it.get("coins"))
        row = {k: it[k] for k in ("date", "headline", "summary", "why", "coins", "source_name", "source_url",
                                  "institution", "category") if it.get(k)}
        if it.get("use_case_match"):
            row["use_case_match"] = True  # the token's stated use case matches; not a confirmed partnership
        items.append(row)
    return {"date": d.get("date"), "items": items} if items else None


def events():
    d = load(EVENTS_JSON)
    rows = []
    for e in (d or {}).get("events", []):
        try:
            at = datetime.fromisoformat(e["at_ct"]).replace(tzinfo=CT)
        except Exception:
            continue
        if at < NOW - timedelta(days=3) or not (e.get("source") or e.get("url")):
            continue
        row = {"at_utc": iso(at), "at_ct": e["at_ct"], "title": e.get("short"), "why": e.get("why"),
               "source": e.get("source"), "url": e.get("url"), "url2": e.get("url2")}
        rows.append({k: v for k, v in row.items() if v})
    rows.sort(key=lambda r: r["at_utc"])
    return rows


def write(name, obj):
    out = os.path.join(ROOT, "data", name)
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, out)


def main():
    ev = events()
    write("events.json", {
        "_readme": "GENERATED by scripts/brief.py from the Shorts' sourced event notes. Times in UTC (at_utc) and US Central (at_ct). "
                   "Only dated, sourced items; kept 3 days after they happen.",
        "generated_utc": iso(NOW), "events": ev})
    brief = {"_readme": "GENERATED by scripts/brief.py: the latest newsletter's headline facts + the Shorts' sourced news items. "
                        "Live numbers (prices, Fear & Greed, levels, trades) come from the other data/*.json files.",
             "generated_utc": iso(NOW)}
    nl, nw = newsletter(), news()
    if nl:
        brief["newsletter"] = nl
    if nw:
        brief["news"] = nw
    write("brief.json", brief)
    print(f"brief: events={len(ev)} newsletter={'yes' if nl else 'no'} news={len(nw['items']) if nw else 0}", file=sys.stderr)


if __name__ == "__main__":
    main()
