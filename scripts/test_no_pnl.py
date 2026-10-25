"""Standing rule: the paper-trade track record and P&L stay private. Trade pages were retired on Oct 25, 2026; no page,
in any language, may render a P&L, return or win/loss figure, and the feed carries blog posts only."""
import glob, os, re, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoPnl(unittest.TestCase):
    def test_free_text_drops_pnl_label(self):
        self.assertEqual(i18n.no_pnl("About 2.7 blended. P&L is at 1x: T1 +8.8%."), "About 2.7 blended. Move is at 1x: T1 +8.8%.")
        self.assertEqual(i18n.no_pnl("the unrealized P&L was"), "the move was")
        self.assertEqual(i18n.no_pnl("no label here"), "no label here")

    def test_generators_have_no_pnl_strings(self):
        for f in ("scripts/build_pages.py", "scripts/site_pages.py", "scripts/site_chrome.py", "scripts/how_page.py", "assets/trust.js"):
            src = open(os.path.join(ROOT, f), encoding="utf-8").read()
            self.assertNotRegex(src, r'_t?\("[^"]*P&(amp;)?L|unrealized_pnl_pct|pnl_pct|win_rate|P&amp;L \$\{', f)

    def test_trade_generators_are_gone(self):
        for f in ("scripts/trade_pages.py", "scripts/ideas.py", "assets/dash.js", "assets/affiliate.js"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, f)), f)

    def test_feed_has_no_outcomes(self):
        import feed
        x = feed.atom(ROOT)
        self.assertNotRegex(x, r"(?i)\bT0\d\d\b|filled|win rate|stopped|pnl|P&amp;L|leverage")

    def test_built_pages_have_no_pnl(self):
        for p in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True):
            if "/node_modules/" in p or "/.git/" in p:
                continue
            src = open(p, encoding="utf-8").read()
            self.assertNotRegex(src, r"P&amp;L|unrealized_pnl|win rate|Win rate|track record", p)


if __name__ == "__main__":
    unittest.main()
