#!/usr/bin/env python3
"""Atom feed (/feed.xml) for feed readers and aggregators. Called by build_pages.py on every build (so publish.sh keeps it
current); English only, stdlib only. Writes nothing itself: atom() returns the XML string.

Entries (newest first, at most MAX_ENTRIES):
- blog posts: blog/<slug>/index.html (hand-built), read from their head meta (og:title, description, canonical,
  article:published_time / modified_time). A post appears only once its published_time has passed, so a scheduled
  post (e.g. a 10 AM drop) is not announced early; the next build after that time adds it.
- Lumi's market updates: data/log.json entries with kind "analysis" (the tracker's "auto" lines are left out).
- active paper-trade ideas (pending/open) from data/trades.json, linking to /trades/<ID>/: the plan only (direction,
  leverage, entry zone, stop, targets). Never a fill result, P&L, outcome or the record (the track record is private).
Every free-text field goes through privacy.scrub_text + i18n.no_pnl, plus an extra sentence filter for target/stop events.
`updated` values come from the data, never from the clock, so an unchanged input gives a byte-identical feed (no churn).
"""
import datetime as dt
import html
import os
import re
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

import i18n
import privacy

SITE = "https://lumitrades.io/"
FEED_URL = SITE + "feed.xml"
FEED_ID = "tag:lumitrades.io,2026:feed"
MAX_ENTRIES = 30
MAX_ANALYSIS = 20
TITLE = "Lumi Trades"
SUBTITLE = ("Lumi's articles, market updates and active paper-trade ideas. "
            "Paper-trade analysis, not investment advice. Lumi does not trade real money.")
NOTICE = "Paper-trade analysis, not investment advice. Lumi does not trade real money."
# extra guard on top of privacy.scrub_text: no sentence about a target/stop event or a fill result reaches the feed
EVENT = re.compile(r"\b(?:target\s*\d?\s*hit|T[12]\s+(?:was\s+)?hit|hit\s+T[12]|breakeven|break-even|stopped|stop\s+moved"
                   r"|filled|unfilled|expired|invalidated|cancel+ed|closed|exited|P&L|win\s*rate|track\s+record|scorecard)\b", re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPLIT = re.compile(r"(?<=[.;!?])\s+")


def clean(text):
    """Public-safe plain text: privacy scrub, no P&L label, no sentence about a target/stop event."""
    t = privacy.scrub_text(text or "") or ""
    t = i18n.no_pnl(t)
    t = " ".join(s for s in _SPLIT.split(t) if s and not EVENT.search(s)).strip()
    return _CTRL.sub("", t)


def ts(iso):
    """ISO string (Z, offset or naive = US Central) -> RFC 3339 UTC 'YYYY-MM-DDTHH:MM:SSZ', or None."""
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=ZoneInfo("America/Chicago"))
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta(src, attr, name):
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', src)
    return html.unescape(m.group(1)) if m else None


def blog_posts(root, now_utc):
    out = []
    bdir = os.path.join(root, "blog")
    if not os.path.isdir(bdir):
        return out
    for d in sorted(os.listdir(bdir)):
        p = os.path.join(bdir, d, "index.html")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            head = f.read().split("</head>", 1)[0]
        if re.search(r'<meta name="robots" content="[^"]*noindex', head):
            continue
        pub = ts(_meta(head, "property", "article:published_time"))
        if not pub or pub > now_utc:
            continue  # unpublished or scheduled for later: not in the feed yet
        title = _meta(head, "property", "og:title") or (re.search(r"<title>([^<]*)</title>", head) or [None, d])[1]
        m = re.search(r'<link rel="canonical" href="([^"]+)"', head)
        out.append({"id": f"tag:lumitrades.io,2026:blog/{d}", "title": html.unescape(title), "link": m.group(1) if m else f"{SITE}blog/{d}/",
                    "published": pub, "updated": ts(_meta(head, "property", "article:modified_time")) or pub,
                    "summary": clean(_meta(head, "name", "description") or ""), "category": "Articles"})
    return out


