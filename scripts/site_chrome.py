"""Shared chrome for every generated page (head, header, nav, footer, social icons). stdlib only.

Trust-only since Oct 25, 2026: the market / trading section (coin pages, trade ideas, signals, newsletter, price ticker,
exchange referral links) was retired, so there is no "Markets" nav group, no ticker and no referral footer. Called by
scripts/build_pages.py and the page modules it drives (site_pages, how_page, privacy_page, policy_page, contact_page,
top_sellers_page, seller_pages, blog_index) as `tp`.
"""
import json


def page_head(h, title, desc, url, V, path, kind="article", extra_ld=None, keywords=None):
    ld = json.dumps(extra_ld or [], ensure_ascii=False).replace("</", "<\\/")
    kw = f'<meta name="keywords" content="{h.E(keywords)}">\n' if keywords else ""
    return f"""<!doctype html>
<html lang="{h.L.code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h.E(title)}</title>
<meta name="description" content="{h.E(desc)}">
{kw}<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{url}">
{h.head_i18n(path, h.langs)}
<meta name="theme-color" content="#070a10">
<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="Lumi">
<meta property="og:title" content="{h.E(title.replace(' | Lumi Trades', ''))}">
<meta property="og:description" content="{h.E(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{h.SITE}assets/og.png?v={V}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@Lumisinsite">
<meta name="twitter:title" content="{h.E(title.replace(' | Lumi Trades', ''))}">
<meta name="twitter:description" content="{h.E(desc)}">
<meta name="twitter:image" content="{h.SITE}assets/og.png?v={V}">
"""+ "{ASSETS}" + f"""<script type="application/ld+json">{ld}</script>
</head>
"""


# Shared site chrome for every generated page. Trust pages only: the market/trading section was retired on Oct 25, 2026.
FOOT_BRAND = "<b>Lumi Trades</b>: independent test-buys of x402 sellers, with receipts anyone can check. Informational test evidence only, not financial advice."
# Legal SF1: every "independent" claim sits next to the material-connection disclosure and the conflicts policy link.
FOOT_INDEP = "Lumi is independent of the sellers it tests: no seller pays for a score (see our <a href=\"{href}\">conflicts policy</a>)."
TRUST_METHOD = "trust-policy/#score"   # nav "How it works" = how the trust score works (policy_page.SECTIONS "score")
HOW_TESTS = "How Lumi tests x402 sellers"   # title of /how-it-works/ (scripts/how_page.py)


def blog_href(h, home):
    """/blog/ is English-only at the site root: one level above a language home."""
    L = getattr(h, "L", None)
    return f'{home}{"../" if L is not None and L.prefix else ""}blog/'


def site_nav(h, home, coins="", current=None):
    """Top nav links (inside .nav-inner): trust pages only. `coins` is ignored (kept for old callers)."""
    E, _ = h.E, h._
    cur = lambda c: ' aria-current="page"' if current == c else ""
    return (f'<a href="{home}">{E(_("Home"))}</a>'
            f'<a href="{home}trust/"{cur("trust")}>{E(_("Vendor trust"))}</a>'
            f'<a href="{home}agents/"{cur("agents")}>{E(_("For AI agents"))}</a>'
            f'<a href="{home}{TRUST_METHOD}"{cur("policy")}>{E(_("How it works"))}</a>'
            f'<a href="{blog_href(h, home)}"{cur("blog")}>{E(_("Blog"))}</a>')


# Social icons (X, YouTube, TikTok): header of generated pages + every footer. Same handles as the text links.
SOCIAL_SVG = {
    "x": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "yt": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31.6 31.6 0 0 0 0 12a31.6 31.6 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31.6 31.6 0 0 0 24 12a31.6 31.6 0 0 0-.5-5.8zM9.6 15.6V8.4l6.2 3.6z"/></svg>',
    "tt": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>',
}


