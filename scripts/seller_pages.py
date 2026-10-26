"""/sellers/<host-slug>/: one English page per seller on the curated x402 trust list ("<seller> test-buy results",
"<seller> x402 review" searches). Built by build_pages.py on the English pass from the same data as /trust/:
https://api.lumitrades.io/v1/trust/vendors (site_pages.fetch_vendors) plus each seller's free entry
https://api.lumitrades.io/v1/trust/vendors/<id> (observations, endpoints, pay-to chains, replies), cached in
state/trust_vendor_details.json (git-ignored) so an API outage reuses the last good copy.

Rules: real data only (a field the API doesn't report is left out, numbers are never estimated); neutral wording, no
verdicts about any business; paying Lumi never changes a score. A seller with no paid test-buy and no recorded test
payment attempt has essentially no data: its page is noindex and stays out of sitemap.xml. A seller that leaves the
list keeps its URL as a short noindex page pointing back to /trust/. Every data publish (scripts/publish.sh ->
build_pages.py --paths) regenerates these pages, so they refresh with the trust list.
"""
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

import seo
import site_pages as sp

ROOT = sp.ROOT
DIR = "sellers"
DETAIL_URL = sp.API + "/v1/trust/vendors/{id}"
DETAIL_CACHE = os.path.join(ROOT, "state", "trust_vendor_details.json")
LUMI_CHECK_NPM = "https://www.npmjs.com/package/lumi-check"
CHAIN_OF_PAYTO = {"xrpl": "XRPL", "evm": "EVM (Base)", "base": "Base", "stellar": "Stellar"}
STATUS_TXT = {"live": "Live: answering Lumi's free quote checks",
              "unreachable": "Unreachable in Lumi's recent free quote checks"}


# ---------- data ----------
def host_of(v):
    m = re.match(r"^https://([^/:?#]+)", sp._https(v.get("homepage")) or "")
    return m.group(1).lower() if m else ""


def slugs(vendors):
    """{vendor_id: slug}: the homepage host ("www." dropped, dots -> "-"), else the vendor id. Unique."""
    out, used = {}, set()
    for v in vendors:
        vid = str(v.get("id") or "")
        if not vid:
            continue
        h = re.sub(r"^www\.", "", host_of(v))
        s = re.sub(r"[^a-z0-9-]+", "-", (h or vid).lower().replace(".", "-")).strip("-") or re.sub(r"[^a-z0-9-]+", "-", vid.lower())
        if s in used:
            s = f"{s}-{re.sub(r'[^a-z0-9-]+', '-', vid.lower())}"
        used.add(s)
        out[vid] = s
    return out


def _load_cache():
    try:
        with open(DETAIL_CACHE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _fetch_one(vid):
    req = urllib.request.Request(DETAIL_URL.format(id=urllib.parse.quote(vid, safe="")),
                                 headers={"Accept": "application/json", "User-Agent": "lumitrades.io build"})
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d if d.get("kind") == "trust_vendor" and d.get("id") == vid else None


def fetch_details(ids, dry=False):
    """{id: free vendor entry}: live (parallel, short timeouts) with the cached copy as fallback per seller. Never raises."""
    cache = _load_cache()
    if dry:
        return {i: cache[i] for i in ids if i in cache}
    got = {}
    try:
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(_fetch_one, i): i for i in ids}
            for f in cf.as_completed(futs, timeout=40):
                try:
                    d = f.result()
                    if d:
                        got[futs[f]] = d
                except Exception:
                    pass
    except Exception as e:
        print(f"seller_pages: detail fetch incomplete ({e!r}), using cache", file=__import__("sys").stderr)
    if got:
        cache.update(got)
        try:
            os.makedirs(os.path.dirname(DETAIL_CACHE), exist_ok=True)
            with open(DETAIL_CACHE + ".tmp", "w", encoding="utf-8") as f:
                json.dump(cache, f)
            os.replace(DETAIL_CACHE + ".tmp", DETAIL_CACHE)
        except OSError:
            pass
    return {i: (got.get(i) or cache.get(i)) for i in ids if got.get(i) or cache.get(i)}


