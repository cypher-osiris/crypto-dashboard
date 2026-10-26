"""/top-sellers/: x402 sellers that kept delivering in Lumi's own paid test-buys, grouped by what they sell.
Called from site_pages.build(). Rows come ONLY from scripts/top_sellers_snapshot.json, which
scripts/top_sellers_refresh.py fetches from Lumi's public results (api.lumitrades.io/badge/<key>.json, the same stored
results as api.lumitrades.io/trust/v/<key>). Never hand-write a row.

Rules (keep the page text in sync with qualifies() and ordering()):
- inclusion comes only from test results: latest conclusive test-buy delivered AND at least MIN_DELIVERED of the last
  WINDOW conclusive test-buys delivered AND the latest test-buy is at most MAX_AGE_DAYS old (inconclusive = Lumi-side, not counted)
- sellers that don't qualify are simply not shown: no "bad list", no failure counts, never call anyone a scam
- order within a category: delivered count in the window, then most recent test, then key. Payment is never an input.
- categories come from the seller's public catalog description (CDP x402 Bazaar) or its curated name, via CATEGORIES
- no P&L, never name a person
"""
import datetime as dt
import json
import os
import re
import types
import urllib.parse

import seo

SLUG = "top-sellers/"
LIVE_LANGS = ("en", "es", "pt", "tr", "ko", "ja")
SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "top_sellers_snapshot.json")
API = "https://api.lumitrades.io"
CONTACT = "hello@lumitrades.io"
MIN_DELIVERED, WINDOW, MAX_AGE_DAYS = 2, 3, 45

TITLE = "x402 APIs with delivered test-buys, by category | Lumi Trades"
H1 = "Sellers with delivered test-buys, by category"
DESC = ("x402 APIs that delivered in Lumi's own paid test-buys, grouped by what they sell: data APIs, AI tools, "
        "search and pre-payment checks. Chosen from test results only; paying Lumi never changes who is listed or the order.")
LEDE = ("These x402 sellers delivered data in Lumi's recent paid test-buys. Sample sizes are small; this is not a ranking or "
        "an endorsement. We buy from them with our own money and record every result. This list is built from those results only.")
RULE_HEAD = "How a seller gets on this list"
RULE = [
    "A seller is listed when its latest paid test-buy delivered data, at least {n} of its last {m} paid test-buys delivered data, and its latest test-buy is less than {days} days old.",
    "Inconclusive test-buys (we never saw a response, a problem on our side) are not counted.",
    "Most sellers have been test-bought only once so far. They can appear here after their next test-buy.",
    "Within each category, sellers with more delivered test-buys come first, then the most recently tested.",
    "Categories come from each seller's public description in Coinbase's x402 Bazaar catalog, or from our own seller list.",
    "<b>Paying Lumi never changes who is listed or the order.</b> See our <a href=\"{policy}\">conflicts policy</a>.",
    "This is a record of past test results, not an endorsement or a guarantee. Past results do not predict future ones. Questions about an entry: <a href=\"mailto:{mail}\">{mail}</a>.",
]
CATEGORIES = [  # (id, label, keyword regex on description + name + endpoint path); most hits wins
    ("checks", "Pre-payment checks and validation", r"preflight|\bsafe\b|safety|honeypot|rug pull|\bchecks?\b|ofac|sanctions screen|screening|validat|reachab|facilitator"),
    ("ai", "AI and LLM tools", r"chat/completions|chat completion|\bllm\b|openai|\bgpt|language model|agent question|inference|prompt"),
    ("weather", "Weather", r"weather|forecast|temperature"),
    ("search", "Search and web data", r"search|wikipedia|web page|scrape|crawl|listings|news"),
    ("market", "Finance and crypto data APIs", r"price|\bmarkets?\b|crypto|token|perp|funding|exchange rate|\bfx\b|currenc|macro|\bcpi\b|options|premium|\bamm\b|signal|stock"),
    ("other", "Other tools", r""),
]
CAT_LABEL = {c: l for c, l, _ in CATEGORIES}
L_SELLER, L_CHAINS, L_LAST, L_DELIV, L_RESULT = "Seller", "Chains", "Last tested", "Delivered", "Results"
L_OF, L_VIEW = "{d} of {n}", "View results"
L_ASOF = "Data as of {date}. Test dates are in UTC."
L_COUNT = "Sellers: {n}"
L_EMPTY = "No seller meets the rule yet."
FOOTER_LINK = "Sellers with delivered test-buys"
TRUST_NOTE = "x402 sellers that delivered in our recent paid test-buys, by category."


def _ts(s):
    return dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


def load(path=SNAPSHOT):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"generated_at": None, "sellers": []}


def conclusive(s):
    return [t for t in s.get("tests", []) if t.get("verdict") in ("delivered", "not_delivered")]


def qualifies(s, now):
    t = conclusive(s)[:WINDOW]  # newest first
    if not t or t[0]["verdict"] != "delivered":
        return False
    if sum(x["verdict"] == "delivered" for x in t) < MIN_DELIVERED:
        return False
    return (now - _ts(t[0]["at"])).days < MAX_AGE_DAYS


def category(s):
    ep = s["tests"][0].get("endpoint") or "" if s.get("tests") else ""
    text = " ".join([s.get("desc") or "", s.get("name") or "", urllib.parse.urlparse(ep).path.replace("-", " ").replace("_", " ")]).lower()
    best, hits = "other", 0
    for cid, _l, rx in CATEGORIES:  # most keyword hits wins; ties go to the earlier category
        n = len(re.findall(rx, text)) if rx else 0
        if n > hits:
            best, hits = cid, n
    return best


