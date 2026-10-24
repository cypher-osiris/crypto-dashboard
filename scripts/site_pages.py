"""Static info pages, one per language: /agents/ (Lumi's pay-per-call API for AI agents) and /trust/ (x402 vendor
observations), plus /llms.txt. SEO bits (keywords, JSON-LD, the /agents/ FAQ) live in seo.py. Called by build_pages.py inside its language loop with the same helper namespace `h` that
trade_pages.py gets (h.E, h._, h.L, h.SITE, h.ctime, h.langs, h.i18n, h.head_i18n, h.i18n_scripts, ...).

/trust/ is rendered to static HTML at build time from https://api.lumitrades.io/v1/trust/vendors (fetched once per
build, cached in state/trust_vendors.json, which is git-ignored; if the API is down the cache is used). assets/trust.js
then refreshes the table live from the same free endpoint. Every routine that runs scripts/publish.sh with data/ files
(dashboard update, trade tracker) rebuilds the pages, so the static table stays fresh without a separate job.
"""
import json
import re
import urllib.parse
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

# (product, method + path, price in USD); keys are translated, paths and prices are not.
# Every price here was checked against the live API (https://api.lumitrades.io/ paid_endpoints + plans, v1.1.2, Oct 22 2026).
TRUST_PRICES = [
    ("x402 pay check: allow / warn / block with reasons, signed receipts", "GET /v1/trust/check?url=", "$0.004"),
    ("Full report on one curated vendor (observation history, tx hashes, signed receipts)", "GET /v1/trust/vendors/{id}/report", "$0.02"),
    ("Vendor trust list and seller lookup", "GET /v1/trust/vendors", "free"),
    ("Verify a signed test-buy receipt", "POST /v1/trust/receipts/verify", "free"),
]
MARKET_PRICES = [
    ("Signal per coin (buy/sell read, RSI/MACD/EMA)", "GET /v1/signal/{coin}", "$0.01"),
    ("Support / resistance and 7-day scenario levels (not forecasts)", "GET /v1/levels/{coin}", "$0.01"),
    ("All-coins scan (50 signals in one call)", "GET /v1/scan", "$0.02"),
    ("Lite signal per coin (label, score, price)", "GET /v1/lite/{coin}", "$0.004"),
    ("Market slate (today's paper-trade ideas)", "GET /v1/slate", "$0.02"),
    ("BTC + macro market backdrop", "GET /v1/market", "$0.02"),
    ("Daily crypto market brief", "GET /v1/brief", "$0.02"),
    ("Yen carry-trade watch (USD/JPY, Nikkei)", "GET /v1/macro/yen", "$0.01"),
    ("Crypto sentiment (CoinMarketCap Fear & Greed, funding)", "GET /v1/sentiment", "$0.005"),
    ("Macro and crypto events calendar", "GET /v1/events", "$0.005"),
    ("Perpetual funding rates (50 coins)", "GET /v1/funding", "$0.003"),
    ("CoinMarketCap Fear & Greed with history", "GET /v1/fear-greed", "$0.003"),
    ("Events in the next 48 hours", "GET /v1/events/next48h", "$0.003"),
    ("Paper-trade history", "GET /v1/trades", "$0.02"),
    ("Daily Institutional & Policy Brief", "GET /v1/institutional", "$0.10"),
]
PRICES = TRUST_PRICES + MARKET_PRICES
# Lumi Market Ideas (signals, levels, scan, slate, trade history): the same routes and prices, shown as their own group,
# apart from the Lumi Trust products above and the neutral market data below.
MARKET_IDEAS_PATHS = ("/v1/signal/", "/v1/lite/", "/v1/scan", "/v1/slate", "/v1/trades", "/v1/levels/")
MARKET_IDEAS_PRICES = [x for x in MARKET_PRICES if x[1].split(" ", 1)[1].startswith(MARKET_IDEAS_PATHS)]
MARKET_DATA_PRICES = [x for x in MARKET_PRICES if x not in MARKET_IDEAS_PRICES]
MARKET_IDEAS_TEXT = ("Signals, support and resistance levels, the all-coins scan, the paper-trade slate and the trade history are "
                     "Lumi Market Ideas: an AI's paper-trade analysis, sold per call like the market data and kept apart from Lumi's trust checks.")
AGENTS_ROUTES_TEXT = ("Live signals for the top 50 coins, support and resistance levels, the paper-trade slate, and market and policy briefs: "
                      "{m} paid market routes (table below) plus {t} paid trust routes, from {lo} to {hi} per call. Free trial: new Base and XRPL wallets get 3 free calls "
                      "on every paid route, including the policy brief (send <code>X-Lumi-Trial: 1</code> and sign in with a Base wallet holding at least 0.01 USDC "
                      "or an activated XRP Ledger account; one trial per wallet, nothing is moved).")


def route_counts():
    """Paid route counts and price range, computed from the tables above (the /agents/ text and the homepage use these)."""
    paid = [x[2] for x in PRICES if x[2] != "free"]
    num = lambda s: float(s.lstrip("$"))
    return {"m": len(MARKET_PRICES), "t": sum(1 for x in TRUST_PRICES if x[2] != "free"),
            "lo": min(paid, key=num), "hi": max(paid, key=num)}


# (plan, price, what you get). Live: GET /v1/monitor and GET /v1/feed. 30-day plans, no auto-renew.
MONITOR_PLANS = [
    ("Monitor", ("{p} per 30 days", "$9"), "1 endpoint: one test-buy per term (plus one recheck after a failure) and alerts"),
    ("Monitor Plus", ("{p} per 30 days", "$29"), "Up to 20 endpoints: weekly test-buys and alerts"),
    ("Audit", ("{p} one-time", "$99"), "One test-buy of every listed endpoint, with a full report signed by Lumi's wallet"),
]
FEED_PLANS = [
    ("Free", ("{p}", "$0"), "1,000 lookups a month per key (wallet-signature signup), returns the verdict only"),
    ("Feed credits", ("{p} per 1,000 lookups", "$1.50"), "Prepaid lookups on top of the free 1,000 a month; credits never expire"),
    ("Feed", ("{p} per 30 days", "$99"), "100,000 bulk lookups, delta feed, full evidence and receipts"),
    ("Feed Pro", ("{p} per 30 days", "$199"), "500,000 lookups, delta feed, licensed full snapshot export, status-change webhooks, receipts"),
]
PLANS = MONITOR_PLANS + FEED_PLANS

