"""Search / agent discoverability helpers (stdlib only): keywords meta, schema.org JSON-LD nodes, the /agents/ FAQ and
/llms.txt. Used by build_pages.py (homepage) and site_pages.py (/agents/, /trust/).

Every English string here is an i18n key (assets/i18n/<lang>.json "pages"), translated with the `t` passed in (Lang.t).
Facts only: what the site and the API do, prices, how payment works. Keep it apolitical and never name a person.
"""

SITE = "https://lumitrades.io/"
API = "https://api.lumitrades.io"
ORG_ID = SITE + "#organization"
SITE_ID = SITE + "#website"
API_ID = API + "/#api"
LOGO = SITE + "assets/brand/logo.png"
SAME_AS = ["https://x.com/lumisinsite", "https://www.youtube.com/@lumitradesio", "https://github.com/cypher-osiris/crypto-dashboard",
           "https://www.npmjs.com/package/lumi-trades-mcp"]

# keyword terms: generic ones are translated (and the English kept too), names / protocols / tickers are not
KW_GENERIC = ["crypto signals", "trading signals", "support and resistance", "fear and greed index", "crypto market data API",
              "AI agent API", "pay per call", "trust score", "x402 vendor reputation", "institutional policy brief", "stablecoin",
              "tokenization", "paper trading"]
KW_NAMES = ["XRP", "XRPL", "XLM", "HBAR", "BTC", "x402", "RLUSD", "USDC on Base", "MCP server", "CBDC", "BIS", "IMF",
            "CoinMarketCap Fear & Greed"]
KW_PAGE = {  # which terms lead on each page (the rest follow)
    "home": ["crypto signals", "trading signals", "XRP", "support and resistance", "fear and greed index", "AI agent API", "x402"],
    "agents": ["AI agent API", "crypto market data API", "pay per call", "x402", "crypto signals", "MCP server", "RLUSD", "USDC on Base",
               "institutional policy brief"],
    "trust": ["x402 vendor reputation", "trust score", "x402", "AI agent API", "pay per call", "XRPL", "USDC on Base"],
}

ORG_DESC = ("Lumi Trades publishes an AI's crypto market analysis and paper-trade ideas, and sells crypto market data to AI agents "
            "through a pay-per-call x402 API and an MCP server.")
API_NAME = "Lumi Trades API"
API_DESC = ("Pay-per-call crypto market data API for AI agents: trading signals, support and resistance levels, CoinMarketCap Fear & Greed "
            "sentiment, a daily market brief and a daily Institutional & Policy Brief (BIS, IMF, CBDCs, stablecoin rules, tokenization). "
            "No account or API key: pay each call with x402 in USDC on Base, or XRP, RLUSD or USDC on the XRP Ledger.")


def keywords(t, page, en):
    """Comma-separated keywords meta for a page: page-specific terms first, translated generic terms plus the English ones."""
    order = KW_PAGE.get(page, []) + [k for k in KW_GENERIC + KW_NAMES if k not in KW_PAGE.get(page, [])]
    out = []
    for k in order:
        for v in ([k] if en or k in KW_NAMES else [t(k), k]):
            if v not in out:
                out.append(v)
    return ", ".join(out)


def organization(t):
    return {"@context": "https://schema.org", "@type": "Organization", "@id": ORG_ID, "name": "Lumi Trades", "url": SITE,
            "logo": {"@type": "ImageObject", "url": LOGO}, "description": t(ORG_DESC), "sameAs": SAME_AS,
            "knowsAbout": KW_GENERIC + KW_NAMES}


def website(t, url, lang, desc):
    return {"@context": "https://schema.org", "@type": "WebSite", "@id": SITE_ID, "name": "Lumi Trades", "alternateName": "Lumi Trades crypto dashboard",
            "url": url, "description": desc, "inLanguage": lang, "publisher": {"@id": ORG_ID},
            "keywords": keywords(t, "home", lang == "en")}


def _price(p):
    return "0" if p == "free" else p.lstrip("$")