def has_data(v):
    """A paid test-buy or a recorded (opted-in) test payment attempt. Free quote checks alone = thin page (noindex)."""
    return bool((v.get("samples") or {}).get("paid_test_buys") or v.get("last_paid_observation") or sp.vendor_attempts(v))


def short_name(v):
    n = str(v.get("name") or v.get("id") or "").strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", n).strip() or n


def _day(iso):
    return str(iso or "")[:10]


def _outcome(o):
    dv = o.get("delivery")
    if dv == "delivered":
        return "Delivered"
    if dv in ("not_delivered", "failed") or o.get("data_returned") is False:
        return "No data"
    return "Inconclusive"


# ---------- page ----------
DESC_MAX = 155


def _fit(whos, rest, limit=DESC_MAX):
    """First seller label in `whos` that fits with `rest` in `limit` chars ("Name (host)", then "Name"); else the name
    cut at a word boundary with "…". The facts in `rest` are never cut."""
    for w in whos:
        if len(w) + len(rest) <= limit:
            return w + rest
    who = whos[-1]
    room = max(limit - len(rest) - 1, 8)
    cut = who[:room]
    if who[room:room + 1] not in ("", " "):  # mid-word: back up to the last space if that keeps at least half
        i = cut.rfind(" ")
        if i >= room // 2:
            cut = cut[:i]
    return cut.rstrip(" .,:;(-") + "…" + rest


def description(v, d, h):
    return _fit(*_desc_parts(v, d, h))


def _desc_parts(v, d, h):
    s = v.get("samples") or {}
    nm, host = short_name(v), host_of(v)
    who = [f"{nm} ({host})", nm] if host else [nm]
    n, dl = int(s.get("paid_test_buys") or 0), int(s.get("delivered") or 0)
    o = v.get("last_paid_observation") or {}
    a = sp.vendor_attempts(v)
    if n:
        txt = f": {n} paid x402 test-buy{'s' if n != 1 else ''} by Lumi in 30 days, {dl} delivered data"
        if o.get("observed_at"):
            txt += f"; latest {h.ctime(o['observed_at'], False)}"
        return who, txt + ". Dated results, not a review."
    if a:
        return who, (f": Lumi's x402 test payment not accepted yet ({a['count']} tr{'ies' if a['count'] != 1 else 'y'} on XRPL "
                f"since {h.ctime(a['first_attempt'], False)}). Dated results, not a review.")
    return who, f": on Lumi's x402 seller trust list. No paid test-buy on record yet. Dated observations, not a review."


def _row(k, v):
    return f"<tr><th scope=\"row\">{k}</th><td>{v}</td></tr>"