CURL = """# 1. ask: no key, no account. The API answers 402 with a quote
curl -i https://api.lumitrades.io/v1/signal/XRP
#    HTTP/2 402
#    PAYMENT-REQUIRED: <base64 JSON: price, networks (Base USDC, XRPL XRP/RLUSD/USDC, Stellar USDC), payTo>

# 2. pay with any x402 client, then repeat the call with the signed payment
curl https://api.lumitrades.io/v1/signal/XRP -H "PAYMENT-SIGNATURE: <payment payload>"
#    HTTP/2 200 + the data, PAYMENT-RESPONSE: <settlement receipt>"""

MCP = """{ "mcpServers": {
  "lumi": { "url": "https://api.lumitrades.io/mcp" }
} }"""


SWEEP_ALL = ("As of {date}, Lumi had checked all {checked} third-party hosts that list an XRPL payment option in Coinbase's x402 Bazaar, "
             "made a real XRPL mainnet purchase from {bought}, and {delivered} returned data. Every payment is an XRPL mainnet transaction.")
SWEEP_PART = ("As of {date}, Lumi had checked {checked} of the {total} third-party hosts that list an XRPL payment option in Coinbase's x402 "
              "Bazaar, made a real XRPL mainnet purchase from {bought}, and {delivered} returned data. Every payment is an XRPL mainnet transaction.")


def sweep(doc):
    """The dated XRPL Bazaar sweep exactly as the live API reports it (catalog.purchase_verified_by_chain.xrpl.bazaar_sweep), or None."""
    try:
        sw = doc["catalog"]["purchase_verified_by_chain"]["xrpl"]["bazaar_sweep"]
        n = {k: int(sw[k]) for k in ("hosts_checked", "hosts_total", "hosts_bought", "delivered")}
        day = __import__("datetime").date.fromisoformat(str(sw["as_of"])[:10])
    except Exception:
        return None
    if not (0 < n["hosts_checked"] <= n["hosts_total"] and n["delivered"] <= n["hosts_bought"] <= n["hosts_checked"]):
        return None
    return {**n, "as_of": day}


def sweep_html(h, doc):
    """Translated, dated sweep sentence (plain text, HTML-escaped) or "" when the API has no sweep figures."""
    sw = sweep(doc)
    if not sw:
        return ""
    import datetime as _dt
    d = h.L.date(_dt.datetime(sw["as_of"].year, sw["as_of"].month, sw["as_of"].day), with_time=False)
    tpl = SWEEP_ALL if sw["hosts_checked"] == sw["hosts_total"] else SWEEP_PART
    return h.E(h._(tpl, date=d, checked=sw["hosts_checked"], total=sw["hosts_total"], bought=sw["hosts_bought"], delivered=sw["delivered"]))



# ---------- hero pieces (trust page + homepage): stat chips from the live API, 3-step visual, chain marks ----------
def trust_stats(doc):
    """Real figures from /v1/trust/vendors (catalog counts + per-chain test-buys), or None. Nothing is estimated:
    a figure the API doesn't report is left out."""
    try:
        cat = (doc or {}).get("catalog") or {}
        c = cat.get("counts") or {}
        bc = cat.get("purchase_verified_by_chain") or {}
        base = int((bc.get("base_usdc") or {}).get("test_buys") or 0)
        x = bc.get("xrpl") or {}
        xrpl = int(x.get("test_buys") or 0) + int((x.get("bazaar_catalog") or {}).get("test_buys") or 0)
        xlm = int((bc.get("stellar_usdc") or {}).get("test_buys") or 0)
        out = {"indexed": int(c.get("catalogued") or 0), "domains": int(c.get("domains") or 0), "as_of": str(c.get("as_of") or "")[:10],
               "quote_verified": int(c.get("quote_verified") or 0), "base": base, "xrpl": xrpl, "stellar": xlm,
               "buys": base + xrpl + xlm, "chains": sum(1 for n in (base, xrpl, xlm) if n)}
        return out if out["indexed"] or out["buys"] else None
    except (TypeError, ValueError):
        return None


def _n(v):
    return f"{v:,}"


def stats_html(h, doc, home=False):
    """<ul> of stat chips; empty string when the API gave nothing (the page still reads fine without it)."""
    st = trust_stats(doc)
    if not st:
        return ""
    _t, E = h._, h.E
    chips = []
    if st["buys"]:
        tip = _t("Base USDC {b} · XRPL {x} (curated list: last 30 days) · Stellar USDC {s}", b=_n(st["base"]), x=_n(st["xrpl"]), s=_n(st["stellar"]))
        chips.append((_n(st["buys"]), _t("paid test-buys on record"), tip))
    if st["indexed"]:
        lab = _t("x402 listings indexed")
        try:  # dated, because the count changes with every catalog ingest (the blog article quotes an earlier day's figure)
            import datetime as _dt
            day = _dt.date.fromisoformat(st["as_of"])
            lab = _t("x402 listings indexed as of {date}", date=h.L.date(_dt.datetime(day.year, day.month, day.day), with_time=False))
        except ValueError:
            pass
        chips.append((_n(st["indexed"]), lab, _t("across {d} seller domains", d=_n(st["domains"])) if st["domains"] else ""))
    if st["quote_verified"] and not home:
        chips.append((_n(st["quote_verified"]), _t("returned a valid quote (48 h)"), _t("free, unpaid quote checks")))
    if st["chains"]:
        chips.append((str(st["chains"]), _t("chains with paid test-buys"), "XRPL · Base · Stellar"))
    li = "".join(f'<li{f" title=\"{E(t)}\"" if t else ""}><b class="mono">{E(v)}</b><span>{E(l)}</span></li>' for v, l, t in chips)
    return f'<ul class="hx-stats" aria-label="{E(_t("Live figures from the Lumi API"))}">{li}</ul>'


CHAIN_MARKS = (("xrpl", "XRPL", "M6 6l12 12M18 6 6 18"), ("base", "Base", "M4 12h16"), ("stellar", "Stellar", "M12 3l2.6 6 6.4.6-4.9 4.3 1.5 6.3L12 17l-5.6 3.2 1.5-6.3L3 9.6 9.4 9z"))