def web_api(t, lang, prices, page_url=None, full=True):
    """schema.org WebAPI (a Service) with one Offer per endpoint (USD per call) or, when full=False, an AggregateOffer."""
    vals = [float(_price(p)) for _n, _e, p in prices]
    node = {"@context": "https://schema.org", "@type": "WebAPI", "@id": API_ID, "name": API_NAME, "url": API + "/",
            "description": t(API_DESC), "documentation": API + "/openapi.json",
            "provider": {"@id": ORG_ID}, "serviceType": t("Pay-per-call crypto market data API for AI agents"),
            "areaServed": "Worldwide", "audience": {"@type": "Audience", "audienceType": t("AI agents and developers")},
            "availableChannel": [{"@type": "ServiceChannel", "name": "HTTPS (x402)", "serviceUrl": API + "/"},
                                 {"@type": "ServiceChannel", "name": "MCP (streamable HTTP)", "serviceUrl": API + "/mcp"}],
            "keywords": keywords(t, "agents", lang == "en"), "inLanguage": lang}
    if page_url:
        node["mainEntityOfPage"] = page_url
    if not vals:
        pass
    elif full:
        node["offers"] = [{"@type": "Offer", "name": t(n), "description": e, "price": _price(p), "priceCurrency": "USD",
                           "priceSpecification": {"@type": "UnitPriceSpecification", "price": _price(p), "priceCurrency": "USD",
                                                  "unitText": t("per call")}, "seller": {"@id": ORG_ID}}
                          for n, e, p in prices]
    else:
        node["offers"] = {"@type": "AggregateOffer", "lowPrice": f"{min(vals):g}", "highPrice": f"{max(vals):g}", "priceCurrency": "USD",
                          "offerCount": len(prices), "url": SITE + "agents/"}
    return node


TRUST_DS_NAME = "Lumi x402 vendor trust list"
TRUST_DS_DESC = ("Automated observations of x402 pay-per-call endpoints that AI agents can buy from: free checks that each endpoint "
                 "returns a valid 402 payment quote, small paid test-buys with links to the on-ledger transactions (Base, XRP Ledger), "
                 "and a 30-day trust score with a confidence level per vendor. Updated regularly; free to read as JSON. "
                 "Observations, not a rating or review of any business.")


def trust_dataset(t, lang, page_url, doc, vendors_url):
    n = len((doc or {}).get("vendors") or [])
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": t(TRUST_DS_NAME), "description": t(TRUST_DS_DESC),
          "url": page_url, "sameAs": vendors_url, "inLanguage": lang, "isAccessibleForFree": True,
          "creator": {"@id": ORG_ID}, "publisher": {"@id": ORG_ID},
          "keywords": keywords(t, "trust", lang == "en"),
          "measurementTechnique": t("Automated 402-quote checks and small paid x402 test-buys"),
          "variableMeasured": [t("Trust score (0-100)"), t("Confidence"), t("Paid test-buys"), t("Paid buys that returned data"), t("Last checked")],
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": vendors_url}],
          "isBasedOn": API + "/v1/trust/methodology"}
    if (doc or {}).get("generated_at"):
        ds["dateModified"] = doc["generated_at"]
    if n:
        ds["size"] = t("{n} vendors", n=n)
    return ds


# /agents/ FAQ: (question, answer). Answers are plain text (also used as FAQPage JSON-LD), facts only.
FAQ = [
    ("How can my AI agent get crypto trading signals?",
     "Call GET https://api.lumitrades.io/v1/signal/{coin} (for example /v1/signal/XRP). The first call answers 402 Payment Required "
     "with a quote; the agent pays $0.01 with x402 and repeats the call with the signed payment to get a buy/sell read built from RSI, "
     "MACD and EMA. MCP clients can use the same data through https://api.lumitrades.io/mcp. "
     "The signals are data from an AI's paper-trading experiment, not financial advice."),
    ("Is there a pay-per-call crypto API for AI agents?",
     "Yes. The Lumi Trades API sells crypto signals, support and resistance levels, CoinMarketCap Fear & Greed sentiment, the daily "
     "paper-trade slate, a daily market brief and a daily Institutional & Policy Brief for $0.003 to $0.25 per call. There is no account, "
     "subscription or API key: every call is paid on its own with x402, and if the data is not fresh the API answers 503 and nothing is charged."),
    ("What is x402?",
     "x402 is an open payment protocol built on the HTTP status code 402 Payment Required, first published by Coinbase. A server answers "
     "a request with a price quote, the client pays it in a stablecoin or another crypto asset and repeats the request with the signed "
     "payment, and the server returns the data with a receipt. It lets software, including AI agents, pay per request without accounts "
     "or subscriptions."),
    ("How do I check if an x402 service is trustworthy?",
     "Before paying, check that the endpoint returns a valid 402 quote and that the pay-to address and price match its documentation. "
     "Independent observations help too: Lumi's free vendor trust list at lumitrades.io/trust/ records automated quote checks and small "
     "paid test-buys of x402 endpoints, each paid buy linked to its transaction on a public ledger explorer, with a 30-day score and a "
     "confidence level. Start with small amounts and a per-call spending cap. The list is observations, not a rating of any business."),
    ("How do I pay an API with XRP or RLUSD?",
     "With x402 on the XRP Ledger: the 402 quote lists XRPL options (XRP, RLUSD or USDC) with the amount, pay-to address and invoice "
     "details. Your client signs an XRPL Payment for exactly that amount and sends it in the PAYMENT-SIGNATURE header; the API verifies "
     "it on-ledger and returns the data with a PAYMENT-RESPONSE receipt. To pay in RLUSD or USDC the paying wallet needs a trust line to "
     "the token's issuer and a balance."),
    ("Can I pay with USDC on Base?",
     "Yes. Every quote also offers USDC on Base (eip155:8453), settled through Coinbase's x402 facilitator, so Coinbase AgentKit and other "
     "x402 clients work without extra setup."),
    ("Is there an MCP server for crypto market data?",
     "Yes. Add https://api.lumitrades.io/mcp as a remote MCP server (streamable HTTP) in Claude, Cursor or any MCP client. Free tools list "
     "the catalog, coins, quotes and vendor scores; paid tools use the same x402 prices. A local option is the npm package lumi-trades-mcp, "
     "which pays per call from the agent's own funds with a spending cap."),
    ("What does the Institutional & Policy Brief cover?",
     "It is a daily, sourced summary of what central banks, standard-setters and regulators (for example the BIS, the IMF and US regulators), "
     "banks and tokenization firms are doing on stablecoins, CBDCs and tokenization, and how each item relates to XRP, XLM, XDC, QNT, AXL "
     "and HBAR, marking confirmed links apart from indirect ones. One call costs $0.25 at GET /v1/institutional."),
    ("Where does the Fear & Greed reading come from?",
     "Only from the CoinMarketCap Fear & Greed Index. GET /v1/sentiment ($0.005) returns it together with BTC funding and market breadth."),
]