def analysis_entries(log):
    out = []
    for e in (log or {}).get("entries", []):
        if e.get("kind") != "analysis":
            continue
        when = ts(e.get("t"))
        text = clean(e.get("text"))
        if not when or not text:
            continue
        ct = dt.datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        ct = ct.astimezone(ZoneInfo("America/Chicago"))
        label = ct.strftime("%b %-d, %-I:%M %p ") + ct.tzname()
        out.append({"id": f"tag:lumitrades.io,2026:update/{when}", "title": f"Lumi market update, {label}",
                    "link": SITE + "#markets", "published": when, "updated": when,
                    "summary": text + " " + NOTICE, "category": "Market updates"})
        if len(out) >= MAX_ANALYSIS:
            break
    return out


def idea_entries(trades, symbols, lvl):
    out = []
    for t in (trades or {}).get("trades", []):
        if t.get("status") not in ("pending", "open") or not t.get("id"):
            continue
        when = ts(t.get("opened_at"))
        if not when:
            continue
        sym = symbols.get(t.get("coin"), str(t.get("coin", "")).upper())
        d = "long" if t.get("direction") == "long" else "short"
        spot = t.get("market") == "spot" or t.get("leverage") == 1
        lev = "spot" if spot else f'{t.get("leverage")}x'
        z = t.get("entry_zone") or {}
        tg = " / ".join(lvl(x) for x in (t.get("targets") or []))
        zone = f'{lvl(z.get("low"))}–{lvl(z.get("high"))}' if z.get("low") is not None else lvl(t.get("entry"))
        summary = (f'Lumi posted paper-trade idea {t["id"]}: {sym} {d} ({lev}). Entry zone {zone}, stop {lvl(t.get("stop"))}'
                   + (f", targets {tg}" if tg else "") + f". Status and chart on the idea page. {NOTICE}")
        out.append({"id": f'tag:lumitrades.io,2026:idea/{t["id"]}', "title": f'Paper-trade idea {t["id"]}: {sym} {d} ({lev})',
                    "link": f'{SITE}trades/{t["id"]}/', "published": when, "updated": when, "summary": summary,
                    "category": "Paper-trade ideas"})
    return out


def entries(root, log, trades, symbols, lvl, now_utc=None):
    now_utc = now_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    es = blog_posts(root, now_utc) + analysis_entries(log) + idea_entries(trades, symbols, lvl)
    es.sort(key=lambda e: (e["updated"], e["id"]), reverse=True)
    return es[:MAX_ENTRIES]


def atom(root, log, trades, symbols, lvl, now_utc=None):
    es = entries(root, log, trades, symbols, lvl, now_utc)
    x = lambda s: escape(str(s), {'"': "&quot;"})
    updated = max((e["updated"] for e in es), default="2026-10-21T00:00:00Z")
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en">',
           f"  <title>{x(TITLE)}</title>",
           f"  <subtitle>{x(SUBTITLE)}</subtitle>",
           f'  <link rel="self" type="application/atom+xml" href="{FEED_URL}"/>',
           f'  <link rel="alternate" type="text/html" href="{SITE}"/>',
           f"  <id>{FEED_ID}</id>",
           f"  <updated>{updated}</updated>",
           f"  <author><name>Lumi</name><uri>{SITE}</uri></author>",
           f"  <icon>{SITE}favicon.ico</icon>",
           f"  <logo>{SITE}assets/brand/logo.png</logo>",
           "  <rights>Paper-trade analysis, not investment advice.</rights>"]
    for e in es:
        out += ["  <entry>",
                f"    <title>{x(e['title'])}</title>",
                f'    <link rel="alternate" type="text/html" href="{x(e["link"])}"/>',
                f"    <id>{x(e['id'])}</id>",
                f"    <published>{e['published']}</published>",
                f"    <updated>{e['updated']}</updated>",
                f'    <category term="{x(e["category"])}"/>',
                f"    <summary type=\"text\">{x(e['summary'])}</summary>",
                "  </entry>"]
    out += ["</feed>", ""]
    return "\n".join(out)