def chains_html(h, label=True):
    """Text badges with a neutral glyph per chain (no third-party logos)."""
    b = "".join(f'<span class="hx-chain {k}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="{d}"/></svg>{n}</span>' for k, n, d in CHAIN_MARKS)
    lab = f'<span class="hx-chains-l">{h.E(h._("Test-buys on"))}</span>' if label else ""
    return f'<div class="hx-chains">{lab}{b}</div>'


STEP_ICONS = ("M10 2a8 8 0 1 0 4.9 14.3l5.4 5.4 1.4-1.4-5.4-5.4A8 8 0 0 0 10 2zm0 2a6 6 0 1 1 0 12 6 6 0 0 1 0-12zm-1 3v2H7v2h2v2h2v-2h2V9h-2V7z",
              "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15.9V19h-2v-1.1a4 4 0 0 1-3-3.4h2a2 2 0 0 0 2 1.5c1.2 0 2-.6 2-1.4 0-.9-.8-1.2-2.3-1.6-2-.5-3.5-1.2-3.5-3.1A3.2 3.2 0 0 1 11 6.1V5h2v1.1a3.4 3.4 0 0 1 2.7 3h-2a1.6 1.6 0 0 0-1.7-1.2c-1 0-1.7.5-1.7 1.2 0 .8.9 1.1 2.3 1.5 1.9.5 3.5 1.2 3.5 3.2a3.3 3.3 0 0 1-3.1 3.1z",
              "M5 2h14v20l-2.3-1.6L14.3 22 12 20.4 9.7 22l-2.4-1.6L5 22zm3 5v2h8V7zm0 4v2h8v-2zm0 4v2h5v-2z")


def steps_html(h):
    _t, E = h._, h.E
    steps = ((_t("Lumi checks the quote"), _t("A free request asks each endpoint for its x402 price quote and checks it is readable and payable.")),
             (_t("Lumi makes a small paid test-buy"), _t("Lumi pays a few cents from its own wallet and records whether real data came back.")),
             (_t("The payment is on a public ledger"), _t("Every paid test-buy is a real transaction on XRPL, Base or Stellar, kept with a signed receipt. The tx hash of each seller's latest buy is free on the trust list; the signed receipts come with the paid vendor report.")))
    li = "".join(f'<li><span class="hx-step-i"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="{STEP_ICONS[i]}"/></svg><em>{i + 1}</em></span>'
                 f'<b>{E(t)}</b><span>{E(d)}</span></li>' for i, (t, d) in enumerate(steps))
    return f'<ol class="hx-steps">{li}</ol>'


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


# Vendor homepages that don't load for visitors (404 / payment wall, launch QA 2026-10-24): link the name to Lumi's public
# vendor report instead. Display only; the vendor's data and score are unchanged. Mirrored in assets/trust.js (NO_HOME).
NO_HOME = {"x402.cryptobuddy.com.au", "oracle.evebrief.org"}
REPORT_URL = API + "/trust/v/{id}"


def vendor_link(v):
    home = _https(v.get("homepage"))
    host = re.sub(r"^https://([^/:]+).*$", r"\1", home or "").lower()
    if host in NO_HOME and v.get("id"):
        return REPORT_URL.format(id=urllib.parse.quote(str(v["id"]), safe=""))
    return home


# ---------- "Tested by Lumi" badge on /trust/ (same look as the API badge /badge/{key}.svg and the brand video) ----------
# Built only from the vendor's latest stored paid test-buy (last_paid_observation): result, UTC date (MM-DD-YYYY, the
# same date the API badge prints) and chain. No paid test-buy on record = no badge. Display only: it never changes a
# score. Mirrored in assets/trust.js (badge()).
def badge_chain(network):
    n = str(network or "").lower()
    if n.startswith("xrpl"):
        return "XRPL"
    if n.startswith("stellar"):
        return "Stellar"
    if n in ("base", "base-mainnet", "eip155:8453"):
        return "Base"
    return ""


def badge_result(o):
    """'delivered' | 'no_delivery' | 'inconclusive' for a real paid test-buy, else None (never tested: no badge)."""
    if not o or not o.get("observed_at"):
        return None
    dv = o.get("delivery")
    if dv == "delivered":
        return "delivered"
    if dv in ("not_delivered", "failed") or o.get("data_returned") is False:
        return "no_delivery"
    return "inconclusive"


def badge_date(iso):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{m.group(2)}-{m.group(3)}-{m.group(1)}" if m else ""


BADGE_NOTE = "Look for the Tested by Lumi badge: it means Lumi bought from this seller and checked the delivery."
BADGE_KEY = ("Green: the latest paid test-buy got data back. Red: it did not. The date (UTC) and chain are those of "
             "that test-buy. Sellers Lumi has not bought from yet have no badge.")
BADGE_RES = {"delivered": "delivered", "no_delivery": "no delivery", "inconclusive": "inconclusive"}
BADGE_TIP = {"delivered": "Latest paid test-buy by Lumi: data delivered.",
             "no_delivery": "Latest paid test-buy by Lumi: no data delivered.",
             "inconclusive": "Latest paid test-buy by Lumi: result inconclusive."}
BADGE_TIP_END = "Date in UTC. A dated test result, not an endorsement or guarantee."


def badge_html(h, v):
    """The two-pill badge for one vendor, or "" when Lumi has no real completed paid test-buy for it."""
    E, _t = h.E, h._
    o = v.get("last_paid_observation") or None
    res = badge_result(o)
    day = badge_date(o.get("observed_at")) if res else ""
    if not res or not day:
        return ""
    chain = badge_chain(o.get("network"))
    right = " · ".join([_t(BADGE_RES[res]), day] + ([chain] if chain else []))
    label = _t("Tested by Lumi")
    tip = _t(BADGE_TIP[res]) + " " + _t(BADGE_TIP_END)
    return (f'<span class="lt-badge b-{res}" role="img" aria-label="{E(label)}: {E(right)}" title="{E(tip)}">'
            f'<span class="lt-b-l" aria-hidden="true">{E(label)}</span><span class="lt-b-r" aria-hidden="true">{E(right)}</span></span>')