def social_icons(h, cls="soc"):
    E, _ = h.E, h._
    items = (("x", "https://x.com/Lumisinsite", _("Lumi on X (@Lumisinsite)")),
             ("yt", "https://www.youtube.com/@lumitradesio", _("Lumi on YouTube")),
             ("tt", "https://www.tiktok.com/@lumitradesio", _("Lumi on TikTok")))
    return (f'<span class="{cls}">' + "".join(f'<a class="soc-i {k}" href="{u}" rel="me noopener" target="_blank" aria-label="{E(l)}" title="{E(l)}">{SOCIAL_SVG[k]}</a>'
                                            for k, u, l in items) + "</span>")


def foot_brand(h):
    """First footer line: positioning + social links (same on every generated page)."""
    E, _ = h.E, h._
    return (f'<p class="foot-brand">{_(FOOT_BRAND)} '
            f'<a href="https://x.com/Lumisinsite" rel="me noopener" target="_blank">{E(_("Follow @Lumisinsite"))}</a> · '
            f'<a href="https://www.youtube.com/@lumitradesio" rel="me noopener" target="_blank">{E(_("Lumi on YouTube"))}</a> · '
            f'<a href="https://www.tiktok.com/@lumitradesio" rel="me noopener" target="_blank">TikTok</a></p>')


def chrome(h, pre, home, nav_items, V, path, current=None):
    """Header + nav (pre = path prefix to the site root, home = to this language's home). nav_items is ignored."""
    return (f'<body class="cp tp lgw">\n<div class="bg-glow" aria-hidden="true"></div>\n'
            f'<header class="cp-top"><div class="wrap cp-top-inner">\n'
            f'  <a class="cp-brand" href="{home}"><img class="wm" src="{pre}assets/brand/wordmark.png?v={V}" alt="Lumi" width="80" height="42"><span class="sr-only"> Trades</span></a>\n'
            f'  <span class="cp-top-r">{h.i18n.switcher(h.L, path, h.langs)}<a class="cp-dash" href="{home}trust/">{h.E(h._("Vendor trust list →"))}</a>{social_icons(h)}</span>\n</div></header>\n'
            f'<nav class="nav" aria-label="{h.E(h._("Site"))}"><div class="wrap nav-inner">{site_nav(h, home, "", current)}</div></nav>\n')


def _policy_link(h, pre):
    import policy_page  # footer link in every language that has the page (policy_page.LIVE_LANGS)
    return policy_page.footer_link(h, pre + h.L.prefix)


def footer(h, pre, gen_date):
    E, _ = h.E, h._
    P = pre + h.L.prefix
    return (f'<footer class="wrap footer">\n  {foot_brand(h)}\n  <p class="foot-soc">{social_icons(h)}</p>\n'
            f'  <p class="foot-isnt">{_(FOOT_INDEP, href=E(P + "trust-policy/"))}</p>\n'
            f'  <p>{_("Times in US Central · Page generated {date}", date=E(gen_date))} · <a href="{P}privacy/">{E(_("Privacy Policy"))}</a>{_policy_link(h, pre)}'
            f'{extra_footer_links(h, pre)}</p>\n</footer>\n</body>\n</html>\n')


INFO_LINKS = (("pricing/", "Pricing"), ("about/", "About"), ("terms/", "Terms"))   # English-only pages (scripts/info_pages.py)


def extra_footer_links(h, root):
    """Footer links to /pricing/, /about/ and /terms/ (English-only, at the site root; root = path prefix to the site root)."""
    E, _ = h.E, h._
    return "".join(f' · <a href="{root}{p}">{E(_(t))}</a>' for p, t in INFO_LINKS)


def assets(h, pre, V):
    return (f'<link rel="icon" href="{pre}favicon.ico?v={V}" sizes="any">\n'
            f'<link rel="apple-touch-icon" href="{pre}assets/apple-touch-icon.png?v={V}" sizes="180x180">\n'
            f'<link rel="preload" href="{pre}assets/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>\n'
            f'<link rel="preload" href="{pre}assets/fonts/sora-var.woff2" as="font" type="font/woff2" crossorigin>\n'
            f'<link rel="stylesheet" href="{pre}assets/style.css?v={V}">\n'
            f'<link rel="stylesheet" href="{pre}assets/glow.css?v={V}">\n'
            + h.i18n_scripts(pre))
