"""Pricing, About and Terms pages (English only, at the site root). stdlib only.

Ported from branch homepage-redesign (Terms section 17 + Addendum B) onto the trust-only site; the homepage redesign
itself is NOT included (deferred).
- /pricing/: trust checks, seller monitoring and the trust data feed, from the same tables as /agents/
  (site_pages.TRUST_PRICES / MONITOR_PLANS / FEED_PLANS). No trading ideas, signals, levels or market data.
- /about/ and /terms/: no personal names. The only postal address is the business mailbox NOTICE_ADDRESS, listed in
  /terms/ section 17 only (never on /contact/ or any other page; notices go by email to LEGAL_EMAIL, the address is listed,
  not invited); check_placeholders() fails the build if it is ever reset to the placeholder. Never a home address.

Built from build_pages.py for English only (h.L.en); linked from every footer (site_chrome.extra_footer_links).
"""
import os
import re

import seo
import site_pages as sp

CONTACT = "hello@lumitrades.io"
# Legal M2: a USPS PO box, a CMRA private mailbox or a registered-agent address. NEVER a home address.
NOTICE_PLACEHOLDER = "[NOTICE ADDRESS: to supply]"
# Business mailbox (supplied Oct 25, 2026). Operator name "Lumi Trades" only (no LLC/Inc.). Not translated.
NOTICE_ADDRESS = "Lumi Trades, 6311 Ames Ave #1056, Omaha, NE 68104, United States"
LEGAL_EMAIL = "legal@lumitrades.io"
TERMS_UPDATED = "Oct 26, 2026"   # first published version
TERMS_VERSION = 1
FEED_LICENCE = "https://api.lumitrades.io/v1/feed/license"
FEED_LICENCE_NAME = "Trust Data Licence, version 2026-10-22"   # Legal N5: "licence" everywhere in site copy


def check_placeholders():
    """Fail the build while a Legal placeholder would be published (override for local previews only)."""
    if NOTICE_ADDRESS == NOTICE_PLACEHOLDER and os.environ.get("LUMI_ALLOW_DRAFT_PLACEHOLDERS") != "1":
        raise SystemExit(f"build_pages: REFUSED: /terms/ still has {NOTICE_PLACEHOLDER}. Set home_pages.NOTICE_ADDRESS to a "
                         "PO box, private mailbox or registered-agent address (never a home address), or set "
                         "LUMI_ALLOW_DRAFT_PLACEHOLDERS=1 for a local preview build that is not published.")


def _english_only(page):
    """No hreflang alternates or language switcher: there is no translated version of these pages yet."""
    page = re.sub(r'<link rel="alternate" hreflang="[^"]*" href="[^"]*">\n?', "", page)
    page = re.sub(r'<meta property="og:locale:alternate" content="[^"]*">\n?', "", page)
    return re.sub(r'<details class="lang-menu">.*?</details>', "", page, flags=re.S)


def _ld(h, slug, name, desc):
    url = h.SITE + slug
    return [{"@context": "https://schema.org", "@type": "WebPage", "name": name, "url": url, "description": desc,
             "inLanguage": "en", "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID}},
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE},
                {"@type": "ListItem", "position": 2, "name": name, "item": url}]}]


# ---------- /pricing/ ----------
PRICING_TITLE = "Pricing: trust checks, seller monitoring and data feed | Lumi Trades"
PRICING_DESC = ("Lumi Trades prices: free trust list, $0.02 check before paying a URL, $0.02 vendor report, seller monitoring from $5 "
                "and a trust data feed. Pay per call with x402.")   # <=155 chars, no "&" or quotes


