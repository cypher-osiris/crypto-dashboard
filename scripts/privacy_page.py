"""/privacy/ (one per language): the privacy policy. Called from site_pages.build().
(Not to be confused with scripts/privacy.py, which scrubs paper-trade results from data files.)

Facts only, and every statement here mirrors the code. Keep it in sync when any of these change:
- newsletter: Kit form 10079883 (build_pages.NEWSLETTER_BLOCK, index.html, assets/newsletter.js), email only
- analytics: Cloudflare Web Analytics beacon (build_pages.CF_BEACON), cookieless
- hosting: GitHub Pages (CNAME); no accounts, logins or comment forms
- third parties loaded by pages: Google Fonts, jsDelivr (Chart.js on /classic/), browser-side market data from Coinbase Exchange,
  Kraken, CoinGecko and OKX (assets/signals.js, live.js, extras.js), country lookup api.country.is / ipapi.co (assets/affiliate.js)
- browser storage: localStorage lumi_lang + lumi_lang_hint (assets/i18n.js), sessionStorage lumi_geo_v1 (assets/affiliate.js)
- referral links are geo-gated by assets/affiliate.js: describe them generically, never name an exchange the site hides from US visitors
- agent API (lumi-api repo): src/traffic.ts (path, status, UA, referrer host, country, daily keyed IP hash, 90 days),
  src/sales.ts (payer wallet, amount, network, tx), src/trial.ts (wallet + daily IP hash), monitor/feed signups
  (migrations/0011: wallet, endpoints, optional webhook URL / email), tips and replies (src/trust)
Never name a person. Contact: hello@lumitrades.io."""
import datetime as dt

import seo

UPDATED = dt.date(2026, 10, 23)   # bump when the policy text changes (shown on the page and in dateModified)
CONTACT = "hello@lumitrades.io"

LEDE = ("Lumi Trades runs this website (lumitrades.io) and the agent API (api.lumitrades.io). We collect as little as we can. "
        "This page lists what is collected, by whom and why. We do not sell personal data and we do not use advertising trackers.")
SECTIONS = [
    ("newsletter", "Newsletter", [
        "If you subscribe to the free daily newsletter, the email address you enter is sent to Kit (ConvertKit), the email service "
        "that stores the subscriber list and sends the emails. The form asks for your email address only, and it is used only to send "
        "the daily newsletter.",
        "Kit asks you to confirm the subscription by email, and every newsletter has an unsubscribe link: you can unsubscribe at any time. "
        "Like most email services, Kit may record delivery details such as whether an email was opened. Kit handles this data under its own privacy policy.",
    ]),
    ("analytics", "Analytics", [
        "The site counts visits with Cloudflare Web Analytics. It does not use cookies and does not follow you across websites. "
        "We only see aggregate numbers, such as page views, referring sites, countries and browser types.",
    ]),
    ("hosting", "Hosting", [
        "The website is a set of static pages hosted on GitHub Pages. GitHub may log visitors' IP addresses and request details to run "
        "and secure its service, under GitHub's privacy statement. The site has no accounts, logins or comment forms.",
    ]),
    ("third-parties", "Third-party content and links", [
        "Pages load fonts from Google Fonts and, on some pages, a chart library from the jsDelivr CDN. Live prices and market data are fetched "
        "by your browser directly from public APIs (Coinbase Exchange, Kraken, CoinGecko and OKX). Like any web request, these send your IP "
        "address and browser details to those providers. Nothing from X, YouTube or TikTok is embedded; they are plain links.",
        "Some links to exchanges and wallet makers are affiliate or referral links: we may earn a commission if you sign up, at no cost to you. "
        "Which links are shown depends on your region. To decide, your browser asks a country lookup service (api.country.is, or ipapi.co "
        "as a fallback) for your country, or uses your time zone. The answer stays in your browser and is not sent to us. "
        "Once you follow a link to another site, that site's privacy policy applies.",
    ]),
    ("browser", "Stored in your browser", [
        "This site sets no cookies. Your browser keeps your language choice and whether you dismissed the language suggestion (local storage), "
        "and the region answer described above until you close the tab (session storage). You can clear them in your browser settings.",
    ]),
    ("api", "The agent API (api.lumitrades.io)", [
        "The API runs on Cloudflare Workers. To operate it, it keeps a private traffic log: for each request, the path (without the query string), "
        "the status code, the user agent, the referring site, the country and a keyed hash of the IP address that changes every day. "
        "Raw IP addresses are not stored, and traffic records are deleted after 90 days.",
        "Payments are made on public blockchains. For each paid call the API records the payer's wallet address, the amount, the network and the "
        "transaction ID, which are public on the ledger anyway. Free trial calls record the wallet that signed in and a daily IP hash, to enforce the limits.",
        "If you sign up for seller monitoring or the data feed, the API stores what you submit: your wallet address, your endpoints and, "
        "if you add them, a webhook URL or an email address for alerts. That email address is used only for those alerts and is never shown publicly. "
        "Reports, seller replies and tips sent to the API are stored as submitted (reports and tips with a hashed IP address, to limit abuse); tips are never published.",
    ]),
    ("sharing", "No selling of data", [
        "We do not sell, rent or trade personal data. We share it only with the service providers named on this page, as far as they need it "
        "to run the site, the newsletter and the API, or when the law requires it.",
    ]),
    ("choices", "Your choices and contact", [
        "To unsubscribe from the newsletter, use the link in any email. To ask what we hold about you, or to have it corrected or deleted, "
        "email <a href=\"mailto:{mail}\">{mail}</a>. Payments recorded on a public blockchain cannot be changed or deleted by anyone.",
        "The site is not aimed at children. If this policy changes, this page is updated and the date at the top changes.",
    ]),
]
TITLE = "Privacy Policy | Lumi Trades"
DESC = ("What Lumi Trades collects and why: newsletter email via Kit, cookieless Cloudflare Web Analytics, GitHub Pages hosting and the "
        "agent API logs. We do not sell data.")


def build_page(h, tp, nav_items, V, gen_date, page):
    E, _t = h.E, h._
    title = _t(TITLE)
    desc = _t(DESC)
    url = h.SITE + h.L.prefix + "privacy/"
    ld = [seo.organization(_t),
          {"@context": "https://schema.org", "@type": "WebPage", "name": _t("Privacy Policy"), "url": url, "description": desc,
           "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           "dateModified": UPDATED.isoformat()},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": _t("Privacy Policy"), "item": url}]}]
    upd = h.L.date(dt.datetime(UPDATED.year, UPDATED.month, UPDATED.day), with_time=False)
    secs = "".join(
        f'<section class="card cp-sec" id="{sid}"><h2>{E(_t(head))}</h2>\n'
        + "".join(f"<p>{_t(p, mail=CONTACT) if '{mail}' in p else E(_t(p))}</p>" for p in paras) + "</section>\n"
        for sid, head, paras in SECTIONS)
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(_t("Privacy Policy"))}</p>
<h1>{E(_t("Privacy Policy"))}</h1>
<p class="meta">{E(_t("Last updated: {date}", date=upd))}</p>
<p class="cp-lede">{E(_t(LEDE))}</p>
{secs}</main>
"""
    return page(h, tp, "privacy/", title, desc, ld, body, V, gen_date, nav_items, "privacy", keywords=None)
