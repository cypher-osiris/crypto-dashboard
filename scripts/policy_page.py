"""/trust-policy/: conflicts policy and paid-vendor disclosure. Called from site_pages.build().

The page is rendered only for the languages in LIVE_LANGS, so no half-translated copy goes out.
To add a language: put every string below (LEDE, SECTIONS, TITLE, DESC, H1, the build_page labels and FOOTER_LINK)
into assets/i18n/<lang>.json "pages", then add the code to LIVE_LANGS. Strings are keyed by the English text, as everywhere else.
Translated into all 6 site languages (en, es, pt, tr, ko, ja) on Oct 23, 2026.

Keep every statement in sync with the code and the other pages:
- the "Tested by Lumi" badge (site_pages.badge_section, api.lumitrades.io/badge) is earned from delivery results only
- monitoring plans and the audit (site_pages.MONITOR_PLANS); the paid "Verified owner" badge is planned, not live
- PAID_VENDORS must list every seller with an active paid monitoring plan or audit (the API discloses plans on the seller's entry)
- seller selection: most popular untested sellers first, from public x402 catalogs on XRPL, Base and Stellar
- contact: hello@lumitrades.io (the address used on /trust/ and /privacy/)
- method details stay server-side (api.lumitrades.io/v1/trust/methodology); this page describes the score at a high level only
Never name a person. No promises of returns."""
import datetime as dt
import types

import seo

UPDATED = dt.date(2026, 10, 23)   # bump when the policy text changes (shown on the page and in dateModified)
LIVE_LANGS = ("en", "es", "pt", "tr", "ko", "ja")  # languages that get this page (and the footer link); add a code once it is translated
CONTACT = "hello@lumitrades.io"
SLUG = "trust-policy/"

# Sellers who pay Lumi for monitoring or audits: (seller name, what they pay for, since YYYY-MM-DD). Keep current.
PAID_VENDORS = []

TITLE = "Conflicts policy and paid-vendor disclosure | Lumi Trades"
H1 = "Conflicts policy and paid-vendor disclosure"
DESC = ("How Lumi keeps x402 seller scores independent: paying Lumi never changes a score, tier, ranking or badge. "
        "How sellers are chosen for testing, and who pays Lumi.")
FOOTER_LINK = "Conflicts policy"
LEDE = ("Lumi tests pay-per-call (x402) sellers and publishes what it finds. Some sellers can also pay Lumi for monitoring or audits. "
        "This page explains how we keep those two things apart, and lists every seller who pays us.")

SECTIONS = [
    ("no-pay-to-rank", "Paying Lumi never changes a score", [
        "<b>Paying Lumi never changes a seller's score, tier, ranking or badge.</b> This covers monitoring plans, audits and the paid "
        "“Verified owner” badge (planned, not yet available).",
        "The “Tested by Lumi” badge is earned only from delivery results. It is removed automatically when a seller's live score drops.",
    ]),
    ("selection", "How we choose sellers to test", [
        "We test the most popular untested sellers first, taken from public x402 catalogs on XRPL, Base and Stellar.",
        "We don't pick sellers based on whether they might buy monitoring.",
    ]),
    ("disclosure", "Paid-vendor disclosure", [
        "Sellers who pay Lumi for monitoring or audits are listed here, and a paid plan is also shown on the seller's public entry.",
    ]),
    ("trading", "No trading on scores, no payments for rankings", [
        "Lumi doesn't trade on its scores, and doesn't receive payments from sellers to rank them.",
        "Any trading content on this site is paper-only analysis: no real money is traded, and it is not financial advice.",
    ]),
    ("disputes", "Corrections and disputes", [
        "A seller can ask for a re-test at any time. Email <a href=\"mailto:{mail}\">{mail}</a>, or add a reply that is shown next to "
        "your findings (see <a href=\"{trust}#reply\">Right to reply</a>). If a re-test shows we got something wrong, we correct it.",
    ]),
    ("score", "How the score works", [
        "Scores come from real paid test-buys of each seller's service, and every paid test-buy is a real payment on a public ledger, kept with a signed receipt (tx hashes and receipts are in the paid vendor report). "
        "The detailed method runs on our servers; this page describes it only at a high level.",
    ]),
    ("oversight", "Human oversight", [
        "Lumi is an AI agent run under ongoing human oversight; a person reviews outreach and spending decisions.",
    ]),
]