def pricing_page(h, tp, nav_items, V, gen_date):
    E = h.E
    row = lambda p, ep, pr: f'<tr><td>{E(p)}</td><td class="mono">{E(ep)}</td><td class="num mono">{E(pr)}</td></tr>'
    thead = '<thead><tr><th>Product</th><th>Endpoint</th><th class="num">Price</th></tr></thead>'
    table = lambda items: f'<div class="cp-tablewrap"><table class="cp-table cp-stack cp-stack-r pr-table">{thead}<tbody>{"".join(row(*x) for x in items)}</tbody></table></div>'
    pthead = '<thead><tr><th>Plan</th><th>Price</th><th>What you get</th></tr></thead>'
    ptable = lambda items: ('<div class="cp-tablewrap"><table class="cp-table cp-stack pr-table pr-plans">' + pthead + "<tbody>" + "".join(
        f'<tr><td>{E(nm)}</td><td class="mono pr-price">{E(fmt.format(p=p))}</td><td>{E(d)}</td></tr>' for nm, (fmt, p), d in items) + "</tbody></table></div>")
    lk = lambda href, txt: f'<a href="{href}" target="_blank" rel="noopener">{E(txt)}</a>'
    ld = [seo.organization(h._, "home")] + _ld(h, "pricing/", "Pricing", PRICING_DESC)
    body = f"""<main class="wrap cp-main ag-main pr-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › Pricing</p>
<h1>Pricing</h1>
<p class="cp-lede">The vendor trust list is free. Everything else is pay per call with x402: no account, no API key. New Base and XRPL wallets get <b>3 free calls</b> in total, usable on any paid route (one trial per wallet, not per chain). Paying Lumi never changes a score or label.</p>
<section class="card cp-sec" id="trust"><h2>Check a seller before you pay</h2>
<p>The pay check, <code>GET /v1/trust/check?url=</code>, answers allow, warn or block with reasons for any x402 URL, for <b class="mono">$0.02</b> per check. The full report on one vendor from the list, with tx hashes and signed receipts, is <b class="mono">$0.02</b>. The <a href="../trust/">vendor trust list</a> is free.</p>
{table(sp.TRUST_PRICES)}</section>
<section class="card cp-sec" id="sellers"><h2>For sellers: monitoring and audits</h2>
<p><b>Sellers:</b> prove you control your payTo wallet, then Lumi test-buys your endpoints and alerts you when something breaks. Watch <b class="mono">$5</b> or Watch Pro <b class="mono">$20</b> per endpoint per 30 days, with a free tier and a free 14-day Watch trial; Re-test pack <b class="mono">$6.50</b> (30 test-buys) or Founder pack <b class="mono">$5.00</b> (24 test-buys, first 10 sellers); Audit <b class="mono">$99</b> one-time. A paid plan is disclosed on the seller's public entry and never changes its label. No auto-renew; no refunds unless Lumi can't perform the monitoring. {lk("https://api.lumitrades.io/v1/monitor", "How to start →")}</p>
{ptable(sp.MONITOR_PLANS)}</section>
<section class="card cp-sec" id="feed"><h2>Trust data feed</h2>
<p><b>Trust data feed</b> for facilitators, wallets and agent frameworks: a free key with 1,000 lookups a month, then <b class="mono">$1.50</b> per 1,000 (prepaid credits never expire), or Feed <b class="mono">$99</b> and Feed Pro <b class="mono">$199</b> per 30 days. No resale of raw data, attribution required, no warranty. Use is governed by the {lk(FEED_LICENCE, FEED_LICENCE_NAME)}.</p>
{ptable(sp.FEED_PLANS)}</section>
<section class="card cp-sec" id="pay"><h2>How to pay</h2>
<p>Pay per call with x402, no account or key: <b>USDC on Base</b>, <b>XRP, RLUSD or USDC on the XRP Ledger</b> or <b>USDC on Stellar</b>. MCP server: <code>https://api.lumitrades.io/mcp</code>. Docs: {lk("https://api.lumitrades.io/", "api.lumitrades.io")} · <a href="../agents/">The 402 flow and MCP setup →</a></p>
<p class="meta">Every price here matches the live API's 402 quotes and <code>/.well-known/x402</code>. The price that applies is the one in the 402 quote when you pay; promotional or founder prices may apply as quoted. If the data isn't fresh the API answers 503 and you are not charged. <a href="../prices/">Dated prices and proof (also as JSON) →</a></p></section>
</main>
"""
    page = sp._page(h, tp, "pricing/", PRICING_TITLE, PRICING_DESC, ld, body, V, gen_date, nav_items, "pricing")
    return _english_only(page)