# ---------- Free on-chain proof: the tx hash of each seller's latest paid test-buy (the same buy the badge shows) ----------
# Source, in order: last_paid_observation.tx_hash from the live API (if it ever carries one), else scripts/trust_tx.json, a
# read-only copy of hashes from Lumi's own trust database. A copied hash is used only when vendor id, observed_at, endpoint
# and network all equal the API's latest paid test-buy, so a newer buy never shows an older hash. No match = no tx link.
# Hashes are never derived or made up. Mirrored in assets/trust.js (txFor()). Signed receipts stay in the paid report.
TX_SNAPSHOT = os.path.join(ROOT, "scripts", "trust_tx.json")
TX_EXPLORER = {"XRPL": "https://livenet.xrpl.org/transactions/{h}", "Base": "https://basescan.org/tx/{h}",
               "Stellar": "https://stellar.expert/explorer/public/tx/{h}"}
TX_RE = {"XRPL": re.compile(r"^[0-9A-F]{64}$"), "Base": re.compile(r"^0x[0-9a-f]{64}$"), "Stellar": re.compile(r"^[0-9a-f]{64}$")}
TX_LABEL = "On-chain tx"
TX_TIP = "Lumi's payment for this test-buy on the public {chain} ledger. Free to check."
_tx_snap = None


def tx_snapshot():
    """{vendor_id: {observed_at, endpoint, network, tx_hash}} from scripts/trust_tx.json ({} if missing or invalid)."""
    global _tx_snap
    if _tx_snap is None:
        try:
            with open(TX_SNAPSHOT, encoding="utf-8") as f:
                d = json.load(f).get("vendors") or {}
            _tx_snap = {k: x for k, x in d.items() if isinstance(x, dict)}
        except Exception:
            _tx_snap = {}
    return _tx_snap


def obs_tx(v, snap=None):
    """(tx_hash, explorer_url) of the vendor's latest paid test-buy, or None when we have no matching hash."""
    o = v.get("last_paid_observation") or None
    if not o or not o.get("observed_at"):
        return None
    chain = badge_chain(o.get("network"))
    if not chain:
        return None
    h = o.get("tx_hash")
    if not h:
        x = (tx_snapshot() if snap is None else snap).get(str(v.get("id") or "")) or {}
        if all(x.get(k) == o.get(k) for k in ("observed_at", "endpoint", "network")):
            h = x.get("tx_hash")
    h = str(h or "").strip()
    if chain == "XRPL":
        h = h.upper()
    elif chain == "Base":
        h = h.lower()
    if not TX_RE[chain].match(h):
        return None
    return h, TX_EXPLORER[chain].format(h=h)


def tx_short(h):
    return h[:8] + "…" + h[-6:] if h.startswith("0x") else h[:6] + "…" + h[-6:]


def tx_html(h, v):
    """Compact free tx link under the badge: 'On-chain tx 51E571…D1F4C2 ↗' with the full hash in the link."""
    t = obs_tx(v)
    if not t:
        return ""
    E, _t = h.E, h._
    tip = _t(TX_TIP, chain=badge_chain(v["last_paid_observation"].get("network")))
    return (f'<span class="tr-tx">{E(_t(TX_LABEL))} <a href="{E(t[1])}" target="_blank" rel="noopener" title="{E(tip)}" '
            f'data-tx="{E(t[0])}"><code>{E(tx_short(t[0]))}</code> ↗</a></span>')


def vendor_row(h, v):
    E, _t = h.E, h._
    s = v.get("samples") or {}
    o = v.get("last_paid_observation") or None
    home = vendor_link(v)
    nm = E(v.get("name") or v.get("id"))
    if home and home.startswith(API + "/trust/v/"):  # no working vendor homepage: say plainly that the link is Lumi's own result page
        name = f'{nm} <a class="tr-own" href="{E(home)}" target="_blank" rel="noopener">{E(_t("Lumi test result"))} ↗</a>'
    else:
        name = f'<a href="{E(home)}" target="_blank" rel="noopener nofollow">{nm}</a>' if home else nm
    conf = str(v.get("confidence") or "—")
    ev = "—"
    if o and o.get("observed_at"):  # outcome + date of the latest paid test-buy (free data); signed receipts are in the paid report
        dv = o.get("delivery")
        ev = (f'<span title="{E(_t("Signed receipt and full history: paid vendor report ($0.02)"))}">'
              f'{E(_t("Delivered") if dv == "delivered" else _t("No data") if dv in ("not_delivered", "failed") or o.get("data_returned") is False else _t("Inconclusive"))}'
              f' · {E(h.ctime(o["observed_at"]))}</span>')
    if o and _https(o.get("explorer")):
        ev = (f'<a href="{E(o["explorer"])}" target="_blank" rel="noopener" title="{E(o.get("summary") or "")}">'
              f'{E(((o.get("amount") or "") + " " + (o.get("asset") or "")).strip())} · {E(_t("data") if o.get("data_returned") else _t("no data"))} ↗</a>')
    if v.get("replies") and _https(v.get("detail")):
        ev += f' <a href="{E(v["detail"])}" target="_blank" rel="noopener">· {E(_t("reply ({n})", n=v["replies"]))}</a>'
    lc = _last_checked(v)
    return (f'<tr><td>{name}{badge_html(h, v)}{tx_html(h, v)}<span class="vid">{E(v.get("id"))}</span></td>'
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
               "on Base or Stellar, or XRP and RLUSD on the XRPL. MCP server, no API key.")
TRUST_DESC = ("x402 vendor reputation: free trust scores for pay-per-call endpoints from Lumi's automated 402-quote checks and small "
              "paid on-ledger test-buys on XRPL, Base and Stellar. Observations, not a rating or review of any business.")


BADGE_EXAMPLE = "printmoneylab"  # a real curated vendor with delivered test-buys (checked live Oct 23 2026)


