"""Standing rule: the paper-trade track record and P&L stay private. No page, in any language, may render a P&L,
return or win/loss figure, even when data/trades.json still carries one (e.g. unrealized_pnl_pct on an open idea)."""
import os, re, sys, types, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n, trade_pages  # noqa: E402


class NoPnl(unittest.TestCase):
    def h(self):
        return types.SimpleNamespace(_=lambda s, **kw: s.format(**kw) if kw else s, pct_txt=lambda v, d=1: f"{v:+.{d}f}%",
                                     ctime=lambda *a, **k: "Oct 23")

    def test_result_txt_never_has_a_figure(self):
        h = self.h()
        for t in ({"status": "open", "unrealized_pnl_pct": -1.68, "last_checked": "x"}, {"status": "won", "pnl_pct": 12.3},
                  {"status": "closed", "pnl_pct": -4.0}, {"status": "pending"}, {"status": "cancelled"}):
            val, note = trade_pages.result_txt(t, h)
            self.assertNotRegex(val + note, r"\d|P&L")

    def test_outcome_hides_win_loss(self):
        for s in ("won", "target", "lost", "stopped", "closed"):
            self.assertEqual(trade_pages.outcome({"status": s, "pnl_pct": 5}), ("void", "Closed"))

    def test_free_text_drops_pnl_label(self):
        self.assertEqual(i18n.no_pnl("About 2.7 blended. P&L is at 1x: T1 +8.8%."), "About 2.7 blended. Move is at 1x: T1 +8.8%.")
        self.assertEqual(i18n.no_pnl("the unrealized P&L was"), "the move was")
        self.assertEqual(i18n.no_pnl("no label here"), "no label here")

    def test_generators_have_no_pnl_strings(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for f in ("scripts/trade_pages.py", "scripts/build_pages.py", "assets/dash.js"):
            src = open(os.path.join(root, f), encoding="utf-8").read()
            self.assertNotRegex(src, r'_t?\("[^"]*P&(amp;)?L|unrealized_pnl_pct\)?\s*(\)|,)\s*\}?\s*$|P&amp;L \$\{', f)


if __name__ == "__main__":
    unittest.main()