# ---------- /prices/ (machine-readable price and proof page) ----------
PRICES_TITLE = "Prices and proof: x402 seller checks | Lumi Trades"
PRICES_DESC = ("Lumi Trades prices, copied from the live x402 quotes and dated: $0.01 to check a seller before "
               "paying, $0.02 for a quote check or seller report. JSON too.")   # <=155 chars, no "&" or quotes
PRICES_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prices", "index.json")


def prices_page(h, tp, nav_items, V, gen_date):
    """Built from prices/index.json (scripts/prices_snapshot.py: unpaid GETs of the live 402 quotes, never a payment)."""
    import json
    E = h.E
    with open(PRICES_JSON, encoding="utf-8") as f:
        snap = json.load(f)
    lk = lambda href, txt: f'<a href="{E(href)}" target="_blank" rel="noopener">{E(txt)}</a>'
    rows = "".join(
        f'<tr><td class="mono">{E(p["endpoint"])}</td><td class="num mono">${E(p["price_usd"])}</td><td class="mono">'
        + "<br>".join(E(f'{o["amount"]} {o["asset"]} on {o["chain"]}') for o in p["accepts"])
        + "</td><td>" + (lk(snap["proof"]["x402_discovery"], "Quote in x402 discovery") if "{id}" in p["quote_url"] else lk(p["quote_url"], "Live quote"))
        + "</td></tr>" for p in snap["paid"])
    free = "".join(f'<li><code>{E(x["endpoint"])}</code>: {E(x["name"])}, free</li>' for x in snap["free"])
    pay_to = "".join(f'<li>{E(w["chain"])}: <code>{E(w["address"])}</code></li>' for w in snap["pay_to"])
    pr = snap["proof"]
    ld = [seo.organization(h._, "home")] + _ld(h, "prices/", "Prices and proof", PRICES_DESC) + [{
        "@context": "https://schema.org", "@type": "Dataset", "name": "Lumi Trades x402 prices", "url": h.SITE + "prices/",
        "description": PRICES_DESC, "dateModified": snap["as_of"], "isAccessibleForFree": True,
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": h.SITE + "prices/index.json"}],
        "publisher": {"@id": seo.ORG_ID}}]
    body = f"""<main class="wrap cp-main ag-main pr-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › Prices and proof</p>
<h1>Prices and proof</h1>
<p class="cp-lede">x402 seller trust you can verify. <b>Check a seller before paying:</b> <code>GET https://api.lumitrades.io/v1/verdict?url=</code>, one signed label for <b class="mono">$0.01</b>. Every price below is copied from the live x402 quote, checked <time datetime="{E(snap["as_of"])}">{E(snap["as_of_ct"])}</time> (US Central). Machine-readable: <a href="index.json">prices/index.json</a>.</p>
<section class="card cp-sec" id="paid"><h2>Paid per call (x402)</h2>
<div class="cp-tablewrap"><table class="cp-table cp-stack pr-table"><thead><tr><th>Endpoint</th><th class="num">USD</th><th>Quoted as</th><th>Check it</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="meta">XRP is quoted at the live XRP/USD rate on every call; the XRP amount shown is the quote at the time above. The quote you pay against is the one that applies. {E(snap["never_charged"])}</p></section>
<section class="card cp-sec" id="free"><h2>Free</h2><ul>{free}</ul></section>
<section class="card cp-sec" id="pay-to"><h2>Where payments go</h2>
<p>{E(snap["pay_to_rule"])}</p><ul>{pay_to}</ul></section>
<section class="card cp-sec" id="proof"><h2>Evidence</h2><ul>
<li><a href="../trust/">Dated test-buy results</a>: Lumi's paid test-buys of x402 sellers, each with its date, chain and transaction link</li>
<li>{lk(pr["test_buy_wallets"], "Lumi's test-buy wallets")}: the only wallets that pay for Lumi's test-buys</li>
<li>{lk(pr["verify_receipt"], "Verify a signed receipt")} (free; signed by Lumi's test-buy wallet). Signed answers check against {lk(pr["signing_keys"], "Lumi's signing keys")}</li>
<li>{lk(pr["sample_previews"], "Free previews")} of the paid answers, with the time generated · {lk(pr["x402_discovery"], "x402 discovery")}</li>
<li><a href="../how-it-works/">How Lumi tests x402 sellers</a></li>
</ul><p class="meta">{E(snap["disclaimer"])}</p></section>
</main>
"""
    page = sp._page(h, tp, "prices/", PRICES_TITLE, PRICES_DESC, ld, body, V, gen_date, nav_items, "pricing")
    return _english_only(page)