def ordering(s):
    t = conclusive(s)[:WINDOW]
    return (-sum(x["verdict"] == "delivered" for x in t), -_ts(t[0]["at"]).timestamp(), s["key"])


def rows(snap=None, now=None):
    """{category id: [row, ...]} in CATEGORIES order (empty categories dropped). Each row: key, name, host, chains, last, delivered, window, url."""
    snap = snap if snap is not None else load()
    now = now or (_ts(snap["generated_at"]) if snap.get("generated_at") else dt.datetime.now(dt.timezone.utc))
    out = {c: [] for c, _l, _r in CATEGORIES}
    for s in sorted((s for s in snap.get("sellers", []) if qualifies(s, now)), key=ordering):
        t = conclusive(s)[:WINDOW]
        chains = sorted({x.get("chain") for x in s["tests"] if x.get("chain") and x["verdict"] == "delivered"})
        host = urllib.parse.urlparse(t[0].get("endpoint") or "").hostname or s["key"]
        out[category(s)].append({"key": s["key"], "name": s.get("name") or s["key"], "host": host, "chains": chains,
                                 "last": t[0]["at"], "delivered": sum(x["verdict"] == "delivered" for x in t), "window": len(t),
                                 "url": f"{API}/trust/v/{urllib.parse.quote(s['key'], safe='')}"})
    return {c: r for c, r in out.items() if r}


def lastmod():
    g = load().get("generated_at")
    return g[:10] if g else None


def footer_link(h, home):
    if h.L.code not in LIVE_LANGS:
        return ""
    return f' · <a href="{home}{SLUG}">{h.E(h._(FOOTER_LINK))}</a>'


def build_page(h, tp, nav_items, V, gen_date, page):
    if h.L.code not in LIVE_LANGS:
        return None
    h = types.SimpleNamespace(**{**vars(h), "langs": [x for x in h.langs if x.code in LIVE_LANGS]})
    E, _t = h.E, h._
    snap = load()
    cats = rows(snap)
    title, desc, h1 = _t(TITLE), _t(DESC), _t(H1)
    url = h.SITE + h.L.prefix + SLUG
    items, pos = [], 0
    for c, rs in cats.items():
        for r in rs:
            pos += 1
            items.append({"@type": "ListItem", "position": pos, "name": r["name"], "url": r["url"]})
    ld = [seo.organization(_t),
          {"@context": "https://schema.org", "@type": "CollectionPage", "name": h1, "url": url, "description": desc,
           "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           **({"dateModified": snap["generated_at"][:10]} if snap.get("generated_at") else {}),
           "mainEntity": {"@type": "ItemList", "numberOfItems": pos, "itemListElement": items}},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": h1, "item": url}]}]

    def day(iso):
        t = _ts(iso)
        return h.L.date(dt.datetime(t.year, t.month, t.day), with_time=False)

    rule = "".join(f"<p>{_t(p, n=MIN_DELIVERED, m=WINDOW, days=MAX_AGE_DAYS, policy='../trust-policy/', mail=CONTACT) if ('<' in p or '{' in p) else E(_t(p))}</p>" for p in RULE)
    toc = " · ".join(f'<a href="#{c}">{E(_t(CAT_LABEL[c]))} ({len(rs)})</a>' for c, rs in cats.items())
    secs = ""
    for c, rs in cats.items():
        trs = "".join(
            f'<tr><td>{E(r["name"])}' + (f'<br><span class="meta mono">{E(r["host"])}</span>' if r["host"] != r["name"] else "") + "</td>"
            f'<td>{E(", ".join(r["chains"]))}</td><td>{E(day(r["last"]))}</td>'
            f'<td>{E(_t(L_OF, d=r["delivered"], n=r["window"]))}</td>'
            f'<td><a href="{E(r["url"])}" rel="noopener">{E(_t(L_VIEW))}</a></td></tr>' for r in rs)
        secs += (f'<section class="card cp-sec" id="{c}"><h2>{E(_t(CAT_LABEL[c]))}</h2>'
                 f'<p class="meta">{E(_t(L_COUNT, n=len(rs)))}</p>'
                 f'<div class="cp-tablewrap"><table class="cp-table cp-stack cp-stack-r"><thead><tr><th>{E(_t(L_SELLER))}</th><th>{E(_t(L_CHAINS))}</th>'
                 f'<th>{E(_t(L_LAST))}</th><th>{E(_t(L_DELIV))}</th><th>{E(_t(L_RESULT))}</th></tr></thead><tbody>{trs}</tbody></table></div></section>\n')
    if not cats:
        secs = f'<section class="card cp-sec"><p>{E(_t(L_EMPTY))}</p></section>\n'
    asof = f'<p class="meta">{E(_t(L_ASOF, date=day(snap["generated_at"])))}</p>' if snap.get("generated_at") else ""
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(h1)}</p>
<h1>{E(h1)}</h1>
{asof}
<p class="cp-lede">{E(_t(LEDE))}</p>
<p class="meta">{toc}</p>
{secs}<section class="card cp-sec" id="rule"><h2>{E(_t(RULE_HEAD))}</h2>
{rule}</section>
</main>
"""
    return page(h, tp, SLUG, title, desc, ld, body, V, gen_date, nav_items, "trust", keywords=None)