def badge_section(h):
    """/agents/#badge: the free "Tested by Lumi" badge (api.lumitrades.io/badge/{key}.svg) with an example and a
    client-side "find your key" helper (assets/badge.js builds the URLs; no listing or search of the catalog)."""
    E, _t = h.E, h._
    k = BADGE_EXAMPLE
    img, page = f"{API}/badge/{k}.svg", f"{API}/trust/v/{k}"
    alt = "Tested by Lumi: latest dated x402 test-buy result"
    md = f"[![{alt}]({API}/badge/{{key}}.svg)]({API}/trust/v/{{key}})"
    html_s = f'<a href="{API}/trust/v/{{key}}"><img src="{API}/badge/{{key}}.svg" alt="{alt}" height="20"></a>'
    lk = lambda href, txt: f'<a href="{href}" target="_blank" rel="noopener">{E(txt)}</a>'
    return f"""<section class="card cp-sec" id="badge"><h2>{E(_t("Get your badge"))}</h2>
<p>{_t("Sell an x402 endpoint that Lumi has tested? Show it. The free “Tested by Lumi” badge shows the verdict and date of Lumi's latest stored paid test-buy of your service, plus the chain (XRPL, Base or Stellar), and links to a public result page with the dated tests and your right to reply. No sign-up, and paying Lumi never changes the result.")}</p>
<p class="ag-badge-ex">{E(_t("Example (a real vendor):"))} <a href="{page}" target="_blank" rel="noopener"><img src="{img}" alt="{E(alt)}" height="20" loading="lazy" style="vertical-align:middle"></a></p>
<p class="meta">{_t("<b>delivered</b> (green): the paid response contained data · <b>not delivered</b> (red): the seller answered without usable data · <b>inconclusive</b> (gray): Lumi never saw a response, a Lumi-side outcome not counted against you · <b>not yet tested</b>: Lumi has no stored result.")}</p>
<h3>{E(_t("Find your key"))}</h3>
<p>{_t("Your key is your Lumi vendor id (shown on the vendor trust list) or the exact host of the x402 URL Lumi bought, for example <code>api.example.com</code>. Paste your endpoint URL, host or vendor id:")}</p>
<form id="bd-form" class="ag-badge-form" autocomplete="off"><input id="bd-key" type="text" inputmode="url" maxlength="300" placeholder="{E(_t("https://api.example.com/v1/data or a vendor id"))}" aria-label="{E(_t("Endpoint URL, host or vendor id"))}" style="min-width:min(100%,340px);padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:rgba(5,8,14,.6);color:inherit"> <button type="submit" class="btn">{E(_t("Make my badge"))}</button></form>
<p id="bd-out" class="ag-badge-ex" hidden></p>
<p class="muted" id="bd-err" hidden></p>
<p class="meta">{E(_t("Markdown (README.md)"))}</p><pre class="ag-code"><code id="bd-md">{E(md)}</code></pre>
<p class="meta">{E(_t("HTML"))}</p><pre class="ag-code"><code id="bd-html">{E(html_s)}</code></pre>
<p class="meta">{_t("Factual test evidence, not an endorsement or guarantee. Updated within the hour of each new test. Questions or a dispute: <a href=\"mailto:hello@lumitrades.io\">hello@lumitrades.io</a>.")} {lk(API + "/badge", _t("Badge docs"))} · <a href="../how-it-works/#testing">{E(_t("How Lumi tests"))}</a></p></section>"""