# ---------- /about/ ----------
# Editor asked for "About: an independent x402 trust service | Lumi Trades"; Legal M9 says drop "independent" (an affiliated
# setup service is planned). Legal wins: Legal's wording, in the editor's title format.
ABOUT_TITLE = "About: x402 test-buy evidence | Lumi Trades"
ABOUT_DESC = ("Lumi is a test-buy evidence service for x402: it test-buys x402 sellers with its own money and publishes the results. "
              "Paying Lumi never changes a label.")   # <=155 chars


def about_page(h, tp, nav_items, V, gen_date):
    ld = _ld(h, "about/", "About", ABOUT_DESC)
    body = f"""<main class="wrap cp-main ag-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › About</p>
<h1>About Lumi Trades</h1>
<p class="cp-lede">Lumi is a test-buy evidence service for x402, the protocol that lets AI agents pay for an API call by call. Before an agent pays a seller, it can ask Lumi what happened the last time someone actually paid.</p>
<p>Lumi is an AI agent. It runs under ongoing human oversight: a person reviews its outreach and spending decisions. There is no larger team behind it.</p>
<section class="card cp-sec" id="what"><h2>What Lumi does</h2>
<p>Lumi makes small, real test-buys from x402 sellers <b>with its own money</b>. For each buy it records what was quoted, what was paid, the on-chain transaction and whether the data came back. It publishes the dated results free on the <a href="../trust/">vendor trust list</a>. For each settled test-buy, the per-vendor report (<b class="mono">$0.02</b>) adds the on-chain transaction hash, which anyone can look up on the public ledger, and a receipt signed by Lumi's wallet, which anyone can <a href="../trust/#verify">verify</a> for free.</p>
<p>How a result becomes a label is written down in the <a href="../trust-policy/">trust policy</a>, and <a href="../how-it-works/">How Lumi tests x402 sellers</a> walks through a test-buy step by step.</p></section>
<section class="card cp-sec" id="independence"><h2>How labels stay separate from payments</h2>
<p><b>Paying Lumi never changes a score or label.</b> They come only from Lumi's own checks and test-buys. A seller can buy monitoring or an audit from Lumi Trades; that's disclosed on the seller's public entry and in the data feed (<code>commercial_relationship</code>), never earns a better label and never removes a finding. The <a href="../trust-policy/">conflicts policy</a> sets out the rules and lists every seller who pays.</p>
<p>Run a seller on the list? You can ask for a re-test, add a reply or ask for a correction: see <a href="../terms/#sellers">Sellers: corrections and reply</a>.</p></section>
<section class="card cp-sec" id="not"><h2>What Lumi is not</h2>
<p>Lumi is not a broker, an exchange or a wallet. <b>Lumi never holds or moves your money</b>, and has no accounts or deposits. Lumi Trades' only income is the per-call x402 fees, seller monitoring plans and audits, and data-feed plans and credits listed on the <a href="../pricing/">pricing page</a>. The only payments Lumi makes are its own test-buys (and refunds).</p></section>
<section class="card cp-sec" id="contact"><h2>Contact</h2>
<p>Email <a href="mailto:{CONTACT}">{CONTACT}</a>. Official accounts and security contacts are listed on the <a href="../contact/">contact page</a>.</p></section>
</main>
"""
    return _english_only(sp._page(h, tp, "about/", ABOUT_TITLE, ABOUT_DESC, ld, body, V, gen_date, nav_items, "about"))


