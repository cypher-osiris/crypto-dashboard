"""Static info pages, one per language: /agents/ (Lumi's pay-per-call API for AI agents) and /trust/ (x402 vendor
observations), plus /llms.txt. SEO bits (keywords, JSON-LD, the /agents/ FAQ) live in seo.py. Called by build_pages.py inside its language loop with the same helper namespace `h` that
trade_pages.py gets (h.E, h._, h.L, h.SITE, h.ctime, h.langs, h.i18n, h.head_i18n, h.i18n_scripts, ...).

/trust/ is rendered to static HTML at build time from https://api.lumitrades.io/v1/trust/vendors (fetched once per
build, cached in state/trust_vendors.json, which is git-ignored; if the API is down the cache is used). assets/trust.js
then refreshes the table live from the same free endpoint. Every routine that runs scripts/publish.sh with data/ files
(dashboard update, trade tracker) rebuilds the pages, so the static table stays fresh without a separate job.
"""
import json
import os
import urllib.request

import seo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.lumitrades.io"
VENDORS_URL = API + "/v1/trust/vendors"
CACHE = os.path.join(ROOT, "state", "trust_vendors.json")
BAZAAR = "https://docs.cdp.coinbase.com/x402/bazaar"
X402SCAN = "https://www.x402scan.com/server/0b8315c8-da5e-4754-8564-e9f286edcbae"
MCP_REG = "https://registry.modelcontextprotocol.io/v0/servers?search=lumi-trades"
NPM = "https://www.npmjs.com/package/lumi-trades-mcp"

# (product, method + path, price in USD); keys are translated, paths and prices are not
PRICES = [
    ("Signal per coin (buy/sell read, RSI/MACD/EMA)", "GET /v1/signal/{coin}", "$0.01"),
    ("Support / resistance levels + 7-day projection", "GET /v1/levels/{coin}", "$0.01"),
    ("Crypto sentiment (CoinMarketCap Fear & Greed, funding)", "GET /v1/sentiment", "$0.01"),
    ("Yen carry-trade watch (USD/JPY, Nikkei)", "GET /v1/macro/yen", "$0.015"),
    ("Market slate (today's paper-trade ideas)", "GET /v1/slate", "$0.02"),
    ("BTC + macro market backdrop", "GET /v1/market", "$0.02"),
    ("Crypto events calendar (next 48 hours)", "GET /v1/events", "$0.01"),
    ("Active trade ideas with entries, stops and targets", "GET /v1/trades", "$0.02"),
    ("Daily crypto market brief", "GET /v1/brief", "$0.03"),
    ("Daily Institutional & Policy Brief", "GET /v1/institutional", "$0.25"),
    ("Detailed vendor report (full observation history)", "GET /v1/trust/vendors/{id}/report", "$0.02"),
    ("Vendor trust list", "GET /v1/trust/vendors", "free"),
]

CURL = """# 1. ask: no key, no account. The API answers 402 with a quote
curl -i https://api.lumitrades.io/v1/signal/XRP
#    HTTP/2 402
#    PAYMENT-REQUIRED: <base64 JSON: price, networks (Base USDC, XRPL XRP/RLUSD/USDC), payTo>

# 2. pay with any x402 client, then repeat the call with the signed payment
curl https://api.lumitrades.io/v1/signal/XRP -H "PAYMENT-SIGNATURE: <payment payload>"
#    HTTP/2 200 + the data, PAYMENT-RESPONSE: <settlement receipt>"""

MCP = """{ "mcpServers": {
  "lumi": { "url": "https://api.lumitrades.io/mcp" }
} }"""