def agents_page(h, tp, nav_items, V, gen_date, vendors_doc=None):
    E, _t = h.E, h._
    row = lambda p, ep, pr: f'<tr><td>{E(_t(p))}</td><td class="mono">{E(ep)}</td><td class="num mono">{E(_t(pr) if pr == "free" else pr)}</td></tr>'
    thead = f'<thead><tr><th>{E(_t("Product"))}</th><th>{E(_t("Endpoint"))}</th><th class="num">{E(_t("Price"))}</th></tr></thead>'
    table = lambda items: f'<div class="cp-tablewrap"><table class="cp-table cp-stack cp-stack-r">{thead}<tbody>{"".join(row(*x) for x in items)}</tbody></table></div>'
    pthead = f'<thead><tr><th>{E(_t("Plan"))}</th><th>{E(_t("Price"))}</th><th>{E(_t("What you get"))}</th></tr></thead>'
    ptable = lambda items: ('<div class="cp-tablewrap"><table class="cp-table cp-stack">' + pthead + "<tbody>" + "".join(
        f'<tr><td>{E(_t(n))}</td><td class="mono">{E(_t(fmt, p=p) if fmt != "{p}" else p)}</td><td>{E(_t(d))}</td></tr>' for n, (fmt, p), d in items) + "</tbody></table></div>")
    title = _t("x402 trust checks and data for AI agents | Lumi Trades")
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
<h1>{E(_t("Lumi for AI agents: x402 trust checks and crypto data"))}</h1>
<p class="cp-lede">{_t("Lumi tests x402 sellers independently: real on-ledger test-buys, a signed receipt for each one, and coverage on the XRP Ledger, Base and Stellar. Agents can check a seller before they pay it, sellers can have their own endpoints monitored, and platforms can license the data. Lumi also sells crypto market data one call at a time. No account and no API key: the API answers <code>402 Payment Required</code> with a quote, the agent pays, and gets the answer.")}</p>
<section class="card cp-sec" id="trust"><h2>{E(_t("Check a seller before you pay"))}</h2>
<p>{_t("Call <code>GET /v1/trust/check?url=</code> with the x402 URL your agent is about to pay (optionally with the payTo and price you were quoted). It answers allow, warn or block with coded reasons, built from Lumi's index of Coinbase's x402 Bazaar, free 402-quote checks and Lumi's own test-buys. Where Lumi has bought from that seller, the paid answer carries Lumi's signed test-buy receipts, which anyone can verify for free. The vendor trust list is free. Paying Lumi, for a check or for monitoring, never changes a score.")}</p>
{f"<p>{sweep_html(h, vendors_doc)}</p>" if sweep_html(h, vendors_doc) else ""}
{table(TRUST_PRICES)}
<p class="meta">{_t("Dated observations, not a rating, endorsement or guarantee of any business.")} {lk(API + "/v1/trust/methodology", _t("Methodology"))} · <a href="../trust/">{E(_t("Vendor trust list (free)"))}</a></p></section>
<section class="card cp-sec" id="sellers"><h2>{E(_t("For sellers: monitoring and audits"))}</h2>
<p>{_t("Prove you control your payTo wallet by signing a challenge (XRPL or Base; Lumi never asks for keys or seeds), enrol your endpoints for free, then pay a plan with x402. Lumi test-buys your endpoints with real payments and alerts you by webhook or email when something breaks: no data, errors, timeouts, or a changed payTo, price or response schema.")}</p>
{ptable(MONITOR_PLANS)}
<p class="meta">{_t("Each test-buy is capped at $0.10 and funded from the plan fee. A paid plan is disclosed on the seller's public entry, and findings stay public with the seller's reply next to them. The “Tested by Lumi” badge is earned only from delivery results and is removed automatically when the seller's live score drops. No auto-renew. No refunds unless Lumi can't perform the monitoring it sold; then the unperformed part is refunded.")} {lk(API + "/v1/monitor", _t("How to start"))}</p></section>
{badge_section(h)}
<section class="card cp-sec" id="feed"><h2>{E(_t("Trust data feed and license"))}</h2>
<p>{_t("Keyed, licensed access to Lumi's trust observations for facilitators, wallets and agent frameworks: bulk lookups of up to 50 URLs or payTo addresses per request, a status-change feed and, on Feed Pro, a full snapshot export.")}</p>
{ptable(FEED_PLANS)}
<p class="meta">{_t("License: no resale or redistribution of the raw data, attribution required, no warranty. Prepaid credits never expire. 30-day plans, no auto-renew.")} {lk(API + "/v1/feed/license", _t("License terms"))} · {lk(API + "/v1/feed", _t("Feed docs"))}</p></section>
<section class="card cp-sec" id="prices"><h2>{E(_t("Market data"))}</h2>
<p>{_t(AGENTS_ROUTES_TEXT, **route_counts())}</p>
{table(MARKET_DATA_PRICES)}
<div class="ag-mi" id="market-ideas">
<h3>Lumi Market Ideas</h3>
{h.MI_LABEL()}
<p>{E(_t(MARKET_IDEAS_TEXT))}</p>
{table(MARKET_IDEAS_PRICES)}
</div>
<p class="meta">{_t("Prices per call in USD. If the data isn't fresh the API answers 503 and you are not charged. Free: <code>/v1/coins</code>, <code>/openapi.json</code>, <code>/skill.md</code>, <code>/.well-known/x402</code>.")}</p></section>
<section class="card cp-sec" id="pay"><h2>{E(_t("How to pay"))}</h2>
<ul class="ag-list"><li>{_t("<b>USDC on Base</b> (eip155:8453), settled through Coinbase's x402 facilitator. Works with Coinbase AgentKit and any x402 client.")}</li>
<li>{_t("<b>XRP Ledger</b>: XRP, RLUSD or USDC, verified on-ledger.")}</li>
<li>{_t("<b>USDC on Stellar</b> (stellar:pubnet), settled through the OpenZeppelin x402 facilitator with network fees sponsored. Same USD prices as Base.")}</li></ul>
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
<li><a href="../trust/">{E(_t("Vendor trust list (free)"))}</a> · {lk(API + "/v1/monitor", _t("Seller monitoring"))} · {lk(API + "/v1/feed", _t("Trust data feed"))}</li>
<li>{lk(BAZAAR, _t("Coinbase x402 Bazaar"))} · {lk(X402SCAN, "x402scan")}</li>
<li>{lk(MCP_REG, _t("Official MCP Registry"))} · {lk(NPM, "npm: lumi-trades-mcp")} · {lk(API + "/.well-known/agent-card.json", _t("A2A agent card"))}</li></ul></section>
{seo.faq_html(_t, E)}
<div class="disclaimer" role="note"><span class="warn-ico" aria-hidden="true">!</span><span>{_t("<strong>Data, not financial advice.</strong> Signals and trade ideas are an AI's paper-trade analysis; no real money is traded.")}</span></div>
</main>
"""
    js = '<script src="{R}assets/badge.js?v={V}" defer></script>\n'
    return _page(h, tp, "agents/", title, desc, ld, body, V, gen_date, nav_items, "agents", extra_js=js, keywords=seo.keywords(_t, "agents", h.L.en))


def policy_note(h):
    """/trust/#reply: link to the conflicts policy, only in languages that have it (policy_page.LIVE_LANGS)."""
    import policy_page
    if h.L.code not in policy_page.LIVE_LANGS:
        return ""
    return (f'<p class="meta">{h.E(h._(policy_page.TRUST_NOTE))} '
            f'<a href="../{policy_page.SLUG}">{h.E(h._(policy_page.H1))}</a></p>\n')


VERIFY_H = "Verify it yourself"
VERIFY_INTRO = ("You don't have to take our word for it. Each tx link above opens Lumi's payment on a public block explorer, "
                "and checking it is free.")
VERIFY_STEPS = [
    ("Pick a seller", "Choose any seller in the list above that has an On-chain tx link."),
    ("Open its tx hash", "Click the hash. The block explorer shows Lumi's payment for that seller's latest test-buy on the "
                         "public XRPL, Base or Stellar ledger."),
    ("Compare the details", "Check that the amount, time and recipient match the seller's listed x402 price, the test-buy "
                            "time shown here and the seller's pay-to address. The price and the pay-to address are in the "
                            "seller's free entry at api.lumitrades.io/v1/trust/vendors/<seller id> (the id is the grey text "
                            "under each name)."),
    ("Optional: check the signed receipt", "Each test-buy also has a receipt signed by the wallet that paid. Receipts come "
                                           "with the paid vendor report ($0.02). To verify one for free, send it to POST "
                                           "https://api.lumitrades.io/v1/trust/receipts/verify (add ?ledger=1 to check the "
                                           "payment on-chain too), or follow the steps listed at that address."),
]
VERIFY_FREE = "The tx proof is free. The full report on a vendor, with its whole history and the signed receipts, costs $0.02."
VERIFY_NONE = "Sellers without a recorded hash for their latest test-buy show no tx link."
VERIFY_SCORE = "Paying Lumi never changes a score: scores come only from Lumi's own checks."
ABOUT_H = "About Lumi Trades"
ABOUT_P = ("Lumi Trades is an independent trust list for x402, bridging trust between Base, XRPL and Stellar. Lumi makes "
           "small paid test-buys from x402 sellers on all three chains and publishes what came back; it does not move "
           "funds between chains. It launched in October 2026.")
