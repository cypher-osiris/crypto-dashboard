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


class SitePages(unittest.TestCase):
    def test_route_counts_from_tables(self):
        c = sp.route_counts()
        self.assertEqual(c["m"], len(sp.MARKET_PRICES))
        self.assertEqual(c["t"], 2)
        self.assertEqual((c["lo"], c["hi"]), ("$0.003", "$0.10"))
        txt = sp.AGENTS_ROUTES_TEXT.format(**c)
        self.assertIn(f"{len(sp.MARKET_PRICES)} paid market routes", txt)
        self.assertNotIn("17 paid routes", txt)

    def test_homepage_count_matches_tables(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            h = f.read()
        c = sp.route_counts()
        self.assertIn(f'{c["m"]} market + {c["t"]} trust paid routes', h)
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

    def test_no_projection_wording_for_levels(self):
        lv = [p for p in sp.MARKET_PRICES if p[1] == "GET /v1/levels/{coin}"][0][0]
        self.assertIn("scenario levels", lv)
        self.assertNotIn("projection", lv)

    def test_a2a_link_points_to_agent_card(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_pages.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn('API + "/a2a"', src)
        self.assertIn('API + "/.well-known/agent-card.json"', src)

    def test_translations_exist_with_placeholders(self):
        keys = [sp.AGENTS_ROUTES_TEXT, [p for p in sp.MARKET_PRICES if p[1] == "GET /v1/levels/{coin}"][0][0], "A2A agent card"]
        for lang in LANGS:
            d = i18n(lang)
            for k in keys:
                self.assertTrue(d.get(k), (lang, k[:40]))
            for ph in ("{m}", "{t}", "{lo}", "{hi}"):
                self.assertIn(ph, d[sp.AGENTS_ROUTES_TEXT], (lang, ph))



class CoinPageWording(unittest.TestCase):
    """Audit 2026-10-23b L-13: coin pages show scenario levels as an outlook, never a projection or price prediction."""
    SLUGS = ["xdc", "xrp", "xlm", "hbar", "axl", "zbcn", "btc", "eth", "sol"]
    BANNED = re.compile(r"projection|(?<!not a )price prediction", re.I)

    def test_generator_has_no_prediction_wording(self):
        with open(os.path.join(ROOT, "scripts", "build_pages.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("Price Prediction", src)
        self.assertNotIn("price prediction?", src)
        self.assertNotIn("-day projection", src)
        self.assertIn("{n}-day outlook (scenario levels)", src)

    def test_built_coin_pages_all_languages(self):
        for lang in [""] + [l + "/" for l in LANGS]:
            for slug in self.SLUGS:
                p = os.path.join(ROOT, lang, slug, "index.html")
                if not os.path.exists(p):
                    continue
                with open(p, encoding="utf-8") as f:
                    h = f.read()
                if not lang:
                    m = self.BANNED.search(h)
                    self.assertIsNone(m, (slug, m and m.group(0)))
                    if "cp-proj" in h:
                        self.assertIn("-day outlook (scenario levels)", h, slug)
                elif "cp-proj" in h:
                    head = i18n(lang[:-1])["{n}-day outlook (scenario levels)"]
                    for part in filter(None, (x.strip() for x in head.split("{n}"))):
                        self.assertIn(part, h, (lang, slug, part))

    def test_outlook_translations_exist(self):
        keys = ["{n}-day outlook (scenario levels)", "What is Lumi's {n}-day outlook for {sym}?",
                "{sym} Price Analysis Today & {name} Outlook | Lumi Trades", "{sym} Price Analysis Today & Outlook | Lumi Trades"]
        old = ["Lumi's {n}-day projection", "What is Lumi's {sym} price prediction?",
               "{sym} Price Analysis Today & {name} Price Prediction | Lumi Trades"]
        for lang in LANGS:
            d = i18n(lang)
            for k in keys:
                self.assertTrue(d.get(k), (lang, k))
                for ph in re.findall(r"\{\w+\}", k):
                    self.assertIn(ph, d[k], (lang, k, ph))
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
                    if '"sameAs": ["https://x.com/lumisinsite"' in src and f'"{self.TT}"' not in src:
                        missing.append(os.path.relpath(p, ROOT) + " (sameAs)")
        self.assertEqual(missing, [])

    def test_footers_all_languages(self):
        for pre in [""] + [l + "/" for l in LANGS]:
            for page in ("index.html", "xrp/index.html", "how-it-works/index.html", "trades/index.html", "trust/index.html"):
                with open(os.path.join(ROOT, pre + page), encoding="utf-8") as f:
                    self.assertIn(self.A, f.read(), pre + page)


class OrgAltName(unittest.TestCase):
    """Organization JSON-LD carries the YouTube channel name as alternateName and TikTok in sameAs, on every page that has it."""
    def test_generator(self):
        import seo
        org = seo.organization(lambda x: x)
        self.assertEqual(org["alternateName"], "Trade with Lumi")
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
                            if node.get("alternateName") != "Trade with Lumi" or "https://www.tiktok.com/@lumitradesio" not in node.get("sameAs", []):
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
            for s in ("hello@lumitrades.io", "lumi@lumitrades.io", "admin@lumitrades.io", "receive-only", '"@type": "ContactPage"',
                      "security.txt", "https://x.com/lumisinsite", "https://github.com/lumitrades", "lumi-check", "trust/#reply",
                      cp.NOT_AFFILIATED):
                self.assertIn(s, h, (lang, s))
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
        for rel in ("index.html", "privacy/index.html", "trust/index.html", "es/trust/index.html", "blog/index.html", "xrp/index.html"):
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
            self.assertNotIn("bitunix", h.lower())
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


class NoBitunixInStaticHtml(unittest.TestCase):
    """Bitunix doesn't serve US users: the static HTML (served to everyone) never names it; affiliate.js adds it for non-US visitors."""
    SLUGS = CoinPageWording.SLUGS

    def test_scrubber(self):
        from i18n import no_us_hidden_names as f
        self.assertEqual(f("venues (Bitunix, Binance, OKX) list no perp"), "venues (Binance, OKX) list no perp")
        self.assertEqual(f("on Kraken or Bitunix."), "on Kraken.")
        self.assertEqual(f("Bitunix lists it"), "a supported exchange lists it")
        self.assertEqual(f("no exchange here"), "no exchange here")

    def test_coin_and_trade_pages(self):
        for lang in [""] + [l + "/" for l in LANGS]:
            paths = [os.path.join(ROOT, lang, s, "index.html") for s in self.SLUGS]
            tdir = os.path.join(ROOT, lang, "trades")
            if os.path.isdir(tdir):
                paths += [os.path.join(tdir, d, "index.html") for d in os.listdir(tdir) if os.path.isfile(os.path.join(tdir, d, "index.html"))]
            for path in paths:
                with open(path, encoding="utf-8") as f:
                    self.assertNotIn("bitunix", f.read().lower(), path)

    def test_generic_exchange_translated(self):
        keys = ["Other international exchanges that list {sym}",
                "Outside the US, Kraken lists {sym} in many countries, and other international exchanges list it too. Availability depends on your country; check the exchange's supported-regions page.",
                "Outside the US, many international exchanges list {sym}. Availability depends on your country; check the exchange's supported-regions page."]
        for lang in LANGS:
            for k in keys:
                self.assertIn(k, i18n(lang), (lang, k))
                self.assertNotIn("bitunix", i18n(lang)[k].lower())


class TrustBadge(unittest.TestCase):
    """/trust/ "Tested by Lumi" badge: only from a real paid test-buy, never invented, same in all 6 languages."""
    class H:
        E = staticmethod(lambda s: __import__("html").escape(str(s)))
        _ = staticmethod(lambda s, **kw: s.format(**kw) if kw else s)

    def test_delivered(self):
        v = {"last_paid_observation": {"observed_at": "2026-10-24T09:21:21.000Z", "network": "xrpl:0", "delivery": "delivered", "data_returned": True}}
        b = sp.badge_html(self.H, v)
        self.assertIn("b-delivered", b)
        self.assertIn(">Tested by Lumi<", b)
        self.assertIn(">delivered · 10-24-2026 · XRPL<", b)

    def test_no_delivery_and_chains(self):
        for net, ch in (("eip155:8453", "Base"), ("stellar:pubnet", "Stellar")):
            v = {"last_paid_observation": {"observed_at": "2026-10-23T04:12:22Z", "network": net, "delivery": "not_delivered", "data_returned": False}}
            b = sp.badge_html(self.H, v)
            self.assertIn("b-no_delivery", b)
            self.assertIn(f">no delivery · 10-23-2026 · {ch}<", b)

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
        keys = [sp.BADGE_NOTE, sp.BADGE_KEY, sp.BADGE_TIP_END, "Tested by Lumi", *sp.BADGE_TIP.values(), *sp.BADGE_RES.values()]
        for lang in LANGS:
            pages = i18n(lang)
            for k in keys:
                self.assertIn(k, pages, f"{lang}: {k}")
            self.assertEqual(pages["Tested by Lumi"], "Tested by Lumi")
            self.assertIn("Tested by Lumi", pages[sp.BADGE_NOTE])

class PaymentAttemptsLabel(unittest.TestCase):
    """Opt-in grey 'Test payment not accepted yet' label: only listed vendors, only with zero paid buys, neutral wording."""
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
            self.assertNotRegex(on.lower(), r"scam|fraud|" + os.environ.get("LUMI_PRIVATE_NAME_RE", "owner-name-redacted"))
        finally:
            sp.att_snapshot = old

    def test_snapshot_file_is_opt_in_list(self):
        with open(sp.ATT_SNAPSHOT, encoding="utf-8") as f:
            d = json.load(f)["vendors"]
        self.assertEqual(sorted(d), ["edge-agents"])


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
        self.assertNotRegex(txt.lower(), r"p&l|profit|return")

    def test_caps_match_runners_when_present(self):
        import re as _re
        cb, tb = os.path.join(os.path.dirname(ROOT), "tools", "catalog_buys.ts"), os.path.join(os.path.dirname(ROOT), "tools", "trust_testbuys.ts")
        if not (os.path.exists(cb) and os.path.exists(tb)):
            self.skipTest("runners not on this machine")
        cbs, tbs = open(cb).read(), open(tb).read()
        self.assertIn("const DAILY_CAP = 750_000n", cbs)
        self.assertIn("const STALE_DAYS = 30", cbs)
        self.assertIn("const DAILY_CAP = { RLUSD: 0.30, XRP: 0.10 }", tbs)
        self.assertIn("const STELLAR_CAP = 0.15", tbs)
        self.assertIn("const STELLAR_MAX_BUYS = 4", tbs)
        self.assertIn("const MAX_PRICE = 0.05", tbs)

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
            self.assertIn("mailto:hello@lumitrades.io", h)
            self.assertNotIn("{mail}", h)


if __name__ == "__main__":
    unittest.main()