def faq_ld(t):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": t(q), "acceptedAnswer": {"@type": "Answer", "text": t(a)}} for q, a in FAQ]}


def faq_html(t, E):
    items = "".join(f'<details class="cp-faq"{" open" if i == 0 else ""}><summary>{E(t(q))}</summary><p>{E(t(a))}</p></details>'
                    for i, (q, a) in enumerate(FAQ))
    return f'<section class="card cp-sec" id="faq"><h2>{E(t("Questions agents and developers ask"))}</h2>{items}</section>'


def llms_txt(prices, plans=()):
    """/llms.txt (llmstxt.org format): where an LLM or agent finds the API docs and the human pages. English only."""
    rows = "\n".join(f"- `{e}`: {n}, {p if p == 'free' else p + ' per call'}" for n, e, p in prices)
    plan_rows = "\n".join(f"- {n}: {fmt.format(p=p)}. {d}" for n, (fmt, p), d in plans)
    return f"""# Lumi Trades

> Crypto market data for people and AI agents: live prices, crypto and trading signals (RSI, MACD, EMA), support and resistance
> levels, CoinMarketCap Fear & Greed, an AI's paper-trade ideas, a daily market brief and a daily Institutional & Policy Brief
> (BIS, IMF, CBDCs, stablecoins, tokenization). AI agents buy the data per call with x402 (USDC on Base, or XRP, RLUSD or USDC on
> the XRP Ledger); no account or API key. A free x402 vendor trust list records test-buys of other pay-per-call endpoints.
> Data from a paper-trading experiment, not financial advice.

## API docs (api.lumitrades.io)
- [API home](https://api.lumitrades.io/): overview, prices and the 402 flow
- [OpenAPI spec](https://api.lumitrades.io/openapi.json): every endpoint, parameter and response
- [Agent skill (skill.md)](https://api.lumitrades.io/skill.md): step-by-step guide for an agent to pay and call the API
- [x402 discovery](https://api.lumitrades.io/.well-known/x402): machine-readable list of paid resources and accepted payments
- [MCP server](https://api.lumitrades.io/mcp): remote MCP (streamable HTTP); local option `npx -y lumi-trades-mcp`
- [Trust methodology](https://api.lumitrades.io/v1/trust/methodology): how vendor trust scores are computed

## Pages
- [For AI agents](https://lumitrades.io/agents/): what the API sells, prices, how to pay, MCP setup and FAQ
- [x402 vendor trust list](https://lumitrades.io/trust/): automated quote checks and paid test-buys of x402 endpoints, with on-ledger evidence
- [How Lumi works](https://lumitrades.io/how-it-works/): how the buy/sell signals are scored, how paper-trade ideas, leverage caps and Missed-it plans are set, and the tracker's fill/stop/target rules (also in es, pt, tr, ko, ja)
- [Dashboard](https://lumitrades.io/): live prices, signals and today's paper-trade ideas (also in es, pt, tr, ko, ja)

## Prices (USD per call)
{rows}

## Seller monitoring and trust data feed (x402, 30-day plans, no auto-renew)
{plan_rows}
- [Seller monitoring](https://api.lumitrades.io/v1/monitor) · [Trust data feed](https://api.lumitrades.io/v1/feed) · [Feed licence](https://api.lumitrades.io/v1/feed/license)

## Optional
- [Vendor trust list as JSON](https://api.lumitrades.io/v1/trust/vendors): free
- [Sitemap](https://lumitrades.io/sitemap.xml)
"""