def fetch_vendors(dry=False):
    """The vendor list: live API first (short timeout), else the last good copy in state/. Never raises."""
    doc = None
    if not dry:
        try:
            req = urllib.request.Request(VENDORS_URL, headers={"Accept": "application/json", "User-Agent": "lumitrades.io build"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("kind") == "trust_vendors" and isinstance(d.get("vendors"), list):
                doc = d
                try:
                    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
                    tmp = CACHE + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(d, f)
                    os.replace(tmp, CACHE)
                except OSError:
                    pass
        except Exception as e:
            print(f"site_pages: trust vendors fetch failed ({e!r}), using cache", flush=True, file=__import__("sys").stderr)
    if doc is None:
        try:
            with open(CACHE, encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            doc = None
    return doc


def _https(u):
    return u if isinstance(u, str) and u.lower().startswith("https://") else ""


def _last_checked(v):
    t = [p.get("checked_at") for p in (v.get("latest_probes") or []) if p and p.get("checked_at")]
    o = v.get("last_paid_observation") or {}
    if o.get("observed_at"):
        t.append(o["observed_at"])
    return max(t) if t else None


def vendor_row(h, v):
    E, _t = h.E, h._
    s = v.get("samples") or {}
    o = v.get("last_paid_observation") or None
    home = _https(v.get("homepage"))
    nm = E(v.get("name") or v.get("id"))
    name = f'<a href="{E(home)}" target="_blank" rel="noopener nofollow">{nm}</a>' if home else nm
    conf = str(v.get("confidence") or "—")
    ev = "—"
    if o and _https(o.get("explorer")):
        ev = (f'<a href="{E(o["explorer"])}" target="_blank" rel="noopener" title="{E(o.get("summary") or "")}">'
              f'{E(((o.get("amount") or "") + " " + (o.get("asset") or "")).strip())} · {E(_t("data") if o.get("data_returned") else _t("no data"))} ↗</a>')
    if v.get("replies") and _https(v.get("detail")):
        ev += f' <a href="{E(v["detail"])}" target="_blank" rel="noopener">· {E(_t("reply ({n})", n=v["replies"]))}</a>'
    lc = _last_checked(v)
    return (f'<tr><td>{name}<span class="vid">{E(v.get("id"))}</span></td>'
            f'<td class="num">{"—" if v.get("score") is None else E(v.get("score"))}</td>'
            f'<td><span class="tr-conf c-{E(conf)}">{E(_t(conf) if conf in ("low", "medium", "high") else conf)}</span></td>'
            f'<td class="num">{E(s.get("paid_test_buys") or 0)}</td><td class="num">{E(s.get("delivered") or 0)}</td>'
            f'<td>{E(h.ctime(lc)) if lc else "—"}</td><td>{ev}</td></tr>')


def _page(h, tp, path, title, desc, ld, body, V, gen_date, nav_items, current, extra_js="", keywords=None):
    up = "" if h.L.en else "../"
    R = "../" + up
    head = tp.page_head(h, title, desc, h.SITE + h.L.prefix + path, V, path, "website", ld, keywords).replace(
        "{ASSETS}", tp.assets(h, R, V) + extra_js.replace("{R}", R).replace("{V}", V))
    return head + tp.chrome(h, R, "../", nav_items, V, path, current) + body + tp.footer(h, R, gen_date)


AGENTS_DESC = ("Pay-per-call crypto API for AI agents: trading signals, support and resistance levels, CoinMarketCap Fear & Greed, "
               "a daily brief and an Institutional & Policy Brief (BIS, IMF, CBDCs, stablecoins, tokenization). Pay with x402 in USDC "
               "on Base or XRP and RLUSD on the XRPL. MCP server, no API key.")
TRUST_DESC = ("x402 vendor reputation: free trust scores for pay-per-call endpoints from Lumi's automated 402-quote checks and small "
              "paid test-buys, with on-ledger evidence on Base and the XRP Ledger. Observations, not a rating or review of any business.")


def agents_page(h, tp, nav_items, V, gen_date):
    E, _t = h.E, h._
    rows = "".join(f'<tr><td>{E(_t(p))}</td><td class="mono">{E(ep)}</td><td class="num mono">{E(_t(pr) if pr == "free" else pr)}</td></tr>' for p, ep, pr in PRICES)
    title = _t("Crypto market data API for AI agents, pay per call with x402 | Lumi Trades")
    desc = _t(AGENTS_DESC)
    url = h.SITE + h.L.prefix + "agents/"
    ld = [seo.organization(_t), seo.web_api(_t, h.L.code, PRICES, url),
          {"@context": "https://schema.org", "@type": "WebPage", "name": title.replace(" | Lumi Trades", ""), "url": url, "description": desc,
           "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "about": {"@id": seo.API_ID}, "publisher": {"@id": seo.ORG_ID},
           "keywords": seo.keywords(_t, "agents", h.L.en)},
          seo.faq_ld(_t),
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": _t("For AI agents"), "item": h.SITE + h.L.prefix + "agents/"}]}]
    lk = lambda href, txt: f'<a href="{href}" target="_blank" rel="noopener">{E(txt)}</a>'
    body = f"""<main class="wrap cp-main ag-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(_t("For AI agents"))}</p>
<h1>{E(_t("Lumi's crypto data for AI agents"))}</h1>
<p class="cp-lede">{_t("Lumi sells crypto market data to AI agents one HTTP call at a time: coin signals, support and resistance levels, the daily paper-trade slate, market briefs and a free trust list of other x402 vendors. No account and no API key: the API answers <code>402 Payment Required</code> with a quote, the agent pays a few cents, and gets the data.")}</p>
<section class="card cp-sec" id="prices"><h2>{E(_t("What it costs"))}</h2>
<div class="cp-tablewrap"><table class="cp-table"><thead><tr><th>{E(_t("Product"))}</th><th>{E(_t("Endpoint"))}</th><th class="num">{E(_t("Price"))}</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="meta">{_t("Prices per call in USD. If the data isn't fresh the API answers 503 and you are not charged. Free: <code>/v1/coins</code>, <code>/openapi.json</code>, <code>/skill.md</code>, <code>/.well-known/x402</code>.")}</p></section>
<section class="card cp-sec" id="pay"><h2>{E(_t("How to pay"))}</h2>
<ul class="ag-list"><li>{_t("<b>USDC on Base</b> (eip155:8453), settled through Coinbase's x402 facilitator. Works with Coinbase AgentKit and any x402 client.")}</li>
<li>{_t("<b>XRP Ledger</b>: XRP, RLUSD or USDC, verified on-ledger.")}</li></ul>
<p class="meta">{_t("The 402 quote lists every accepted network, asset, amount and pay-to address; pick one. Headers: <code>PAYMENT-REQUIRED</code>, <code>PAYMENT-SIGNATURE</code>, <code>PAYMENT-RESPONSE</code>.")}</p></section>
<section class="card cp-sec" id="flow"><h2>{E(_t("The 402 flow in two calls"))}</h2>
<pre class="ag-code"><code>{E(CURL)}</code></pre></section>
<section class="card cp-sec" id="mcp"><h2>{E(_t("MCP server"))}</h2>
<p>{_t("Remote MCP (streamable HTTP) for Claude, Cursor or any MCP client. Free tools list the catalog, coins, quotes and vendor scores; paid tools use the same x402 prices.")}</p>
<pre class="ag-code"><code>{E(MCP)}</code></pre>
<p class="meta">{_t("Local option: <code>npx -y lumi-trades-mcp</code> (npm package <code>lumi-trades-mcp</code>), which pays per call from your agent's own funds with a per-call spending cap; settings are in the package README. Registry name: <code>io.github.cypher-osiris/lumi-trades-mcp</code>.")}</p></section>
<section class="card cp-sec" id="links"><h2>{E(_t("Links"))}</h2>
<ul class="ag-list">
<li>{lk(API + "/", "api.lumitrades.io")} · {lk(API + "/openapi.json", "openapi.json")} · {lk(API + "/skill.md", "skill.md")} · {lk(API + "/.well-known/x402", ".well-known/x402")}</li>
<li><a href="../trust/">{E(_t("Vendor trust list (free)"))}</a></li>
<li>{lk(BAZAAR, _t("Coinbase x402 Bazaar"))} · {lk(X402SCAN, "x402scan")}</li>
<li>{lk(MCP_REG, _t("Official MCP Registry"))} · {lk(NPM, "npm: lumi-trades-mcp")} · {lk(API + "/a2a", "A2A")}</li></ul></section>
{seo.faq_html(_t, E)}
<div class="disclaimer" role="note"><span class="warn-ico" aria-hidden="true">!</span><span>{_t("<strong>Data, not financial advice.</strong> Signals and trade ideas come from an AI's paper-trading experiment; no real money is traded.")}</span></div>
</main>
"""
    return _page(h, tp, "agents/", title, desc, ld, body, V, gen_date, nav_items, "agents", keywords=seo.keywords(_t, "agents", h.L.en))


def trust_page(h, tp, nav_items, V, gen_date, doc):
    E, _t = h.E, h._
    vendors = (doc or {}).get("vendors") or []
    title = _t("x402 vendor trust list: Lumi's automated test-buys | Lumi Trades")
    desc = _t(TRUST_DESC)
    url = h.SITE + h.L.prefix + "trust/"
    ld = [seo.organization(_t),
          {"@context": "https://schema.org", "@type": "WebPage", "name": _t("x402 vendor trust list"), "url": url,
           "description": desc, "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           "keywords": seo.keywords(_t, "trust", h.L.en)},
          seo.trust_dataset(_t, h.L.code, url, doc, VENDORS_URL),
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": _t("Vendor trust"), "item": h.SITE + h.L.prefix + "trust/"}]}]
    rows = "".join(vendor_row(h, v) for v in vendors)
    gen = (doc or {}).get("generated_at")
    status = "" if vendors else f'<p id="tr-status" class="muted">{E(_t("Loading observations…"))}</p>'
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(_t("Vendor trust"))}</p>
<h1>{E(_t("x402 vendor trust list"))}</h1>
<p class="cp-lede">{_t("Lumi checks pay-per-call (x402) endpoints that agents can buy from: a free check that each endpoint returns a valid payment quote, plus small paid test-buys. Each paid test-buy links to its transaction on a public ledger explorer. The list is free; a detailed report on one vendor costs $0.02.")}</p>
<div class="disclaimer" role="note"><span class="warn-ico" aria-hidden="true">!</span><span>{_t("<strong>Automated observations, not a rating or review of any business.</strong> Scores summarize what Lumi's own checks saw over the last 30 days. Few samples = low confidence.")} <a href="{API}/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("Methodology"))}</a></span></div>
<section class="card cp-sec">
<h2>{E(_t("Vendors"))} <span class="muted" id="tr-count">{f"({len(vendors)})" if vendors else ""}</span></h2>
{status}
<div class="tr-wrap"><table class="cp-table tr-table" id="tr-table"{"" if vendors else " hidden"}>
<thead><tr><th>{E(_t("Vendor"))}</th><th class="num">{E(_t("Score"))}</th><th>{E(_t("Confidence"))}</th><th class="num">{E(_t("Paid buys"))}</th><th class="num">{E(_t("Delivered"))}</th><th>{E(_t("Last checked"))}</th><th>{E(_t("Evidence"))}</th></tr></thead>
<tbody id="tr-body">{rows}</tbody></table></div>
<p class="meta">{E(_t("Listed in allowlist order, not ranked. \"Paid buys\" = paid test-buys in the window; \"Delivered\" = paid buys whose response contained data. \"Last checked\" = the most recent free quote check or paid test-buy. Evidence links to the latest paid test-buy's transaction. Times in US Central."))} <span id="tr-gen">{E(_t("Data generated {when}.", when=h.ctime(gen))) if gen else ""}</span></p>
<p class="meta">{E(_t("Raw data:"))} <a href="{VENDORS_URL}" target="_blank" rel="noopener">api.lumitrades.io/v1/trust/vendors</a> · <a href="{API}/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("How scores are computed"))}</a> · <a href="../agents/">{E(_t("Lumi's data for AI agents →"))}</a></p>
</section>
<section class="card cp-sec" id="reply">
<h2>{E(_t("Right to reply"))}</h2>
<p>{_t("If you run one of these endpoints and think an observation is wrong or missing context, you can add a reply that is shown with your entry. Email <a href=\"mailto:hello@lumitrades.io\">hello@lumitrades.io</a>, or post a signed reply to <code>POST https://api.lumitrades.io/v1/trust/replies</code>, signed with the key of a pay-to address listed for your entry (details in the methodology). We can also re-run a check or remove an endpoint from the list on request.")}</p>
</section>
</main>
"""
    js = '<script src="{R}assets/trust.js?v={V}" defer></script>\n'
    return _page(h, tp, "trust/", title, desc, ld, body, V, gen_date, nav_items, "trust", js, seo.keywords(_t, "trust", h.L.en))


def build(h, tp, nav_items, V, gen_date, write, vendors_doc):
    """Writes [<lang>/]agents/index.html, [<lang>/]trust/index.html and (English pass) /llms.txt. Returns sitemap entries (language-relative)."""
    P = h.L.prefix
    write(f"{P}agents/index.html", agents_page(h, tp, nav_items, V, gen_date))
    write(f"{P}trust/index.html", trust_page(h, tp, nav_items, V, gen_date, vendors_doc))
    if h.L.en:
        write("llms.txt", seo.llms_txt(PRICES))
    lm = ((vendors_doc or {}).get("generated_at") or gen_date)[:10]
    return [("agents/", gen_date, "weekly", "0.8"), ("trust/", lm, "daily", "0.7")]
