"""/blog/: English-only index of the hand-built posts in blog/<slug>/index.html (newest first). Built by build_pages.py
on the English pass so the refresh keeps it. Reads each post's <h1>, meta description and <time datetime>."""
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def posts(root=ROOT):
    out = []
    bdir = os.path.join(root, "blog")
    if not os.path.isdir(bdir):
        return out
    for d in sorted(os.listdir(bdir)):
        p = os.path.join(bdir, d, "index.html")
        if not os.path.isfile(p):
            continue
        s = open(p, encoding="utf-8").read()
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
        desc = re.search(r'<meta name="description" content="([^"]*)"', s)
        t = re.search(r'<time datetime="([0-9-]{10})"[^>]*>(.*?)</time>', s, re.S)
        if not h1:
            continue
        out.append({"slug": d, "title": html.unescape(re.sub(r"<[^>]+>", "", h1.group(1)).strip()),
                    "desc": html.unescape(desc.group(1)) if desc else "", "date": t.group(1) if t else "",
                    "date_txt": html.unescape(re.sub(r"<[^>]+>", "", t.group(2)).strip()) if t else ""})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def page(h, tp, V, gen_date, root=ROOT):
    E = h.E
    ps = posts(root)
    url = h.SITE + "blog/"
    title = "Blog | Lumi Trades"
    desc = "Articles from Lumi Trades on AI agents, x402 payments and how to check who delivers before your agent pays."
    ld = json.dumps([{"@context": "https://schema.org", "@type": "Blog", "name": "Lumi Trades blog", "url": url, "inLanguage": "en",
                      "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": f'{url}{p["slug"]}/', "datePublished": p["date"]} for p in ps]}],
                    ensure_ascii=False).replace("</", "<\\/")
    def item(p):
        when = f'<time datetime="{E(p["date"])}">{E(p["date_txt"])}</time>' if p["date"] else ""
        return (f'<li class="bi-post"><a href="{E(p["slug"])}/"><b>{E(p["title"])}</b></a>{when}'
                f'<span>{E(p["desc"])}</span><a class="bi-more" href="{E(p["slug"])}/">Read the article →</a></li>')
    items = "".join(item(p) for p in ps) or "<li>No posts yet.</li>"
    nav = tp.site_nav(h, "../", "", "blog")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#070a10">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Lumi">
<meta property="og:title" content="Lumi Trades blog">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{h.SITE}assets/og.png?v={V}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@lumisinsite">
<meta name="twitter:title" content="Lumi Trades blog">
<meta name="twitter:description" content="{E(desc)}">
<meta name="twitter:image" content="{h.SITE}assets/og.png?v={V}">
<link rel="alternate" type="application/atom+xml" title="Lumi Trades" href="{h.SITE}feed.xml">
<link rel="icon" href="../favicon.ico?v={V}" sizes="any">
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png?v={V}" sizes="180x180">
<link rel="preload" href="../assets/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../assets/fonts/sora-var.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/style.css?v={V}">
<link rel="stylesheet" href="../assets/glow.css?v={V}">
<script src="../assets/live.js?v={V}" defer></script>
<script src="../assets/ticker.js?v={V}" defer></script>
<script type="application/ld+json">{ld}</script>
<style>
.bi-main{{max-width:728px;padding-top:14px;padding-bottom:28px}}
.bi-main h1{{font-family:"Sora",var(--sans);font-size:clamp(1.7rem,5.2vw,2.4rem);line-height:1.18;margin:6px 0 8px}}
.bi-list{{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:12px}}
.bi-post{{display:grid;gap:6px;padding:18px;border:1px solid var(--line2);border-radius:var(--radius);background:rgba(255,255,255,.02)}}
.bi-post b{{font-family:"Sora",var(--sans);font-size:1.2rem;line-height:1.3;color:var(--text)}}
.bi-post time{{color:var(--dim);font-size:.85rem}}
.bi-post span{{color:var(--muted);line-height:1.6}}
.bi-more{{color:var(--cyan);font-size:.9rem}}
</style>
<!-- Cloudflare Web Analytics --><script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "0212d2464cb04c11b35401da715265c6"}}'></script><!-- End Cloudflare Web Analytics -->
</head>
<body class="cp tp lgw">
<div class="bg-glow" aria-hidden="true"></div>
<header class="cp-top"><div class="wrap cp-top-inner">
  <a class="cp-brand" href="../"><img class="wm" src="../assets/brand/wordmark.png?v={V}" alt="Lumi" width="80" height="42"><span class="sr-only"> Trades</span></a>
  <span class="cp-top-r"><a class="cp-dash" href="../trust/">Vendor trust list →</a>{tp.social_icons(h)}</span>
</div></header>
<div class="ticker lt-ticker" role="region" aria-label="Live crypto prices"><div class="ticker-track" id="ticker"></div></div>
<nav class="nav" aria-label="Site"><div class="wrap nav-inner">{nav}</div></nav>
<main class="wrap cp-main bi-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › Blog</p>
<h1>Blog</h1>
<p class="muted">Notes from Lumi on AI agents, x402 payments and checking who delivers before your agent pays.</p>
<ul class="bi-list">{items}</ul>
</main>
<footer class="wrap footer">
  {tp.foot_brand(h)}
  <p class="foot-soc">{tp.social_icons(h)}</p>
  <p>Times in US Central · Page generated {E(gen_date)} · Not financial advice. · <a href="../privacy/">Privacy Policy</a> · <a href="../trust-policy/">Conflicts policy</a></p>
</footer>
</body>
</html>
"""


def build(h, tp, V, gen_date, write, root=ROOT):
    """Writes blog/index.html when there is at least one post. Returns True if written."""
    if not posts(root):
        return False
    write("blog/index.html", page(h, tp, V, gen_date, root))
    return True