# ---------- /terms/ ----------
TERMS_TITLE = "Terms of use | Lumi Trades"
TERMS_DESC = ("Terms of use for lumitrades.io and the Lumi API: who runs the service, informational evidence only, x402 payments "
              "and refunds, acceptable use and limits of liability.")   # <=155 chars


def _callout(html):
    """Legal M4: the warranty disclaimer and the liability cap are conspicuous (bold, bordered)."""
    return f'<div class="tm-callout" style="border:2px solid #f5b942;border-radius:10px;padding:.8rem 1rem;margin:.6rem 0;font-weight:600;color:#f3f4f6">{html}</div>'


def terms_page(h, tp, nav_items, V, gen_date):
    ld = _ld(h, "terms/", "Terms of use", TERMS_DESC)
    mail = f'<a href="mailto:{CONTACT}">{CONTACT}</a>'
    lic = f'<a href="{FEED_LICENCE}" target="_blank" rel="noopener">{FEED_LICENCE_NAME}</a>'
    body = f"""<main class="wrap cp-main ag-main tm-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › Terms</p>
<h1>Terms of use</h1>
<p class="meta"><b>Last updated: {TERMS_UPDATED}</b> · Version {TERMS_VERSION}</p>
<p><b>Sections 2 and 7 limit our responsibility to you. Please read them.</b></p>
<p class="cp-lede">These terms cover lumitrades.io and the Lumi API at api.lumitrades.io (together, "the service"). By using the service you agree to them.</p>
<section class="card cp-sec" id="operator"><h2>Who runs the service</h2>
<p>Lumi Trades ("Lumi Trades", "we") runs lumitrades.io and api.lumitrades.io. Lumi Trades is a trade name used by its operator, an individual doing business as a sole proprietorship. If our operating entity changes, we will update these Terms (see <a href="#assignment">Assignment</a>). Lumi is an AI agent that Lumi Trades runs; references to "Lumi" acting mean Lumi Trades acting through it.</p></section>
<section class="card cp-sec" id="evidence"><h2>1. Informational evidence only</h2>
<p>The service publishes evidence: dated results of Lumi's own test-buys from x402 sellers, the on-chain transactions behind them, signed receipts and the labels Lumi derives from them under its <a href="../trust-policy/">trust policy</a>. It is information about what happened at a point in time. It is not an endorsement, a certification or a recommendation of any seller.</p></section>
<section class="card cp-sec" id="no-guarantee"><h2>2. No guarantee</h2>
<p>A seller that delivered when Lumi tested it can fail later, and one that failed can recover. Results can be incomplete, delayed or wrong. You decide whether to pay a seller, and you are responsible for that decision.</p>
{_callout('<b>DISCLAIMER OF WARRANTIES.</b> THE SERVICE AND ALL RESULTS ARE PROVIDED "AS IS" AND "AS AVAILABLE". TO THE FULLEST EXTENT THE LAW ALLOWS, LUMI TRADES DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY, AVAILABILITY AND NON-INFRINGEMENT.')}</section>
<section class="card cp-sec" id="not-advice"><h2>3. Not financial advice</h2>
<p>Nothing on the site or returned by the API is financial, investment, legal or tax advice, or an offer or solicitation to buy or sell anything. Lumi Trades isn't a registered investment adviser or commodity trading adviser and doesn't give personalized advice: what it publishes is general and impersonal and isn't tailored to anyone. Lumi Trades is not a broker, an exchange or a wallet and never holds your funds.</p></section>
<section class="card cp-sec" id="payments"><h2>4. Payments</h2>
<p>Paid calls are priced in the API's 402 quote and paid with x402 on the networks listed on the <a href="../pricing/">pricing page</a>. Prices can change; the price that applies is the one in the 402 quote when you pay, and promotional or founder prices may apply as quoted. On-chain payments can't be reversed by you or by us, so there are no chargebacks. If the data isn't fresh, the API answers 503 <b>before</b> any payment is taken.</p>
<p>Per-call fees are not refundable. Seller monitoring plans and audits are refundable only as stated on the <a href="../pricing/">pricing page</a> (when Lumi can't perform the monitoring), and data-feed plans and credits as stated in the {lic} (the unprovided part is refunded). Refunds are paid on-chain to the wallet that paid, in the same asset where possible.</p></section>
<section class="card cp-sec" id="use"><h2>5. Acceptable use</h2>
<p>Don't use the service to break the law, to overload or attack it, to get around payment or rate limits, to misrepresent Lumi's results, or to scrape, bulk-download or systematically extract the trust list, reports or API results (beyond normal use of the free endpoints and the limits in the feed licence), to resell, sublicense or republish them as a dataset, feed or competing service, or to create multiple wallets or keys to get around free-tier limits. Showing individual results with attribution ("Trust data: Lumi (lumitrades.io)") is fine. Data-feed use is also governed by the {lic}. We may block traffic that breaks these terms.</p></section>
<section class="card cp-sec" id="privacy"><h2>6. Privacy</h2>
<p>What the service collects and how long it keeps it is described in the <a href="../privacy/">Privacy Policy</a>.</p></section>
<section class="card cp-sec" id="liability"><h2>7. Limitation of liability</h2>
{_callout("<b>LIMITATION OF LIABILITY.</b> TO THE FULLEST EXTENT THE LAW ALLOWS: (a) LUMI TRADES IS NOT LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE DAMAGES, OR FOR LOST PROFITS, LOST DATA OR PAYMENTS YOU MAKE TO THIRD-PARTY SELLERS; AND (b) LUMI TRADES' TOTAL LIABILITY FOR ALL CLAIMS RELATING TO THE SERVICE IS LIMITED TO THE GREATER OF (i) THE AMOUNTS YOU PAID LUMI TRADES FOR THE SERVICE IN THE 12 MONTHS BEFORE THE EVENT GIVING RISE TO THE CLAIM, AND (ii) US$100. THESE LIMITS DO NOT APPLY TO LIABILITY THAT CANNOT BE LIMITED BY LAW, INCLUDING FOR FRAUD, GROSS NEGLIGENCE OR WILFUL MISCONDUCT, OR TO REFUNDS OR CREDITS OWED UNDER SECTION 4.")}
<p>Some jurisdictions don't allow some of these limits, so they may not all apply to you. If you use the service as a consumer, nothing here limits rights you have under consumer protection law that cannot be waived.</p></section>
<section class="card cp-sec" id="eligibility"><h2>8. Eligibility</h2>
<p>You must be at least 18 and able to form a binding contract, and if you use the service for an organization, you confirm you may bind it. You may not use the service if you, or anyone you act for, are on a U.S. sanctions list (including the OFAC SDN list) or are located in, or ordinarily resident in, a country or region subject to comprehensive U.S. sanctions, or if your use would break sanctions or export laws. Lumi Trades screens payment addresses against public sanctions lists and may refuse, suspend or end service, and hold or not return payments, where the law requires.</p></section>
<section class="card cp-sec" id="ai-agent"><h2>9. AI agent</h2>
<p>Much of the service, including test-buys, labels and replies, is produced by Lumi, an AI agent, under human oversight. AI output can be wrong or incomplete; check anything important yourself.</p></section>
<section class="card cp-sec" id="sellers"><h2>10. Sellers: corrections and reply</h2>
<p>If you run a seller endpoint on the trust list, you can ask for a re-test at any time, add a reply shown next to your findings (see <a href="../trust/#reply">Right to reply</a>), or ask us to correct a factual error by emailing {mail} with the endpoint and what's wrong. We aim to respond within 5 business days; if a re-test or our records show we got something wrong, we correct it and note the correction with its date. We may remove replies that are unlawful, abusive, or contain personal data or malware links. Asking not to be tested is handled as described in the <a href="../trust-policy/">conflicts policy</a>.</p></section>
<section class="card cp-sec" id="indemnity"><h2>11. Indemnity</h2>
<p>If you use the service in breach of these terms or the law (for example by reselling data, or misrepresenting Lumi's results), you will cover the reasonable costs Lumi Trades incurs because of it, including reasonable legal fees.</p></section>
<section class="card cp-sec" id="termination"><h2>12. Suspension and termination</h2>
<p>We may suspend or end access for any breach, abuse or legal requirement. You can stop at any time. Sections 2, 3, 7 and this section survive. Ending access doesn't remove refunds owed under section 4.</p></section>
<section class="card cp-sec" id="assignment"><h2>13. Assignment</h2>
<p>We may assign these terms to a successor, including a company formed to operate Lumi Trades, without your consent. You may not assign them without ours.</p></section>
<section class="card cp-sec" id="whole-agreement"><h2>14. Severability; entire agreement; no waiver</h2>
<p>If any part is unenforceable, the rest stays in effect and that part is enforced as far as allowed. These terms, the Privacy Policy, the conflicts policy, the prices in the API's 402 quotes and, for the data feed, the feed licence are the whole agreement. If they conflict, the feed licence governs feed use, and these terms govern everything else. Not enforcing a term right away doesn't waive it.</p></section>
<section class="card cp-sec" id="law"><h2>15. Governing law and courts</h2>
<p>These terms are governed by the laws of the U.S. state in which Lumi Trades' operator principally resides and conducts business, without regard to conflict-of-laws rules, and applicable U.S. federal law.</p></section>
<section class="card cp-sec" id="changes"><h2>16. Changes</h2>
<p>We'll date every version. Material changes take effect 14 days after we post them (or immediately where needed for legal or security reasons); continued use after that means you accept them. Changes don't apply to disputes that arose before the change.</p></section>
<section class="card cp-sec" id="contact"><h2>17. Contact and legal notices</h2>
<p>Questions: {mail}. Legal notices to Lumi Trades must be sent by email to <a href="mailto:{LEGAL_EMAIL}">{LEGAL_EMAIL}</a> with "Legal notice" in the subject line, and are effective when received. Our postal address, provided as required by law, is: <span class="tm-addr" translate="no">{h.E(NOTICE_ADDRESS)}</span>. Notices to you go to the email or wallet-linked contact you gave us, or are posted on this page.</p></section>
</main>
"""
    return _english_only(sp._page(h, tp, "terms/", TERMS_TITLE, TERMS_DESC, ld, body, V, gen_date, nav_items, "terms"))


def build(h, tp, nav_items, V, gen_date, write):
    """English only. Returns English-only sitemap rows (path, lastmod, changefreq, priority).
    build_pages.build() runs check_placeholders() first (not on dry runs such as i18n.py check)."""
    write("pricing/index.html", pricing_page(h, tp, nav_items, V, gen_date))
    write("about/index.html", about_page(h, tp, nav_items, V, gen_date))
    write("terms/index.html", terms_page(h, tp, nav_items, V, gen_date))
    write("prices/index.html", prices_page(h, tp, nav_items, V, gen_date))
    return [("pricing/", gen_date, "monthly", "0.6"), ("prices/", gen_date, "weekly", "0.6"), ("about/", gen_date, "yearly", "0.4"), ("terms/", gen_date, "yearly", "0.3")]
