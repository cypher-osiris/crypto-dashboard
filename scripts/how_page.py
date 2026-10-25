"""/how-it-works/ (one per language): how Lumi tests x402 sellers. Trust-only since Oct 25, 2026 (the market-ideas
explainer was retired with the rest of the trading section). Called from site_pages.build()."""
import seo

TEST_P = ("Lumi test-buys paid x402 agent services with real payments on XRPL, Base and Stellar, and publishes the dated results "
          "with a signed receipt for each purchase. Paying Lumi never changes a score, and every seller has a right to reply, shown next to the findings.")
HOW_LEDE = ("Lumi is an independent trust service for x402, the pay-per-call protocol AI agents use. It checks sellers with its own money "
            "and publishes the evidence, so an agent can look a seller up before it pays.")
HOW_STEPS = [
    ("Free quote checks", "Lumi asks each listed endpoint for its x402 price quote and checks that the quote is readable and payable. Quote checks cost nothing and show that an endpoint is reachable and priced, not that it delivers."),
    ("Small paid test-buys", "Lumi pays a few cents from its own wallet and records whether real data came back. Paid test-buys run within a small shared daily budget, so not every seller is bought every day."),
    ("Public, signed evidence", "Every paid test-buy is a real transaction on XRPL, Base or Stellar. The tx hash of each seller's latest buy is free on the trust list, and every buy has a receipt signed by the paying wallet that anyone can verify for free."),
    ("A 30-day score", "The score summarizes what Lumi's own checks saw over the last 30 days, with a confidence level. Few samples means low confidence. A seller Lumi has not scored yet shows “Not scored yet”."),
]
BADGE_RULE = ("The “Tested by Lumi” badge is earned only when the score is 80 or higher, Lumi has made at least 3 paid test-buys, "
              "and the latest paid test-buy delivered data. It is removed automatically when any of those stops being true.")


def build_page(h, tp, nav_items, V, gen_date, page):
    E, _t = h.E, h._
    title = _t("How Lumi tests x402 sellers | Lumi Trades")
    desc = _t("How Lumi checks x402 pay-per-call sellers: free quote checks, small paid test-buys on XRPL, Base and Stellar, signed receipts and a 30-day score. Paying Lumi never changes a score.")
    url = h.SITE + h.L.prefix + "how-it-works/"
    ld = [seo.organization(_t, "trust"),
          {"@context": "https://schema.org", "@type": "Article", "headline": title.replace(" | Lumi Trades", ""), "url": url,
           "description": desc, "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           "author": {"@id": seo.ORG_ID}, "dateModified": gen_date},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": _t(tp.HOW_TESTS), "item": url}]}]
    steps = "".join(f'<li><b>{E(_t(n))}</b> {E(_t(d))}</li>' for n, d in HOW_STEPS)
    body = f"""<main class="wrap cp-main hw-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(_t(tp.HOW_TESTS))}</p>
<h1>{E(_t(tp.HOW_TESTS))}</h1>
<p class="cp-lede">{E(_t(HOW_LEDE))}</p>
<section class="card cp-sec" id="testing"><h2>{E(_t("How Lumi tests x402 sellers"))}</h2>
<p>{E(_t(TEST_P))}</p>
<ol class="ag-list">{steps}</ol>
<p class="meta">{E(_t(BADGE_RULE))}</p>
<p class="meta"><a href="https://api.lumitrades.io/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("Methodology"))}</a> · <a href="../agents/#badge">{E(_t("The “Tested by Lumi” badge"))}</a> · <a href="../trust-policy/#score">{E(_t("How the score works"))}</a> · <a href="../trust/">{E(_t("Vendor trust list (free)"))}</a></p></section>
<div class="disclaimer" role="note"><span class="warn-ico" aria-hidden="true">!</span><span>{_t("<strong>Informational evidence, not financial advice.</strong> Dated observations of Lumi's own checks, not a rating, endorsement or guarantee of any business.")}</span></div>
</main>
"""
    return page(h, tp, "how-it-works/", title, desc, ld, body, V, gen_date, nav_items, "how", keywords=None)
