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


if __name__ == "__main__":
    unittest.main()