def body_html(h, v, d, slug, now_ms):
    E = h.E
    s = v.get("samples") or {}
    d = d or {}
    nm, full, host, vid = short_name(v), str(v.get("name") or v.get("id")), host_of(v), str(v.get("id"))
    o = v.get("last_paid_observation") or None
    rows = []
    home = sp.vendor_link(v)
    if home and not home.startswith(sp.API + "/trust/v/"):
        rows.append(_row("Seller", f'{E(full)} · <a href="{E(home)}" target="_blank" rel="noopener nofollow">{E(host or home)} ↗</a>'))
    else:
        rows.append(_row("Seller", E(full) + (f" · {E(host)}" if host else "")))
    obs = sorted((x for x in (d.get("observations") or []) if isinstance(x, dict) and x.get("observed_at")),
                 key=lambda x: str(x["observed_at"]), reverse=True)
    tchains = sorted({sp.badge_chain(x.get("network")) for x in obs} - {""})
    if not tchains and o:
        tchains = [c for c in [sp.badge_chain(o.get("network"))] if c]
    if tchains:
        rows.append(_row("Chains of Lumi's test-buys", E(" · ".join(tchains))))
    pchains = [CHAIN_OF_PAYTO.get(k, k) for k, a in (d.get("pay_to") or {}).items() if a]
    if pchains:
        rows.append(_row("Pay-to addresses listed for", E(" · ".join(pchains))))
    n, dl, inc = int(s.get("paid_test_buys") or 0), int(s.get("delivered") or 0), int(s.get("inconclusive_test_buys") or 0)
    if n:
        nd = n - dl - inc
        parts = [f"{dl} delivered data"] + ([f"{nd} returned no data"] if nd > 0 else []) + ([f"{inc} inconclusive"] if inc else [])
        rows.append(_row("Paid test-buys (last 30 days)", E(f"{n}: " + ", ".join(parts))))
    if o and o.get("observed_at"):
        ch = sp.badge_chain(o.get("network"))
        latest = f"{_outcome(o)} · {h.ctime(o['observed_at'])}" + (f" · {ch}" if ch else "") + (f" · HTTP {o['http_status']}" if o.get("http_status") else "")
        rows.append(_row("Latest paid test-buy", E(latest) + sp.badge_html(h, v) + sp.tx_html(h, v)))
    a = sp.vendor_attempts(v)
    if a:
        tried = (sp.ATT_TRIED_1.format(date=h.ctime(a["first_attempt"], False)) if a["count"] == 1
                 else sp.ATT_TRIED.format(n=a["count"], date=h.ctime(a["first_attempt"], False)))
        note = tried + (" " + sp.ATT_ONLINE if sp.seller_online(v, now_ms) else "")
        rows.append(_row("Label", f'<span class="tr-att" title="{E(sp.ATT_TIP)}">{E(sp.ATT_LABEL)}</span>'
                                  f'<span class="tr-att-note">{E(note)} <a href="#reply">{E(sp.ATT_HELP)}</a></span>'))
    if s.get("probes"):
        rows.append(_row("Free quote checks (last 30 days)", E(f"{s.get('probes_ok') or 0} of {s['probes']} returned a valid x402 quote")))
    lc = sp._last_checked(v)
    if lc:
        rows.append(_row("Last checked", E(h.ctime(lc, False))))
    st = v.get("status")
    if st:
        mon = STATUS_TXT.get(st, str(st))
        if any(e.get("daily_test_buy") for e in d.get("endpoints") or [] if isinstance(e, dict)):
            mon += "; on Lumi's test-buy list (daily while new or after a failure, weekly once steady)"
        rows.append(_row("Monitoring status", E(mon)))
    if v.get("score") is not None:
        conf = str(v.get("confidence") or "")
        rows.append(_row("Lumi score", E(f"{v['score']} / 100" + (f" ({conf} confidence)" if conf else ""))
                         + ' <span class="muted">· a summary of Lumi\'s own checks, not a rating of the business</span>'))
    reps = d.get("vendor_replies") or []
    if reps or v.get("replies"):
        k = len(reps) or int(v.get("replies") or 0)
        rows.append(_row("Seller replies", f'<a href="{E(DETAIL_URL.format(id=urllib.parse.quote(vid, safe="")))}" target="_blank" rel="noopener">{k} ↗</a>'))
    table = f'<div class="cp-tablewrap"><table class="cp-table sl-facts"><tbody>{"".join(rows)}</tbody></table></div>'

    hist = ""
    if obs:
        trs = "".join(f"<tr><td>{E(h.ctime(x['observed_at']))}</td><td>{E(sp.badge_chain(x.get('network')) or '—')}</td>"
                      f"<td>{E(_outcome(x))}</td><td class=\"num\">{E(x.get('http_status') or '—')}</td></tr>" for x in obs[:10])
        more = int(d.get("observations_total") or len(obs))
        hist = (f'<section class="card cp-sec" id="history"><h2>Recent paid test-buys</h2>\n'
                f'<div class="cp-tablewrap"><table class="cp-table"><thead><tr><th>When (US Central)</th><th>Chain</th><th>Result</th><th class="num">HTTP</th></tr></thead>'
                f'<tbody>{trs}</tbody></table></div>\n'
                f'<p class="meta">Showing {min(len(obs), 10)} of {more} in the last {int(d.get("window_days") or 30)} days. '
                f'Every tx hash and the signed receipts are in the <a href="../../agents/#paid-report">full report ($0.02)</a>.</p></section>\n')
    eps = [e for e in d.get("endpoints") or [] if isinstance(e, dict) and sp._https(e.get("url"))]
    ep = ""
    if eps:
        li = "".join(f'<li><code>{E(e.get("method") or "GET")} {E(e["url"])}</code>'
                     + (f' · listed price {E(e["listed_price"])} {E(e.get("listed_asset") or "")}' if e.get("listed_price") else "") + "</li>" for e in eps)
        ep = f'<section class="card cp-sec" id="endpoints"><h2>Endpoint{"s" if len(eps) > 1 else ""} Lumi tests</h2><ul class="ag-list">{li}</ul></section>\n'

    lede = (f"Lumi Trades runs an independent x402 seller trust list. It makes small paid test-buys from {E(nm)}"
            f"{' at ' + E(host) if host else ''} with its own wallet, records whether data came back, and publishes the dated results. "
            "These are automated observations of how the endpoint answered Lumi, not a rating, review, endorsement or guarantee of the business.")
    if not has_data(v):
        lede += " Lumi has no paid test-buy on record for this seller yet."
    enc = urllib.parse.quote(vid, safe="")
    return f"""<main class="wrap cp-main sl-main">
<p class="cp-crumb"><a href="../../">Lumi Trades</a> › <a href="../../trust/">Vendor trust</a> › {E(nm)}</p>
<h1>{E(nm)}: Lumi's x402 test-buy results</h1>
<p class="cp-lede">{lede}</p>
<section class="card cp-sec" id="summary"><h2>Summary</h2>
{table}
<p class="meta">Data from Lumi's free trust API, as of {E(h.ctime(v.get("_doc_generated") or d.get("generated_at"), False))}. Paying Lumi never changes a score: scores come only from Lumi's own checks.</p></section>
{hist}{ep}<section class="card cp-sec" id="check"><h2>Check before your agent pays</h2>
<p><a href="{LUMI_CHECK_NPM}" target="_blank" rel="noopener">Lumi Check</a> (npm <code>lumi-check</code>) is a free check an agent can run before it pays an x402 seller: allow, warn or block with reasons, the seller's score and a link to the live report, signed by Lumi.</p>
<p class="meta"><a href="../../trust/">Full vendor trust list</a> · <a href="{sp.API}/trust/v/{E(enc)}" target="_blank" rel="noopener">Lumi's live result page ↗</a> · <a href="{sp.API}/v1/trust/vendors/{E(enc)}" target="_blank" rel="noopener">Free JSON ↗</a> · <a href="{sp.API}/v1/trust/methodology" target="_blank" rel="noopener">Methodology ↗</a> · <a href="../../trust/#verify">Verify a test-buy yourself</a></p></section>
<section class="card cp-sec" id="reply"><h2>Right to reply</h2>
<p>Run {E(nm)} and think an observation is wrong or missing context? Email <a href="mailto:hello@lumitrades.io">hello@lumitrades.io</a>, or post a signed reply to <code>POST {sp.API}/v1/trust/replies</code>, signed with the key of a pay-to address listed for this entry (vendor id <code>{E(vid)}</code>). Verified replies are shown with the entry. Lumi can also re-run a check or remove an endpoint on request.</p></section>
<div class="disclaimer" role="note"><span class="warn-ico" aria-hidden="true">!</span><span><strong>Automated observations, not a rating or review of any business.</strong> Results describe how the endpoint answered Lumi's requests at the times shown. Few samples = low confidence.</span></div>
</main>
"""


