"""Checks for /agents/ and homepage claims that must match the price tables (audit 2026-10-23 L-6/L-7/L-8, L-1).
Run: python3 scripts/test_site_pages.py"""
import json, os, re, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_pages as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ["es", "pt", "tr", "ja", "ko"]


def i18n(lang):
    with open(os.path.join(ROOT, "assets", "i18n", f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)["pages"]



def blocklist_re():
    """Optional blocklist for generated copy. Never hard-coded here: read from the SITE_BLOCKLIST_RE env var (a regex)
    or the git-ignored file named by SITE_BLOCKLIST_FILE (default: site_blocklist.txt at the repo root), one regex per
    line. Returns None when neither is set."""
    pats = [os.environ.get("SITE_BLOCKLIST_RE", "").strip()]
    f = os.environ.get("SITE_BLOCKLIST_FILE", os.path.join(ROOT, "site_blocklist.txt"))
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            pats += [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    pats = [p for p in pats if p]
    return re.compile("|".join(f"(?:{p})" for p in pats), re.I) if pats else None

class SitePages(unittest.TestCase):
    def test_prices_snapshot_matches_table(self):
        """prices/index.json (copied from the live 402s by scripts/prices_snapshot.py) agrees with TRUST_PRICES."""
        with open(os.path.join(ROOT, "prices", "index.json"), encoding="utf-8") as f:
            snap = json.load(f)
        table = {ep: pr for _, ep, pr in sp.TRUST_PRICES if pr != "free"}
        self.assertEqual({p["endpoint"]: "$" + p["price_usd"] for p in snap["paid"]}, table)
        for p in snap["paid"]:
            self.assertTrue(p["accepts"])
            for o in p["accepts"]:
                if o["usd_pegged"]:
                    self.assertEqual(float(o["amount"]), float(p["price_usd"]), (p["endpoint"], o))
        self.assertRegex(snap["as_of"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertIn("/v1/check/wallets", snap["proof"]["test_buy_wallets"])
        self.assertNotRegex(json.dumps(snap).lower(), r"solana|partner|scam")

    def test_prices_page_and_llms_routing(self):
        with open(os.path.join(ROOT, "prices", "index.html"), encoding="utf-8") as f:
            page = f.read()
        with open(os.path.join(ROOT, "prices", "index.json"), encoding="utf-8") as f:
            snap = json.load(f)
        self.assertIn(snap["as_of"], page)
        self.assertIn('href="index.json"', page)
        self.assertIn('href="../trust/"', page)
        for p in snap["paid"]:
            self.assertIn("$" + p["price_usd"], page)
        self.assertNotRegex(page.lower(), r"solana|partner|scam")
        with open(os.path.join(ROOT, "llms.txt"), encoding="utf-8") as f:
            llms = f.read()
        self.assertIn("CHECK A SELLER BEFORE PAYING -> GET https://api.lumitrades.io/v1/verdict?url=", llms)
        self.assertIn("https://lumitrades.io/prices/index.json", llms)
        bl = blocklist_re()
        if bl:
            self.assertIsNone(bl.search(page + json.dumps(snap)))

    def test_route_counts_from_tables(self):
        c = sp.route_counts()
        self.assertNotIn("m", c)
        self.assertEqual(c["t"], 5)
        self.assertEqual((c["lo"], c["hi"]), ("$0.005", "$0.02"))
        txt = sp.AGENTS_ROUTES_TEXT.format(**c)
        self.assertIn("5 paid routes", txt)
        self.assertNotRegex(txt.lower(), r"market data|policy brief")

    def test_homepage_count_matches_tables(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            h = f.read()
        c = sp.route_counts()
        self.assertIn(f'Paid routes from <b class="mono">{c["lo"]}</b> to <b class="mono">{c["hi"]}</b> per call', h)
        self.assertNotIn("17 paid routes", h)

    def test_trial_text_covers_base_and_xrpl(self):
        self.assertIn("new Base and XRPL wallets", sp.AGENTS_ROUTES_TEXT)
        self.assertIn("0.01 USDC", sp.AGENTS_ROUTES_TEXT)
        self.assertIn("activated XRP Ledger account", sp.AGENTS_ROUTES_TEXT)
        self.assertIn("one trial per wallet", sp.AGENTS_ROUTES_TEXT)
        self.assertNotIn("no trial", sp.AGENTS_ROUTES_TEXT)

    def test_homepage_trial_text_covers_xrpl(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            h = f.read()
        self.assertIn("New Base and XRPL wallets get <b>3 free calls</b>", h)
        self.assertNotIn("no trial", h)

    def test_no_trading_routes_listed(self):
        # Oct 25, 2026: trust-only. The site lists x402 trust routes only (no market data, signals, levels or briefs)
        self.assertFalse(hasattr(sp, "MARKET_PRICES"))
        self.assertIs(sp.PRICES, sp.TRUST_PRICES)
        for name, route, _price in sp.PRICES:
            self.assertRegex(route, r"^(GET|POST) /v1/(trust/|verdict|check/batch)", route)
            self.assertNotRegex(name, r"(?i)signal|levels|projection|trade idea|slate|bias|market|fear|greed|brief", name)

    def test_a2a_link_points_to_agent_card(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_pages.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn('API + "/a2a"', src)
        self.assertIn('API + "/.well-known/agent-card.json"', src)

    def test_translations_exist_with_placeholders(self):
        keys = [sp.AGENTS_ROUTES_TEXT, "A2A agent card"] + [p[0] for p in sp.PRICES]
        for lang in LANGS:
            d = i18n(lang)
            for k in keys:
                self.assertTrue(d.get(k), (lang, k[:40]))
            for ph in ("{t}", "{lo}", "{hi}"):
                self.assertIn(ph, d[sp.AGENTS_ROUTES_TEXT], (lang, ph))
            self.assertNotIn("{m}", d[sp.AGENTS_ROUTES_TEXT], lang)



class CoinPageWording(unittest.TestCase):
    """Oct 25, 2026 (trust-only cleanup): coin pages, trade pages and /classic/ are removed from the repo and from the
    published _site/ (they 404 now), and none is in the sitemap."""
    SLUGS = ["xdc", "xrp", "xlm", "hbar", "axl", "zbcn", "btc", "eth", "sol"]

    def retired_paths(self):
        out = []
        for lang in [""] + [l + "/" for l in LANGS]:
            out += [lang + s + "/" for s in self.SLUGS] + [lang + "trades/"]
        return out + ["classic/"]

    def test_retired_pages_gone(self):
        for rel in self.retired_paths():
            self.assertFalse(os.path.exists(os.path.join(ROOT, rel, "index.html")), rel)

    def test_not_in_sitemap(self):
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            sm = f.read()
        for rel in self.retired_paths():
            self.assertNotIn(f"<loc>https://lumitrades.io/{rel}</loc>", sm)

    def test_old_trading_keys_pruned(self):
        old = ["{n}-day outlook (scenario levels)", "Lumi's {n}-day projection", "What is Lumi's {sym} price prediction?",
               "{sym} Price Analysis Today & Outlook | Lumi Trades", "Leverage", "Trade ideas", "Market data",
               "Daily Institutional & Policy Brief", "Trust layer for AI-agent payments"]
        for lang in LANGS:
            d = i18n(lang)
            for k in old:
                self.assertNotIn(k, d, (lang, k))


class Beacon(unittest.TestCase):
    """Cloudflare Web Analytics: lumitrades.io is DNS-only (GitHub Pages), so every page needs the manual beacon."""
    def test_every_page_has_beacon(self):
        import build_pages as bp
        missing = []
        for d, _dirs, files in os.walk(ROOT):
            if "/.git" in d or "/state" in d:
                continue
            for f in files:
                if f.endswith(".html"):
                    p = os.path.join(d, f)
                    with open(p, encoding="utf-8") as fh:
                        src = fh.read()
                    if "</head>" in src and bp.CF_BEACON not in src:
                        missing.append(os.path.relpath(p, ROOT))
        self.assertEqual(missing, [])

    def test_with_beacon_idempotent(self):
        import build_pages as bp
        once = bp.with_beacon("<html><head><title>x</title></head><body></body></html>")
        self.assertEqual(once.count("beacon.min.js"), 1)
        self.assertEqual(bp.with_beacon(once), once)

    def test_with_beacon_refreshes_old_token(self):
        import build_pages as bp
        stale = bp.CF_BEACON.replace(bp.CF_BEACON_TOKEN, "0" * 32)
        out = bp.with_beacon("<html><head>" + stale + "\n</head><body></body></html>")
        self.assertIn(bp.CF_BEACON, out)
        self.assertNotIn("0" * 32, out)
        self.assertEqual(out.count("beacon.min.js"), 1)


class TikTokLink(unittest.TestCase):
    """Lumi's TikTok sits wherever the X and YouTube links are: footers, header socials, JSON-LD sameAs, all 6 languages."""
    TT = "https://www.tiktok.com/@lumitradesio"
    A = '<a href="https://www.tiktok.com/@lumitradesio" rel="me noopener" target="_blank">TikTok</a>'

    def test_same_as(self):
        import seo
        self.assertIn(self.TT, seo.SAME_AS)

    def test_every_page_with_youtube_has_tiktok(self):
        missing = []
        for d, _dirs, files in os.walk(ROOT):
            if "/.git" in d or "/state" in d:
                continue
            for f in files:
                if f.endswith(".html"):
                    p = os.path.join(d, f)
                    with open(p, encoding="utf-8") as fh:
                        src = fh.read()
                    yt = src.count('href="https://www.youtube.com/@lumitradesio"')
                    if yt and src.count(f'href="{self.TT}" rel="me noopener"') != yt:
                        missing.append(os.path.relpath(p, ROOT))
                    if '"sameAs": ["https://x.com/Lumisinsite"' in src and f'"{self.TT}"' not in src:
                        missing.append(os.path.relpath(p, ROOT) + " (sameAs)")
        self.assertEqual(missing, [])

    def test_footers_all_languages(self):
        for pre in [""] + [l + "/" for l in LANGS]:
            for page in ("index.html", "how-it-works/index.html", "trust/index.html", "agents/index.html"):
                with open(os.path.join(ROOT, pre + page), encoding="utf-8") as f:
                    self.assertIn(self.A, f.read(), pre + page)


class OrgAltName(unittest.TestCase):
    """Organization JSON-LD carries the YouTube channel name as alternateName and TikTok in sameAs, on every page that has it."""
    def test_generator(self):
        import seo
        org = seo.organization(lambda x: x)
        self.assertEqual(org["alternateName"], "Lumi")
        self.assertIn("https://www.tiktok.com/@lumitradesio", org["sameAs"])

    def test_every_org_node(self):
        bad, n = [], 0
        for d, _dirs, files in os.walk(ROOT):
            if "/.git" in d or "/state" in d:
                continue
            for f in files:
                if not f.endswith(".html"):
                    continue
                p = os.path.join(d, f)
                with open(p, encoding="utf-8") as fh:
                    src = fh.read()
                for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', src, re.S):
                    data = json.loads(m.group(1))
                    for node in data if isinstance(data, list) else [data]:
                        if node.get("@id") == "https://lumitrades.io/#organization":
                            n += 1
                            if node.get("alternateName") != "Lumi" or "https://www.tiktok.com/@lumitradesio" not in node.get("sameAs", []):
                                bad.append(os.path.relpath(p, ROOT))
        self.assertGreater(n, 0)
        self.assertEqual(bad, [])


class ContactPage(unittest.TestCase):
    """/contact/: official addresses + accounts in every language, ContactPage JSON-LD, in the sitemap, linked from footers."""
    def test_pages_exist_and_in_sitemap(self):
        import contact_page as cp
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            sm = f.read()
        for lang in [""] + [l + "/" for l in LANGS]:
            with open(os.path.join(ROOT, lang, "contact", "index.html"), encoding="utf-8") as f:
                h = f.read()
            for s in ("hello@lumitrades.io", "lumi@lumitrades.io", '"@type": "ContactPage"',
                      "security.txt", "https://x.com/Lumisinsite", "https://github.com/lumitrades", "lumi-check", "trust/#reply",
                      cp.NOT_AFFILIATED):
                self.assertIn(s, h, (lang, s))
            for s in ("admin@", "receive-only"):
                self.assertNotIn(s, h, (lang, s))
            for s in ("scam", "solana", "cypher", "support and resistance"):
                self.assertNotIn(s, h.split("<main", 1)[1].split("</main>", 1)[0].lower(), (lang, s))
            m = re.search(r'<meta name="description" content="([^"]*)"', h)
            self.assertLessEqual(len(m.group(1)), 155, lang)
            self.assertIn(f"<loc>https://lumitrades.io/{lang}contact/</loc>", sm)
        for lang in LANGS:
            tr = i18n(lang)
            for k in (cp.TITLE, cp.H1, cp.DESC, cp.LEDE, cp.NOTE):
                self.assertIn(k, tr, (lang, k[:40]))

    def test_footers_link_contact(self):
        for rel in ("index.html", "privacy/index.html", "trust/index.html", "es/trust/index.html", "blog/index.html", "how-it-works/index.html"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                foot = f.read().split('<footer', 1)[1]
            self.assertIn('contact/">', foot, rel)


class PrivacyPage(unittest.TestCase):
    """/privacy/ (scan 2026-10-23 #1): exists in every language, is linked from every footer and newsletter form, names no exchange."""
    def test_pages_exist_translated_and_in_sitemap(self):
        import privacy_page as pp
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            sm = f.read()
        for lang in [""] + [l + "/" for l in LANGS]:
            path = os.path.join(ROOT, lang, "privacy", "index.html")
            with open(path, encoding="utf-8") as f:
                h = f.read()
            self.assertIn("hello@lumitrades.io", h)
            self.assertIn(pp.UPDATED.isoformat(), h)
            self.assertFalse(__import__("i18n").has_hidden_name(h))
            self.assertIn('id="lumi-check"', h)          # Lumi Check section (English on every language page for now)
            self.assertNotIn("draft", h.lower())
            self.assertIn(f"<loc>https://lumitrades.io/{lang}privacy/</loc>", sm)
            if lang:
                self.assertNotIn(pp.LEDE[:60], h)
        for lang in LANGS:
            tr = i18n(lang)
            for k in [pp.TITLE, pp.DESC, pp.LEDE] + [x for _, head, ps in pp.SECTIONS for x in [head] + ps]:
                self.assertIn(k, tr, (lang, k[:40]))

    def test_every_footer_and_newsletter_links_privacy(self):
        bad = []
        for dp, _, files in os.walk(ROOT):
            if "/." in dp or "/node_modules" in dp:
                continue
            for fn in files:
                if not fn.endswith(".html"):
                    continue
                with open(os.path.join(dp, fn), encoding="utf-8") as f:
                    h = f.read()
                foot = re.findall(r"<footer.*?</footer>", h, re.S)
                fine = re.findall(r'<p class="nl-fine">.*?</p>', h, re.S)
                if any("privacy/" not in x for x in foot + fine):
                    bad.append(os.path.relpath(os.path.join(dp, fn), ROOT))
        self.assertEqual(bad, [])

    def test_homepage_description_short_and_current(self):
        import build_pages as bp
        self.assertLessEqual(len(bp.INDEX_DESC), 155)
        self.assertNotIn("XLM, HBAR", bp.INDEX_DESC)
        for lang in LANGS:
            self.assertLessEqual(len(i18n(lang)[bp.INDEX_DESC]), 155, lang)


class NoOldExchangeInStaticHtml(unittest.TestCase):
    """Oct 25, 2026: the affiliate/referral links are gone entirely. No built page in any language names the old exchange partner or carries
    an affiliate or referral link; the scrubber stays as a safety filter for free text."""
    def test_scrubber(self):
        import hashlib
        import i18n as m
        fake = hashlib.sha256(b"foonix").hexdigest()
        m.HIDDEN_NAME_SHA256.add(fake)
        try:
            f = m.no_us_hidden_names
            self.assertEqual(f("venues (Foonix, Binance, OKX) list no perp"), "venues (Binance, OKX) list no perp")
            self.assertEqual(f("on Kraken or Foonix."), "on Kraken.")
            self.assertEqual(f("Foonix lists it"), "a supported exchange lists it")
            self.assertEqual(f("no exchange here"), "no exchange here")
        finally:
            m.HIDDEN_NAME_SHA256.discard(fake)

    def test_no_affiliate_code_or_config(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "assets", "affiliate.js")))
        # data/ (including the old affiliate config) is no longer in the repo or the published site
        self.assertFalse(os.path.exists(os.path.join(ROOT, "data", "config.json")))

    def test_no_old_exchange_or_affiliate_in_built_html(self):
        bad = []
        for dp, _, files in os.walk(ROOT):
            if "/." in dp or "/state" in dp or "/node_modules" in dp or "/posts" in dp:
                continue
            for fn in files:
                if fn.endswith(".html") or fn in ("sitemap.xml", "feed.xml") or (dp.endswith("assets/i18n") and fn.endswith((".js", ".json"))):
                    with open(os.path.join(dp, fn), encoding="utf-8") as f:
                        low = f.read().lower()
                    if __import__("i18n").has_hidden_name(low) or re.search(r"affiliate(?!d)|referral|[?&]ref=|aff-foot", low):
                        bad.append(os.path.relpath(os.path.join(dp, fn), ROOT))
        self.assertEqual(bad, [])


class TrustBadge(unittest.TestCase):
    """/trust/ "Tested by Lumi" badge: only from a real paid test-buy, never invented, same in all 6 languages."""
    class H:
        E = staticmethod(lambda s: __import__("html").escape(str(s)))
        _ = staticmethod(lambda s, **kw: s.format(**kw) if kw else s)

    def test_delivered(self):
        v = {"last_paid_observation": {"observed_at": "2026-10-24T09:21:21.000Z", "network": "xrpl:0", "delivery": "delivered", "data_returned": True}}
        b = sp.badge_html(self.H, v)
        self.assertIn("b-delivered", b)
        self.assertIn(">Last test-buy<", b)
        self.assertIn(">delivered · 10-24-2026 · XRPL<", b)
        self.assertNotIn(">Tested by Lumi<", b)  # one delivered buy is not the badge

    def test_earned_only_from_badge_verdict(self):
        v = {"id": "x-earned", "score": 91, "last_paid_observation": {"observed_at": "2026-10-24T09:21:21Z", "network": "xrpl:0", "delivery": "delivered"}}
        old = dict(sp.BADGE_EARNED)
        try:
            sp.BADGE_EARNED.clear()
            self.assertNotIn(">Tested by Lumi<", sp.badge_html(self.H, v))
            sp.BADGE_EARNED["x-earned"] = True
            b = sp.badge_html(self.H, v)
            self.assertIn("b-earned", b)
            self.assertIn(">Tested by Lumi<", b)
            self.assertIn(">earned<", b)
            self.assertLess(b.index("b-earned"), b.index(">Last test-buy<"))
        finally:
            sp.BADGE_EARNED.clear(); sp.BADGE_EARNED.update(old)

    def test_not_scored_yet(self):
        self.assertEqual(sp.score_html(self.H, {"score": None}), "Not scored yet")
        self.assertEqual(sp.score_html(self.H, {"score": 84}), "84")

    def test_no_delivery_and_chains(self):
        for net, ch in (("eip155:8453", "Base"), ("stellar:pubnet", "Stellar")):
            v = {"last_paid_observation": {"observed_at": "2026-10-23T04:12:22Z", "network": net, "delivery": "not_delivered", "data_returned": False}}
            b = sp.badge_html(self.H, v)
            self.assertIn("b-no_delivery", b)
            self.assertIn(f">not delivered · 10-23-2026 · {ch}<", b)

    def test_never_tested_or_unknown(self):
        self.assertEqual(sp.badge_html(self.H, {}), "")
        self.assertEqual(sp.badge_html(self.H, {"last_paid_observation": None}), "")
        self.assertEqual(sp.badge_html(self.H, {"last_paid_observation": {"delivery": "delivered"}}), "")  # no date: no badge
        b = sp.badge_html(self.H, {"last_paid_observation": {"observed_at": "2026-10-24T01:00:00Z", "network": "solana:x", "delivery": "delivered"}})
        self.assertIn(">delivered · 10-24-2026<", b)  # unknown chain is left out, not guessed

    def test_no_scam_or_pnl_wording(self):
        txt = " ".join([sp.BADGE_NOTE, sp.BADGE_KEY, sp.BADGE_TIP_END, *sp.BADGE_TIP.values(), *sp.BADGE_RES.values()]).lower()
        for w in ("scam", "fraud", "p&l", "profit", "track record"):
            self.assertNotIn(w, txt)

    def test_translated(self):
        keys = [sp.BADGE_NOTE, sp.BADGE_KEY, sp.BADGE_TIP_END, "Tested by Lumi", sp.BADGE_EARNED_TXT, sp.BADGE_EARNED_TIP, sp.LAST_LABEL,
                sp.NOT_SCORED, *sp.BADGE_TIP.values(), *sp.BADGE_RES.values()]
        for lang in LANGS:
            pages = i18n(lang)
            for k in keys:
                self.assertIn(k, pages, f"{lang}: {k}")
            self.assertEqual(pages["Tested by Lumi"], "Tested by Lumi")
            self.assertIn("Tested by Lumi", pages[sp.BADGE_NOTE])
            with open(os.path.join(ROOT, "assets", "i18n", f"{lang}.json"), encoding="utf-8") as f:
                ui = json.load(f)["ui"]
            for k in (sp.BADGE_EARNED_TXT, sp.BADGE_EARNED_TIP, sp.LAST_LABEL, sp.NOT_SCORED, "not delivered"):
                self.assertIn(k, ui, f"{lang} ui: {k}")  # trust.js renders these in the browser

class PaymentAttemptsLabel(unittest.TestCase):
    """Grey 'Test payment not accepted yet' label: only vendors in the derived list, only with zero paid buys, neutral wording."""
    SNAP = {"edge-agents": {"count": 4, "first_attempt": "2026-10-23T03:08:48.615Z"}}
    NOW = 1792860000000  # 2026-10-24T16:40Z

    def h(self):
        import types, html
        return types.SimpleNamespace(E=lambda s: html.escape(str(s)), _=lambda s, **kw: s.format(**kw) if kw else s,
                                     ctime=lambda *a, **k: "Oct 22, 2026", L=types.SimpleNamespace(code="en"))

    def probe(self, ms_ago, ok=True):
        import datetime as dt
        t = dt.datetime.fromtimestamp((self.NOW - ms_ago) / 1000, dt.timezone.utc).isoformat()
        return {"checked_at": t, "http_status": 402 if ok else 500, "valid_quote": ok}

    def test_opt_in_only(self):
        self.assertIsNotNone(sp.vendor_attempts({"id": "edge-agents", "samples": {"paid_test_buys": 0}}, self.SNAP))
        self.assertIsNone(sp.vendor_attempts({"id": "monid", "samples": {"paid_test_buys": 0}}, self.SNAP))

    def test_gone_after_a_paid_buy(self):
        self.assertIsNone(sp.vendor_attempts({"id": "edge-agents", "samples": {"paid_test_buys": 1}}, self.SNAP))
        self.assertIsNone(sp.vendor_attempts({"id": "edge-agents", "last_paid_observation": {"x": 1}}, self.SNAP))

    def test_api_field_wins(self):
        v = {"id": "x", "payment_attempts": {"status": "test_payment_not_accepted_yet", "count": 5, "first_attempt": "2026-10-20T00:00:00Z"}}
        self.assertEqual(sp.vendor_attempts(v, {})["count"], 5)

    def test_online_sentence_needs_fresh_valid_402(self):
        old = sp.att_snapshot
        sp.att_snapshot = lambda: self.SNAP
        try:
            base = {"id": "edge-agents", "status": "live", "samples": {"paid_test_buys": 0}}
            on = sp.attempts_html(self.h(), dict(base, latest_probes=[self.probe(10 * 60000)]), self.NOW)
            self.assertIn("Lumi has tried 4 times on XRPL since Oct 22, 2026. The seller is online", on)
            self.assertIn('href="#reply"', on)
            for probes in ([self.probe(3 * 3600000)], [self.probe(60000, ok=False)], []):
                off = sp.attempts_html(self.h(), dict(base, latest_probes=probes), self.NOW)
                self.assertIn("Lumi has tried 4 times on XRPL", off)
                self.assertNotIn("online", off)
            self.assertNotRegex(on.lower(), r"scam|fraud")
            bl = blocklist_re()
            if bl:
                self.assertIsNone(bl.search(on))
        finally:
            sp.att_snapshot = old

    def test_snapshot_file_is_well_formed(self):
        with open(sp.ATT_SNAPSHOT, encoding="utf-8") as f:
            d = json.load(f)["vendors"]
        for vid, a in d.items():
            self.assertGreaterEqual(a["count"], 1, vid)
            self.assertEqual(a["count"], len(set(a["tx_hashes"])), vid)
            self.assertIsNotNone(sp._iso_ms(a["first_attempt"]), vid)

    def test_derive_all_sellers(self):
        """derive_attempts_all.py labels every seller with rejected XRPL payments and no completed buy, nobody else."""
        import importlib, tempfile
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        d = importlib.import_module("derive_attempts_all")
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log"); out = os.path.join(tmp, "att.json")
            with open(log, "w") as f:
                for vid, tx, ts in (("a", "T1", "2026-10-22T01:00:00Z"), ("a", "T2", "2026-10-23T01:00:00Z"), ("a", "T2", "2026-10-23T01:00:00Z"),
                                    ("b", "T3", "2026-10-22T02:00:00Z"), ("gone", "T4", "2026-10-22T03:00:00Z")):
                    f.write(json.dumps({"ts": ts, "event": "buy_not_validated", "vendor": vid, "tx": tx}) + "\n")
                f.write(json.dumps({"ts": "2026-10-22T04:00:00Z", "event": "plan", "vendor": "c", "tx": "T5"}) + "\n")
            vs = [{"id": "a", "samples": {"paid_test_buys": 0}}, {"id": "b", "samples": {"paid_test_buys": 2}},
                  {"id": "c", "samples": {}}, {"id": "d", "samples": {}}]
            saved = (d.LOG, d.OUT, d.vendors, sys.argv)
            d.LOG, d.OUT, d.vendors, sys.argv = log, out, (lambda: vs), ["x"]
            try:
                d.main()
            finally:
                d.LOG, d.OUT, d.vendors, sys.argv = saved
            with open(out) as f:
                got = json.load(f)["vendors"]
        self.assertEqual(sorted(got), ["a"])
        self.assertEqual(got["a"]["count"], 2)
        self.assertEqual(got["a"]["first_attempt"], "2026-10-22T01:00:00Z")

    def test_publish_runs_derive(self):
        with open(os.path.join(ROOT, "scripts", "publish.sh")) as f:
            sh = f.read()
        self.assertIn("python3 scripts/derive_attempts_all.py", sh)
        self.assertLess(sh.index("derive_attempts_all.py)"), sh.index("python3 scripts/build_pages.py --paths"))


class TopSellersPage(unittest.TestCase):
    """/top-sellers/: built only from test results in scripts/top_sellers_snapshot.json; no failing seller, no payment input."""
    def ts(self):
        import top_sellers_page as ts
        return ts

    def test_rule_on_synthetic_results(self):
        import datetime as _dt
        ts = self.ts()
        now = _dt.datetime(2026, 10, 24, tzinfo=_dt.timezone.utc)
        def s(*v, at="2026-10-23T00:00:00Z"):
            return {"key": "k", "tests": [{"at": at, "verdict": {"d": "delivered", "n": "not_delivered", "i": "inconclusive"}[x]} for x in v]}
        self.assertTrue(ts.qualifies(s("d", "d"), now))
        self.assertTrue(ts.qualifies(s("d", "n", "d"), now))
        self.assertTrue(ts.qualifies(s("d", "i", "d"), now))       # inconclusive = Lumi-side, skipped
        self.assertFalse(ts.qualifies(s("d"), now))                # one test is not "consistently"
        self.assertFalse(ts.qualifies(s("n", "d", "d"), now))      # latest must deliver
        self.assertFalse(ts.qualifies(s("d", "n", "n", "d"), now))  # only the last 3 count
        self.assertFalse(ts.qualifies(s("d", "d", at="2026-09-01T00:00:00Z"), now))

    def test_rows_come_from_snapshot_and_all_qualify(self):
        ts = self.ts()
        snap = ts.load()
        by = {x["key"]: x for x in snap["sellers"]}
        cats = ts.rows(snap)
        self.assertTrue(cats)
        now = ts._ts(snap["generated_at"])
        for c, rs in cats.items():
            self.assertIn(c, ts.CAT_LABEL)
            self.assertEqual([r["key"] for r in rs], [x["key"] for x in sorted((by[r["key"]] for r in rs), key=ts.ordering)])
            for r in rs:
                self.assertTrue(ts.qualifies(by[r["key"]], now), r["key"])
                self.assertEqual(ts.conclusive(by[r["key"]])[0]["verdict"], "delivered")
                self.assertTrue(r["url"].startswith("https://api.lumitrades.io/trust/v/"))
        # ordering keys never look at payment
        import inspect
        self.assertNotRegex(inspect.getsource(ts.ordering) + inspect.getsource(ts.qualifies), r"pa(id|y)|plan|monitor")

    def test_pages_translated_in_sitemap_and_clean(self):
        ts = self.ts()
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            sm = f.read()
        keys = [ts.TITLE, ts.H1, ts.DESC, ts.LEDE, ts.RULE_HEAD] + ts.RULE + [l for _c, l, _r in ts.CATEGORIES] + [
            ts.L_CHAINS, ts.L_LAST, ts.L_RESULT, ts.L_OF, ts.L_VIEW, ts.L_ASOF, ts.L_COUNT, ts.L_EMPTY, ts.TRUST_NOTE]
        for lang in LANGS:
            tr = i18n(lang)
            for k in keys:
                self.assertIn(k, tr, (lang, k[:40]))
        n = sum(len(r) for r in ts.rows().values())
        for lang in [""] + [l + "/" for l in LANGS]:
            self.assertIn(f"<loc>https://lumitrades.io/{lang}top-sellers/</loc>", sm)
            with open(os.path.join(ROOT, lang, "top-sellers", "index.html"), encoding="utf-8") as f:
                h = f.read()
            self.assertEqual(h.count("https://api.lumitrades.io/trust/v/"), n + h.count('"url": "https://api.lumitrades.io/trust/v/'), lang)
            self.assertIn('href="../trust-policy/"', h)
            self.assertNotRegex(h.lower(), r"\bscam|p&amp;l|not delivered|\{(n|m|days|mail|policy)\}")
            with open(os.path.join(ROOT, lang, "trust", "index.html"), encoding="utf-8") as f:
                self.assertIn('href="../top-sellers/"', f.read())


class PolicyPageSelection(unittest.TestCase):
    """/trust-policy/#selection: how sellers are chosen for test-buys (must match the box-side runners)."""
    def _sel(self):
        import policy_page as pp
        return [ps for sid, _h, ps in pp.SECTIONS if sid == "selection"][0], pp

    def test_caps_and_rules_stated(self):
        ps, _ = self._sel()
        txt = " ".join(ps)
        for s in ("0.75 USDC", "0.15 USDC", "0.30 RLUSD", "0.10 XRP", "x402 Bazaar", "more than 30 days old", "{mail}"):
            self.assertIn(s, txt)
        self.assertNotIn("scam", txt.lower())
        # Check-driven priority (lumi-api free-check-priority): objective signals only, independent of who ran the check and
        # whether it was paid; at most 5 sellers a day and once per seller per 30 days (PRIORITY_SELLER_DAYS).
        base_add = [p for p in ps if p.startswith("<b>Base, one addition:</b>")][0]
        for s in ("objective signals", "never test-bought", "front of the next day's Base list", "At most 5 sellers",
                  "Whether the check was free or paid, and who ran it, is not considered", "at most once every 30 days",
                  "only from Lumi's own records and public data", "such as a payTo address"):
            self.assertIn(s, base_add)
        self.assertNotIn("a paid Lumi check", base_add)
        self.assertNotIn("warning signs", base_add)
        # Sales firewall (legal review 2-M1).
        self.assertIn("We never pitch paid plans to a seller within 30 days of a failed or warning result, and our sales emails never cite a seller's score.", ps)
        self.assertTrue(any("Paying Lumi never changes" in p and "never change this order" in p for p in ps))
        # Seller rotation (tools/test_rotation.ts, 2026-10-25): new/failing/changed sellers daily, steady ones weekly on a per-seller weekday.
        stellar = [p for p in ps if p.startswith("<b>Stellar:</b>")][0]
        for s in ("every day", "bought the day it appears", "cheapest first", "once a week", "its own fixed weekday", "price or payTo change",
                  "0.15 USDC", "at most 4 buys a day", "not ranked by popularity"):
            self.assertIn(s, stellar)
        self.assertNotIn("then the sellers whose last test-buy is oldest", stellar)
        self.assertNotIn("(on Mondays)", stellar)
        xrpl = [p for p in ps if p.startswith("<b>XRPL:</b>")][0]
        for s in ("fewer than 5 delivered test-buys", "once a week", "its own fixed weekday", "0.30 RLUSD and 0.10 XRP"):
            self.assertIn(s, xrpl)
        self.assertNotIn("We try every seller on the list once a day", xrpl)
        self.assertNotRegex(txt.lower(), r"p&l|profit|return")

    def test_caps_match_runners_when_present(self):
        import re as _re
        tools = os.environ.get("LUMI_TOOLS_DIR", "")
        if not tools:
            self.skipTest("LUMI_TOOLS_DIR not set")
        cb, tb = os.path.join(tools, "catalog_buys.ts"), os.path.join(tools, "trust_testbuys.ts")
        if not (os.path.exists(cb) and os.path.exists(tb)):
            self.skipTest("runners not on this machine")
        cbs, tbs = open(cb).read(), open(tb).read()
        self.assertIn("const DAILY_CAP = 750_000n", cbs)
        self.assertIn("const STALE_DAYS = 30", cbs)
        self.assertIn("const DAILY_CAP = { RLUSD: 0.30, XRP: 0.10 }", tbs)
        self.assertIn("const STELLAR_CAP = 0.15", tbs)
        self.assertIn("const STELLAR_MAX_BUYS = 4", tbs)
        self.assertIn("const MAX_PRICE = 0.05", tbs)
        # Seller rotation (2026-10-25): policy text says "fewer than 5 delivered", 7/14-day windows, per-seller weekday.
        self.assertIn("const XRPL_NEW_MIN = 5", tbs)
        rot = os.path.join(tools, "test_rotation.ts")
        if os.path.exists(rot):
            rs = open(rot).read()
            self.assertIn("weeklySlot", rs)
            self.assertIn("7 * DAY", rs)
            self.assertIn("14 * DAY", rs)

    def test_no_pay_to_rank_covers_paid_badges(self):
        import policy_page as pp
        p1 = [ps for sid, _h, ps in pp.SECTIONS if sid == "no-pay-to-rank"][0][0]
        for s in ("never changes a seller's score, tier, ranking or “Tested by Lumi” result",
                  "Paid plans add a separate “Monitored by Lumi” badge that says it is paid", "“Verified owner”", "labelled as paid"):
            self.assertIn(s, p1)
        self.assertNotIn("ranking or badge", p1 + pp.DESC)
        for lang in LANGS:
            tr = i18n(lang)
            for k in (p1, pp.DESC):
                self.assertIn(k, tr, (lang, k[:40]))
                self.assertIn("Monitored by Lumi" if k == p1 else "Tested by Lumi", tr[k], lang)

    def test_translated_and_built(self):
        ps, pp = self._sel()
        head = [h for sid, h, _p in pp.SECTIONS if sid == "selection"][0]
        for lang in LANGS:
            tr = i18n(lang)
            for k in [head] + ps:
                self.assertIn(k, tr, (lang, k[:40]))
                self.assertEqual(k.count("{mail}"), tr[k].count("{mail}"), (lang, k[:40]))
        for lang in [""] + [l + "/" for l in LANGS]:
            with open(os.path.join(ROOT, lang, "trust-policy", "index.html"), encoding="utf-8") as f:
                h = f.read()
            self.assertIn('id="selection"', h)
            self.assertIn("0.75 USDC", h)
            if lang == "":
                self.assertIn("each on its own fixed weekday", h)
                self.assertIn("at most once every 30 days", h)
                self.assertIn("“Monitored by Lumi” badge that says it is paid", h)
            self.assertIn("Monitored by Lumi", h)
            self.assertNotIn("ranking or badge", h)
            self.assertIn("mailto:hello@lumitrades.io", h)
            self.assertNotIn("{mail}", h)


class InfoPages(unittest.TestCase):
    """/pricing/, /about/ and /terms/ (scripts/info_pages.py): English only, published (indexed, in the sitemap), linked
    from every footer; trust-only copy; the postal address only in /terms/ section 17."""
    SLUGS = ("pricing", "about", "terms")

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return f.read()

    def test_published_english_only(self):
        sm = self.read("sitemap.xml")
        for slug in self.SLUGS:
            t = self.read(f"{slug}/index.html")
            self.assertIn('<meta name="robots" content="index, follow', t, slug)
            self.assertNotIn("noindex", t, slug)
            self.assertIn(f"<loc>https://lumitrades.io/{slug}/</loc>", sm, slug)
            self.assertNotIn('hreflang="es"', t, slug)
            for l in LANGS:
                self.assertFalse(os.path.exists(os.path.join(ROOT, l, slug)), (l, slug))
            body = t.split("<main", 1)[1].split("</main>", 1)[0]
            low = re.sub(r'href="[^"]*"', "", body.lower())
            for w in ("draft", "[pending", "placeholder", "trust layer", "market data", "policy brief", "fear", "greed",
                      "sentiment", "funding", "signal", "leverage", "trade idea", "bitunix", "solana", "paper trading",
                      "write to us", "based in", "/workspace", "independent"):
                self.assertNotIn(w, low, (slug, w))

    def test_terms_addendum_b(self):
        import info_pages
        t = self.read("terms/index.html")
        for s_ in ("Who runs the service", "sole proprietorship", "DISCLAIMER OF WARRANTIES", "LIMITATION OF LIABILITY",
                   "US$100", "OFAC", "Governing law", "principally resides and conducts business",
                   "must be sent by email to", "and are effective when received",
                   "Our postal address, provided as required by law, is:", 'href="mailto:legal@lumitrades.io"',
                   "Trust Data Licence, version 2026-10-22"):
            self.assertIn(s_, t)
        self.assertNotEqual(info_pages.NOTICE_ADDRESS, info_pages.NOTICE_PLACEHOLDER)
        # D14 open: no refund/retry remedy paragraph until the refund/credit flow exists.
        self.assertNotIn("If a payment settles but you", t)
        self.assertNotIn("Idempotency-Key", t)
        self.assertIn(info_pages.NOTICE_ADDRESS, t)
        self.assertNotIn("[NOTICE ADDRESS", t)
        self.assertNotIn("[PENDING", t)

    def test_postal_address_only_on_terms(self):
        import info_pages
        street = info_pages.NOTICE_ADDRESS.split(",")[1].strip()
        hits = []
        for dp, _, files in os.walk(ROOT):
            if "/." in dp or "/state" in dp or "/scripts" in dp or "/node_modules" in dp or "/_site" in dp:
                continue
            for fn in files:
                if fn.endswith((".html", ".txt", ".xml", ".json", ".js")):
                    with open(os.path.join(dp, fn), encoding="utf-8", errors="ignore") as f:
                        if street in f.read():
                            hits.append(os.path.relpath(os.path.join(dp, fn), ROOT))
        self.assertEqual(sorted(hits), ["terms/index.html"])

    def test_pricing_matches_tables(self):
        t = self.read("pricing/index.html")
        for _, ep, pr in sp.TRUST_PRICES:
            self.assertIn(ep.replace("&", "&amp;"), t)
            self.assertIn(pr, t)
        for nm, _, _ in sp.MONITOR_PLANS + sp.FEED_PLANS:
            self.assertIn(nm, t)
        self.assertNotIn("other-routes", t)

    def test_every_footer_links_info_pages(self):
        n = 0
        for dp, _, files in os.walk(ROOT):
            if "/." in dp or "/scripts" in dp or "/_site" in dp or "/node_modules" in dp:
                continue
            for fn in files:
                if not fn.endswith(".html"):
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), ROOT)
                raw = self.read(rel)
                if "<footer" not in raw:
                    continue
                foot = raw.split("<footer", 1)[1]
                depth = rel.count("/")
                root = "../" * depth
                for slug in self.SLUGS:
                    self.assertIn(f'href="{root}{slug}/"', foot, (rel, slug))
                n += 1
        self.assertGreater(n, 50)


if __name__ == "__main__":
    unittest.main()
