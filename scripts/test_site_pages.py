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
        self.assertEqual((c["lo"], c["hi"]), ("$0.003", "$0.25"))
        txt = sp.AGENTS_ROUTES_TEXT.format(**c)
        self.assertIn(f"{len(sp.MARKET_PRICES)} paid market routes", txt)
        self.assertNotIn("17 paid routes", txt)

    def test_homepage_count_matches_tables(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            h = f.read()
        c = sp.route_counts()
        self.assertIn(f'{c["m"]} market + {c["t"]} trust paid routes', h)
        self.assertNotIn("17 paid routes", h)

    def test_trial_text_is_base_only(self):
        self.assertIn("new Base wallets", sp.AGENTS_ROUTES_TEXT)
        self.assertIn("0.01 USDC", sp.AGENTS_ROUTES_TEXT)
        self.assertIn("XRPL-only wallets get no trial", sp.AGENTS_ROUTES_TEXT)

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


if __name__ == "__main__":
    unittest.main()