def _head_fix(html_s, noindex):
    if noindex:
        html_s = html_s.replace('<meta name="robots" content="index, follow, max-image-preview:large">', '<meta name="robots" content="noindex, follow">', 1)
    return re.sub(r'<details class="lang-menu">.*?</details>', "", html_s, count=1, flags=re.S)  # English only: no language menu


def _en_h(h):
    import types
    g = types.SimpleNamespace(**vars(h))
    g.langs = [x for x in h.langs if x.en]
    return g


def page(h, tp, nav_items, V, gen_date, v, d, slug, now_ms):
    path = f"{DIR}/{slug}/"
    url = h.SITE + path
    nm = short_name(v)
    title = f"{nm}: Lumi's x402 test-buy results"
    desc = description(v, d, h)
    lc = sp._last_checked(v)
    about = {"@type": "WebAPI", "name": str(v.get("name") or nm)}
    home = sp._https(v.get("homepage"))
    if home:
        about["url"] = home
    ld = [seo.organization(h._, "trust"),
          {"@context": "https://schema.org", "@type": "ItemPage", "name": title, "url": url, "description": desc, "inLanguage": "en",
           "isPartOf": {"@id": seo.SITE_ID}, "publisher": {"@id": seo.ORG_ID}, "about": about,
           **({"dateModified": _day(lc)} if lc else {})},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Lumi Trades", "item": h.SITE},
              {"@type": "ListItem", "position": 2, "name": "Vendor trust", "item": h.SITE + "trust/"},
              {"@type": "ListItem", "position": 3, "name": nm, "item": url}]}]
    g = _en_h(h)
    R = "../../"
    head = tp.page_head(g, title, desc, url, V, path, "website", ld).replace("{ASSETS}", tp.assets(g, R, V))
    out = head + tp.chrome(g, R, R, nav_items, V, path, "trust") + body_html(g, v, d, slug, now_ms) + tp.footer(g, R, gen_date)
    return _head_fix(out, not has_data(v))


