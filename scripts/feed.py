#!/usr/bin/env python3
"""Atom feed (/feed.xml) for feed readers and aggregators. Called by build_pages.py on every build (so publish.sh keeps it
current); English only, stdlib only. Writes nothing itself: atom() returns the XML string.

Entries (newest first, at most MAX_ENTRIES): blog posts only, from blog/<slug>/index.html (hand-built), read from their head
meta (og:title, description, canonical, article:published_time / modified_time). A post appears only once its
published_time has passed, so a scheduled post is not announced early; the next build after that time adds it.
Since Oct 25, 2026 the feed carries no market updates or trade content.
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
TITLE = "Lumi Trades"
SUBTITLE = "Lumi's articles on x402 seller trust and AI-agent payments. Informational, not financial advice."
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPLIT = re.compile(r"(?<=[.;!?])\s+")


def clean(text):
    """Public-safe plain text: privacy scrub and no P&L label."""
    t = privacy.scrub_text(text or "") or ""
    t = i18n.no_pnl(t)
    t = " ".join(s for s in _SPLIT.split(t) if s).strip()
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


def entries(root, now_utc=None):
    now_utc = now_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    es = blog_posts(root, now_utc)
    es.sort(key=lambda e: (e["updated"], e["id"]), reverse=True)
    return es[:MAX_ENTRIES]


def atom(root, *_unused, now_utc=None):
    es = entries(root, now_utc)
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
           "  <rights>Informational, not financial advice.</rights>"]
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