ABOUT_SAFE = "Lumi never asks for deposits, never holds user funds and never offers investment returns."
ABOUT_OTHER = "Sites and accounts not listed here are not Lumi's."
X_URL = "https://x.com/Lumisinsite"
YT_URL = "https://www.youtube.com/@lumitradesio"


def verify_section(h):
    E, _t = h.E, h._
    li = "".join(f'<li><b>{E(_t(t))}</b> <span>{E(_t(d))}</span></li>' for t, d in VERIFY_STEPS)
    return (f'<section class="card cp-sec tr-verify" id="verify">\n<h2>{E(_t(VERIFY_H))}</h2>\n<p>{E(_t(VERIFY_INTRO))}</p>\n'
            f'<ol>{li}</ol>\n<p class="tr-free"><b>{E(_t(VERIFY_FREE))}</b> {E(_t(VERIFY_NONE))}</p>\n'
            f'<p class="tr-score">{E(_t(VERIFY_SCORE))}</p>\n'
            f'<p class="meta"><a href="{API}/v1/trust/receipts/verify" target="_blank" rel="noopener">{E(_t("Receipt check (free)"))}</a> · '
            f'<a href="{VENDORS_URL}" target="_blank" rel="noopener">{E(_t("Seller data (free JSON)"))}</a> · '
            f'<a href="{API}/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("Methodology"))}</a></p>\n</section>')


def about_section(h):
    E, _t = h.E, h._
    rows = [(_t("Official sites"), '<a href="https://lumitrades.io/">lumitrades.io</a> · <a href="https://api.lumitrades.io/" target="_blank" rel="noopener">api.lumitrades.io</a>'),
            (_t("Official X account (the only one)"), f'<a href="{X_URL}" target="_blank" rel="me noopener">@Lumisinsite</a>'),
            (_t("Contact"), '<a href="mailto:hello@lumitrades.io">hello@lumitrades.io</a>')]
    dl = "".join(f"<dt>{E(k)}</dt><dd>{v}</dd>" for k, v in rows)
    return (f'<section class="card cp-sec tr-about" id="about">\n<h2>{E(_t(ABOUT_H))}</h2>\n<p>{E(_t(ABOUT_P))}</p>\n'
            f'<dl>{dl}</dl>\n<p class="tr-safe"><b>{E(_t(ABOUT_SAFE))}</b> {E(_t(ABOUT_OTHER))}</p>\n</section>')