def gone_page(h, tp, nav_items, V, gen_date, slug):
    path = f"{DIR}/{slug}/"
    g = _en_h(h)
    R = "../../"
    title = "This seller is not on Lumi's trust list right now | Lumi Trades"
    desc = "This x402 seller is not on Lumi's curated trust list right now. See the current list of sellers and their dated test-buy results."
    head = tp.page_head(g, title, desc, h.SITE + path, V, path, "website", [seo.organization(h._, "trust")]).replace("{ASSETS}", tp.assets(g, R, V))
    body = (f'<main class="wrap cp-main"><p class="cp-crumb"><a href="../../">Lumi Trades</a> › <a href="../../trust/">Vendor trust</a></p>\n'
            f'<h1>This seller is not on the trust list right now</h1>\n<p class="cp-lede">{h.E(desc)} <a href="../../trust/">Vendor trust list →</a></p></main>\n')
    return _head_fix(head + tp.chrome(g, R, R, nav_items, V, path, "trust") + body + tp.footer(g, R, gen_date), True)


def build(h, tp, nav_items, V, gen_date, write, doc, dry=False):
    """English pass only. Writes sellers/<slug>/index.html for every listed seller (+ noindex pages for sellers that left
    the list). Returns sitemap entries [(path, lastmod, changefreq, priority)] for the indexable pages only."""
    vendors = [v for v in (doc or {}).get("vendors") or [] if v.get("id")]
    if not vendors:
        return []
    sl = slugs(vendors)
    details = fetch_details(list(sl), dry)
    now_ms = sp._iso_ms((doc or {}).get("generated_at")) or dt.datetime.now(dt.timezone.utc).timestamp() * 1000
    sm = []
    for v in vendors:
        vid = str(v["id"])
        v = dict(v, _doc_generated=(doc or {}).get("generated_at"))
        write(f"{DIR}/{sl[vid]}/index.html", page(h, tp, nav_items, V, gen_date, v, details.get(vid), sl[vid], now_ms))
        if has_data(v):
            sm.append((f"{DIR}/{sl[vid]}/", _day(sp._last_checked(v)) or gen_date, "daily", "0.6"))
    d = os.path.join(ROOT, DIR)
    if os.path.isdir(d):
        for x in sorted(os.listdir(d)):
            if x not in sl.values() and os.path.isfile(os.path.join(d, x, "index.html")):
                write(f"{DIR}/{x}/index.html", gone_page(h, tp, nav_items, V, gen_date, x))
    return sm


def links(doc, pre):
    """{vendor_id: href to its seller page} for /trust/ rows (pre = path from the trust page to the site root)."""
    return {k: f"{pre}{DIR}/{s}/" for k, s in slugs([v for v in (doc or {}).get("vendors") or [] if v.get("id")]).items()}


def paths():
    d = os.path.join(ROOT, DIR)
    return sorted(f"{DIR}/{x}/index.html" for x in os.listdir(d) if os.path.isfile(os.path.join(d, x, "index.html"))) if os.path.isdir(d) else []
