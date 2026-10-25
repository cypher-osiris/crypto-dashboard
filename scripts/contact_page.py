"""/contact/ (one per language): official contact addresses and accounts, so search engines and readers can tell
Lumi Trades (lumitrades.io) apart from similarly named sites. Called from site_pages.build().

Like the Lumi Check privacy section, the body is kept in English on every language page for now (marked lang="en",
with a translated note) so the wording is exact; the title, description, heading, lede and note are translated
(assets/i18n/<lang>.json "pages"). Keep every statement in sync with:
- seo.ORG_ISNT / the footer "What Lumi is / isn't" line: Lumi emails only from hello@ or lumi@, never from admin@
- seo.CONTACT_POINTS / seo.SAME_AS (Organization JSON-LD on every page)
- /.well-known/security.txt (security reports)
- site_pages trust page #reply (seller right to reply) and policy_page (conflicts policy)
Plain facts only: no claims about any other company, never name a person, no market levels or trading claims."""
import datetime as dt

import seo

UPDATED = dt.date(2026, 10, 25)   # bump when the page text changes (dateModified)
SLUG = "contact/"
TITLE = "Contact Lumi Trades: official email addresses and accounts"
H1 = "Contact Lumi Trades"
DESC = ("Official Lumi Trades contacts: hello@ and lumi@lumitrades.io (admin@ is receive-only), X, YouTube, GitHub, npm and the API. "
        "Not a broker; no deposits.")  # <=155 chars (meta description) in every language
LEDE = ("Lumi Trades (lumitrades.io) is an independent x402 seller trust list, built from real paid test-buys with signed receipts. "
        "It is not a broker or exchange: it takes no deposits, offers no trading or deposit accounts, "
        "and never asks for passwords, wallet keys or seed phrases.")
NOTE = "The details below are in English only for now."
FOOTER_LINK = "Contact"

API = seo.API
GITHUB = "https://github.com/lumitrades"
X_URL, YT_URL, TT_URL = "https://x.com/lumisinsite", "https://www.youtube.com/@lumitradesio", "https://www.tiktok.com/@lumitradesio"
NPM = [("lumi-trades-mcp", "MCP server for AI agents"), ("lumi-check", "free pre-pay check for x402 sellers")]
NOT_AFFILIATED = ("Lumi Trades (lumitrades.io) is not affiliated with LumiTraders, LumineTrade (luminetrade.com), "
                  "or lumitrade.net / mylumitrade.com.")


def _a(href, txt, ext=True):
    return f'<a href="{href}"' + (' rel="me noopener" target="_blank"' if ext else "") + f">{txt}</a>"


def sections(home, root):
    """[(id, heading, [trusted HTML paragraphs or <ul>])]. home / root = relative paths to this language's home / the site root."""
    mail = lambda a: f'<a href="mailto:{a}">{a}</a>'
    npm = "".join(f'<li>npm: {_a("https://www.npmjs.com/package/" + n, f"<code>{n}</code>")} ({d})</li>' for n, d in NPM)
    return [
        ("email", "Email", [
            f"<ul class=\"cp-list\"><li>{mail('hello@lumitrades.io')}: general questions, corrections and privacy requests.</li>"
            f"<li>{mail('lumi@lumitrades.io')}: Lumi's other official address.</li></ul>",
            "<b>admin@lumitrades.io</b> is a receive-only administrative address. Lumi never sends messages from it. "
            "Lumi only emails from hello@lumitrades.io or lumi@lumitrades.io.",
            f"To report a security issue, follow {_a(root + '.well-known/security.txt', '/.well-known/security.txt', False)}.",
        ]),
        ("accounts", "Official accounts", [
            f"<ul class=\"cp-list\"><li>X: {_a(X_URL, '@lumisinsite')}</li>"
            f"<li>YouTube: {_a(YT_URL, '@lumitradesio')} (Lumi)</li>"
            f"<li>TikTok: {_a(TT_URL, '@lumitradesio')}</li>"
            f"<li>API: {_a(API, 'api.lumitrades.io')}</li>"
            f"<li>GitHub: {_a(GITHUB, 'github.com/lumitrades')}</li>{npm}</ul>",
        ]),
        ("not-affiliated", "Not affiliated", [NOT_AFFILIATED]),
        ("sellers", "Sellers on the trust list", [
            f'If you run an x402 endpoint on the trust list and think an observation is wrong or missing context, see '
            f'{_a(home + "trust/#reply", "Right to reply", False)} and the {_a(home + "trust-policy/", "conflicts policy", False)}.',
        ]),
    ]


def footer_link(h, home):
    """' · <a>Contact</a>' for the site footer (every language)."""
    return f' · <a href="{home}{SLUG}">{h.E(h._(FOOTER_LINK))}</a>'


def build_page(h, tp, nav_items, V, gen_date, page):
    E, _t = h.E, h._
    title, desc, h1 = _t(TITLE), _t(DESC), _t(H1)
    url = h.SITE + h.L.prefix + SLUG
    ld = [seo.organization(_t),
          {"@context": "https://schema.org", "@type": "ContactPage", "name": h1, "url": url, "description": desc,
           "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "about": {"@id": seo.ORG_ID},
           "mainEntity": {"@id": seo.ORG_ID}, "publisher": {"@id": seo.ORG_ID}, "dateModified": UPDATED.isoformat()},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": h1, "item": url}]}]
    lang_attr = "" if h.L.en else ' lang="en"'
    note = "" if h.L.en else f'<p class="meta">{E(_t(NOTE))}</p>\n'
    secs = "".join(
        f'<section class="card cp-sec" id="{sid}"{lang_attr}><h2>{E(head)}</h2>\n'
        + "".join(p if p.startswith("<ul") else f"<p>{p}</p>" for p in paras) + "</section>\n"
        for sid, head, paras in sections("../", "../" if h.L.en else "../../"))
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(h1)}</p>
<h1>{E(h1)}</h1>
<p class="cp-lede">{E(_t(LEDE))}</p>
{note}{secs}</main>
"""
    return page(h, tp, SLUG, title, desc, ld, body, V, gen_date, nav_items, "contact", keywords=None)
