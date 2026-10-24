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
- Lumi Check (lumi-api packages/scanner-kit = npm lumi-check, src/trust/contributors.ts, outcomes.ts, migrations 0016-0022):
  tier 1 off until yes (asked once after the first check), tier 2 receipts = chain + tx hash only, badge-only rewards
Never name a person. Contact: hello@lumitrades.io."""
import datetime as dt

import seo

UPDATED = dt.date(2026, 10, 24)   # bump when the policy text changes (shown on the page and in dateModified)
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
# Lumi Check section (after "api"). Trusted, hand-written HTML (<strong>, <code>, mailto links), so it is not escaped.
# Kept in English on every language page for now (marked lang="en", with a translated note) so the policy wording is exact;
# translate it into the i18n catalogs and move it into SECTIONS when ready.
LUMI_CHECK_ID, LUMI_CHECK_HEAD = "lumi-check", "Lumi Check"
LUMI_CHECK_NOTE = "This section is in English only for now."
LUMI_CHECK = [
    "Lumi Check is a free check an agent can run before it pays an x402 seller. It answers allow, warn or block with reasons, the seller's score and a link to the live report. The answer is signed by Lumi so the agent can verify it.",
    "<strong>Checks.</strong> When you run a check, the kit sends only the seller URL's origin and path (any query string is removed before it leaves your machine), or the seller's pay-to address, plus the price if you give one. We do not log what you check. Short-lived counters (for rate limits) are kept in memory and are not stored.",
    '<strong>What the kit shares. Tier 1, off until you say yes:</strong> nothing is sent before you agree. Right after your first check, the kit asks once: &ldquo;Share your results to help improve Lumi\'s public trust list? [Y/n]&rdquo;. Your answer is saved only on your computer, and the question is not shown again. Where the kit cannot ask (no terminal, CI, the MCP server or code), sharing stays off. If you say yes, after a paid call the kit sends one anonymous delivery outcome: the seller\'s host name or Lumi endpoint ID, whether the data was delivered (yes or no) and optionally a coarse status class (for example 2xx, 5xx or timeout). Each report carries a new random token that is used once to drop duplicates and cannot be linked to you or to your other reports. It never includes your wallet, the amount, the transaction hash, the query string, the response, or any stable ID. Tier 1 reports are counted only; they never change a seller\'s score. To change your answer at any time, run <code>lumi-scan telemetry on</code> or <code>lumi-scan telemetry off</code>, set <code>LUMI_CHECK_TELEMETRY=on</code> or <code>off</code>, or set <code>"telemetry": true</code> or <code>false</code> in the kit\'s config file.',
    "<strong>Tier 2, off by default:</strong> sharing full signed receipts. Nothing is sent unless you turn it on (<code>lumi-scan sharing on</code> or <code>LUMI_SHARE_RECEIPTS=1</code>). Each shared receipt includes the payment's transaction ID. A transaction ID is public on its blockchain: anyone who has it can look it up and link it to the wallet that paid and the amount. If you take part, the API stores what you register and submit: a label you choose, your contributor public key, the wallet addresses you pay from, any domains you tell us you own, and the wallet that first funded each registered wallet (read from the public ledger, used to tell independent contributors apart). Your contributor private key and wallet secrets stay on your machine and are never sent to us.",
    "For each receipt you share we store the receipt and the test data in it: the seller endpoint (origin and path only) and the seller's pay-to address, the payment's network and transaction ID, HTTP status, outcome, timing, response size, a hash and a schema fingerprint of the response (field names and types, not the content), data freshness, facilitator and settlement time. Receipts contain no amount, price or wallet field, and we refuse receipts that do. Response bodies are never uploaded. We check each receipt against the public ledger before it counts: that the wallet that signed it paid the seller. We do not store the amount. We keep the paying wallet's address (read from the ledger) with the submission only to run the anti-abuse checks below; it is never published or shown by any public page or API.",
    "<strong>Rewards.</strong> Contributors get a public, pseudonymous contributor badge, optionally with a count of verified contributions (at most one per seller per day). That is the only reward: there are no credits, money, perks, rankings or rate-limit changes, and sharing never changes how any score is computed. Seller badges are earned only and can never be bought; a badge is removed automatically when the seller's score drops below the threshold. Paying Lumi never changes any score, tier, ranking or badge.",
    "We use this data to score sellers, to prevent self-testing and abuse (for example, limits per key, per endpoint and per funding source), and to show your badge. Findings can appear in Lumi's seller observations and badges in combined form; your key id and wallets are not shown with them. Demand statistics are off by default; if you opt in, your purchases are counted only in aggregate, at domain level, with at least two contributors per row and no key ids or wallets.",
    '<strong>How long we keep it.</strong> Raw data is kept for 90 days and then deleted: that covers tier 1 outcome counters, contributor submissions (including the stored receipt copy). A raw tier 1 day is deleted only after it has been summarised. The summaries are kept long-term: one row per seller per day, holding the number of delivered and failed purchases and coarse status classes. They contain no wallet address, amount, transaction ID, URL query, payload or anything that identifies you. Your contributor account (key ID, public key and registered wallets) is kept while it is active, meaning you submitted a verified receipt in the last 12 months, and is not deleted at 90 days. You can see your own submissions and your badge at any time through the contributor API. You do not get, and we do not share, the raw pooled database. To ask about your contributor data, email <a href="mailto:hello@lumitrades.io">hello@lumitrades.io</a>.',
    '<strong>Deleting your contributor account.</strong> You can delete it yourself at any time with <code>lumi-scan account delete</code> (it asks you to type your key ID first), or email <a href="mailto:hello@lumitrades.io">hello@lumitrades.io</a> and we delete it the same way. Deletion is immediate and cannot be undone. <em>Deleted:</em> your key (it can never be used again), label, public key, registered wallets and the funding wallet recorded for each, any domains you told us you own, your demand opt-in, your last-activity date, your badge, and every receipt you shared, including the stored copy, unless we have already cited it in a published, dated test result. <em>Kept, with no link to you:</em> receipts already cited in a published, dated test result, with your wallet signature, paying-wallet address, kit details and key ID removed (the transaction ID, seller and delivery result stay because the published result cites them, and they are still deleted after 90 days like other raw data); the anonymous per-seller daily summaries and tier 1 counters, which never had a link to you; and a record that the deleted key ID existed, so it cannot be reused. Transactions on a public blockchain cannot be deleted by anyone, including us.',
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
    note = "" if h.L.en else f'<p class="meta" lang="{h.L.code}">{E(_t(LUMI_CHECK_NOTE))}</p>\n'
    lang_attr = "" if h.L.en else ' lang="en"'
    lumi = (f'<section class="card cp-sec" id="{LUMI_CHECK_ID}"{lang_attr}><h2>{E(LUMI_CHECK_HEAD)}</h2>\n'
            + note + "".join(f"<p>{p}</p>" for p in LUMI_CHECK) + "</section>\n")
    cut = secs.index('<section class="card cp-sec" id="sharing">')
    secs = secs[:cut] + lumi + secs[cut:]
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(_t("Privacy Policy"))}</p>
<h1>{E(_t("Privacy Policy"))}</h1>
<p class="meta">{E(_t("Last updated: {date}", date=upd))}</p>
<p class="cp-lede">{E(_t(LEDE))}</p>
{secs}</main>
"""
    return page(h, tp, "privacy/", title, desc, ld, body, V, gen_date, nav_items, "privacy", keywords=None)