def trust_page(h, tp, nav_items, V, gen_date, doc):
    E, _t = h.E, h._
    vendors = (doc or {}).get("vendors") or []
    title = _t("x402 vendor trust list: Lumi's automated test-buys | Lumi Trades")
    desc = _t(TRUST_DESC)
    url = h.SITE + h.L.prefix + "trust/"
    org = seo.organization(_t, "trust")
    org.update({"foundingDate": "2026-10", "email": "hello@lumitrades.io",
                "sameAs": [X_URL, YT_URL] + [u for u in org.get("sameAs") or [] if u.lower() not in (X_URL.lower(), YT_URL.lower())]})
    howto = {"@context": "https://schema.org", "@type": "HowTo", "name": _t("How to verify a Lumi test-buy yourself"),
             "description": _t(VERIFY_INTRO), "inLanguage": h.L.code, "url": url + "#verify",
             "step": [{"@type": "HowToStep", "position": i + 1, "name": _t(t), "text": _t(d), "url": url + "#verify"}
                      for i, (t, d) in enumerate(VERIFY_STEPS)]}
    ld = [org, howto,
          {"@context": "https://schema.org", "@type": "WebPage", "name": _t("x402 vendor trust list"), "url": url,
           "description": desc, "inLanguage": h.L.code, "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID},
           "keywords": seo.keywords(_t, "trust", h.L.en)},
          seo.trust_dataset(_t, h.L.code, url, doc, VENDORS_URL),
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE + h.L.prefix},
              {"@type": "ListItem", "position": 2, "name": _t("Vendor trust"), "item": h.SITE + h.L.prefix + "trust/"}]}]
    rows = "".join(vendor_row(h, v) for v in vendors)
    snap = {str(v.get("id")): tx_snapshot()[str(v.get("id"))] for v in vendors if str(v.get("id")) in tx_snapshot()}
    snap_js = json.dumps(snap, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    R = "../" + ("" if h.L.en else "../")
    gen = (doc or {}).get("generated_at")
    status = "" if vendors else f'<p id="tr-status" class="muted">{E(_t("Loading observations…"))}</p>'
    body = f"""<main class="wrap cp-main">
<p class="cp-crumb"><a href="../">Lumi Trades</a> › {E(_t("Vendor trust"))}</p>
<section class="tx-hero" aria-labelledby="tx-h">
<div class="hx-top">
<div class="tx-copy">
<p class="hx-eyebrow">{E(_t("x402 vendor trust list"))} · <span>{E(_t("free"))}</span></p>
<h1 id="tx-h" class="hx-h1">{E(_t("Know which agent APIs actually deliver before you pay."))}</h1>
<p class="hx-sub">{E(_t("Lumi pays x402 sellers a few cents for real, records what came back, and keeps a signed receipt for every buy."))}</p>
<div class="hx-cta"><a class="hx-btn" href="#vendors">{E(_t("See the list"))}</a><a class="hx-btn ghost" href="../agents/">{E(_t("Full vendor report: $0.02"))}</a></div>
<p class="hx-price-note muted">{E(_t("$0.02 buys the full report on one vendor from this list (every check, every tx hash and the signed receipts). $0.004 is the pay check: allow, warn or block for any x402 URL before your agent pays it."))}</p>
</div>
<div class="tx-visual ag-panel ag-feed" id="ag-feed">
<div class="ag-head"><span class="ag-who"><img src="{R}assets/brand/logo.png?v={V}" alt="" width="30" height="30"><span><b>{E(_t("Latest delivered test-buys"))}</b><small>{E(_t("from the live trust API"))}</small></span></span><span class="ag-live"><i aria-hidden="true"></i>{E(_t("live"))}</span></div>
<ol class="ag-rows" id="ag-rows"><li class="sk"></li><li class="sk"></li><li class="sk"></li><li class="sk"></li></ol>
<div class="ag-foot"><span>{E(_t("Each buy is an on-ledger payment kept with a signed receipt."))}</span><a href="#vendors">{E(_t("Full list →"))}</a></div>
</div>
</div>
{stats_html(h, doc)}
{steps_html(h)}
{chains_html(h)}
</section>
<div class="disclaimer tx-note" role="note"><span class="warn-ico" aria-hidden="true">!</span><span>{_t("<strong>Automated observations, not a rating or review of any business.</strong> Scores summarize what Lumi's own checks saw over the last 30 days. Few samples = low confidence.")} <a href="{API}/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("Methodology"))}</a></span></div>
<details class="tx-more"><summary>{E(_t("How the checks work"))}</summary>
<p>{_t("Lumi checks pay-per-call (x402) endpoints that agents can buy from: a free check that each endpoint returns a valid payment quote, plus small paid test-buys. Each paid test-buy is a real payment on a public ledger (XRPL, Base or Stellar), stored with its tx hash and a signed receipt. The list and the tx hash of each seller's latest test-buy are free; the full report on one vendor, with its whole history, explorer links and signed receipts, costs $0.02. The $0.004 pay check is a different product: allow, warn or block for any x402 URL.")}</p>
<p>{E(_t("Quote checks are free and unpaid, so they show an endpoint is reachable and priced, not that it delivers. Paid test-buys are capped at a small shared daily budget, so not every vendor is bought every day; fewer samples means lower confidence."))}</p>
</details>
<section class="card cp-sec" id="vendors">
<h2>{E(_t("Vendors on the curated list"))} <span class="muted" id="tr-count">{f"({len(vendors)})" if vendors else ""}</span></h2>
<p class="tr-badge-note">{E(_t(BADGE_NOTE))} <span class="muted">{E(_t(BADGE_KEY))}</span></p>
{status}
<div class="tr-wrap"><table class="cp-table tr-table" id="tr-table"{"" if vendors else " hidden"}>
<thead><tr><th>{E(_t("Vendor"))}</th><th class="num">{E(_t("Score"))}</th><th>{E(_t("Confidence"))}</th><th class="num">{E(_t("Paid buys"))}</th><th class="num">{E(_t("Delivered"))}</th><th>{E(_t("Last checked"))}</th><th>{E(_t("Last test-buy"))}</th></tr></thead>
<tbody id="tr-body">{rows}</tbody></table></div>
<script type="application/json" id="tr-tx">{snap_js}</script>
<p class="meta">{E(_t("Listed in the order we added them, not ranked. \"Paid buys\" = paid test-buys in the window; \"Delivered\" = paid buys whose response contained data. \"Last checked\" = the most recent free quote check or paid test-buy. \"Last test-buy\" = outcome and time of the latest paid test-buy. \"On-chain tx\" = Lumi's payment for that same test-buy on the public ledger, free to check (see \"Verify it yourself\" below). Older tx hashes and the signed receipts come with the paid vendor report ($0.02 per vendor). Times in US Central."))} <span id="tr-gen">{E(_t("Data generated {when}.", when=h.ctime(gen))) if gen else ""}</span></p>
<p class="meta">{E(_t("Raw data:"))} <a href="{VENDORS_URL}" target="_blank" rel="noopener">api.lumitrades.io/v1/trust/vendors</a> · <a href="{API}/v1/trust/methodology" target="_blank" rel="noopener">{E(_t("How scores are computed"))}</a> · <a href="../agents/">{E(_t("Lumi's data for AI agents →"))}</a></p>
</section>
{verify_section(h)}
{about_section(h)}
<section class="card cp-sec" id="reply">
<h2>{E(_t("Right to reply"))}</h2>
<p>{_t("If you run one of these endpoints and think an observation is wrong or missing context, you can add a reply that is shown with your entry. Email <a href=\"mailto:hello@lumitrades.io\">hello@lumitrades.io</a>, or post a signed reply to <code>POST https://api.lumitrades.io/v1/trust/replies</code>, signed with the key of a pay-to address listed for your entry (details in the methodology). We can also re-run a check or remove an endpoint from the list on request.")}</p>
{policy_note(h)}</section>
</main>
"""
    js = '<script src="{R}assets/trust.js?v={V}" defer></script>\n<script src="{R}assets/hero.js?v={V}" defer></script>\n'
    return _page(h, tp, "trust/", title, desc, ld, body, V, gen_date, nav_items, "trust", js, seo.keywords(_t, "trust", h.L.en))


def build(h, tp, nav_items, V, gen_date, write, vendors_doc):
    """Writes [<lang>/]agents/index.html, [<lang>/]trust/index.html, how-it-works/, privacy/, trust-policy/ (live languages only) and (English pass) /llms.txt. Returns sitemap entries (language-relative)."""
    P = h.L.prefix
    write(f"{P}agents/index.html", agents_page(h, tp, nav_items, V, gen_date, vendors_doc))
    write(f"{P}trust/index.html", trust_page(h, tp, nav_items, V, gen_date, vendors_doc))
    import how_page
    write(f"{P}how-it-works/index.html", how_page.build_page(h, tp, nav_items, V, gen_date, _page))
    import privacy_page
    write(f"{P}privacy/index.html", privacy_page.build_page(h, tp, nav_items, V, gen_date, _page))
    import policy_page  # /trust-policy/: written for the languages in policy_page.LIVE_LANGS
    pol = policy_page.build_page(h, tp, nav_items, V, gen_date, _page)
    if pol:
        write(f"{P}{policy_page.SLUG}index.html", pol)
    if h.L.en:
        write("llms.txt", seo.llms_txt(PRICES, PLANS, groups=[("Lumi Trust", TRUST_PRICES), ("Market data", MARKET_DATA_PRICES),
                                                                     ("Lumi Market Ideas", MARKET_IDEAS_PRICES)]))
    lm = ((vendors_doc or {}).get("generated_at") or gen_date)[:10]
    return [("agents/", gen_date, "weekly", "0.8"), ("trust/", lm, "daily", "0.7"), ("how-it-works/", gen_date, "monthly", "0.7"),
            ("privacy/", privacy_page.UPDATED.isoformat(), "yearly", "0.3")] + (
            [(policy_page.SLUG, policy_page.UPDATED.isoformat(), "monthly", "0.4")] if h.L.code in policy_page.LIVE_LANGS else [])