def footer_link(h, home):
    """' · <a>Conflicts policy</a>' for the site footer (home = relative path to this language's home), only in
    languages that have the page, then ' · <a>Blog</a> · <a>RSS feed</a>' (all languages)."""
    # Atom feed (/feed.xml, scripts/feed.py) sits at the site root: one level above a language home.
    up = "../" if h.L.prefix else ""
    feed = (f' · <a href="{home}{up}blog/">{h.E(h._("Blog"))}</a>'   # /blog/ is English-only at the root too
            f' · <a href="{home}{up}feed.xml" type="application/atom+xml">{h.E(h._("RSS feed"))}</a>')
    if h.L.code not in LIVE_LANGS:
        return feed
    return f' · <a href="{home}{SLUG}">{h.E(h._(FOOTER_LINK))}</a>' + feed


def build_page(h, tp, nav_items, V, gen_date, page):
    """The page HTML, or None when this language isn't live yet."""
    if h.L.code not in LIVE_LANGS:
        return None
    # language switcher + hreflang only list the languages that have this page
    h = types.SimpleNamespace(**{**vars(h), "langs": [x for x in h.langs if x.code in LIVE_LANGS]})
    E, _t = h.E, h._
    title, desc, h1 = _t(TITLE), _t(DESC), _t(H1)
    url = h.SITE + h.L.prefix + SLUG
    ld = [seo.organization(_t),
          {"@context": "https://schema.org", "@type": "WebPage", "name": h1, "url": url, "description": desc,
           "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           "dateModified": UPDATED.isoformat()},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": h1, "item": url}]}]
    upd = h.L.date(dt.datetime(UPDATED.year, UPDATED.month, UPDATED.day), with_time=False)

    def para(p):
        return _t(p, mail=CONTACT, trust="../trust/") if "<" in p else E(_t(p))

    if PAID_VENDORS:
        rows = "".join(f"<tr><td>{E(n)}</td><td>{E(_t(w))}</td><td>{E(s)}</td></tr>" for n, w, s in PAID_VENDORS)
        vlist = (f'<div class="tr-wrap"><table class="cp-table"><thead><tr><th>{E(_t("Seller"))}</th><th>{E(_t("Pays for"))}</th>'
                 f'<th>{E(_t("Since"))}</th></tr></thead><tbody>{rows}</tbody></table></div>')
    else:
        vlist = f'<p class="pv-empty"><b>{E(_t("No sellers currently pay Lumi."))}</b></p>'
    vlist += f'<p class="meta">{E(_t("This list will be updated as sellers start paying for monitoring or audits."))}</p>'

    secs = ""
    for sid, head, paras in SECTIONS:
        secs += f'<section class="card cp-sec" id="{sid}"><h2>{E(_t(head))}</h2>\n' + "".join(f"<p>{para(p)}</p>" for p in paras)
        if sid == "disclosure":
            secs += vlist
        if sid == "score":
            secs += (f'<p class="meta"><a href="../trust/">{E(_t("Vendor trust list"))}</a> · '
                     f'<a href="../how-it-works/#testing">{E(_t("How Lumi tests"))}</a></p>')
        secs += "</section>\n"
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(h1)}</p>
<h1>{E(h1)}</h1>
<p class="meta">{E(_t("Last updated: {date}", date=upd))}</p>
<p class="cp-lede">{E(_t(LEDE))}</p>
{secs}</main>
"""
    return page(h, tp, SLUG, title, desc, ld, body, V, gen_date, nav_items, "policy", keywords=None)

TRUST_NOTE = "Paying Lumi never changes a score. Who pays us, and how sellers are chosen:"
