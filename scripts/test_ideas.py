#!/usr/bin/env python3
"""data/ideas.json carries only current (pending/open) ideas and never an outcome, P&L or track record."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ideas  # noqa: E402

DOC = {
    "stats": {"win_rate": 50}, "tracked_utc": "2026-10-24T12:00:00Z",
    "slate": {"as_of": "2026-10-24T11:30:00Z", "rules": "r", "coins": {
        "bitcoin": {"trade_id": "T1"}, "ripple": {"trade_id": "T2"}, "solana": {"trade_id": None, "note": "No setup."}}},
    "trades": [
        {"id": "T1", "coin": "bitcoin", "status": "open", "direction": "long", "entry": 1, "stop": 0.9, "targets": [1.1],
         "unrealized_pnl_pct": 3.2, "mark_price": 1.03, "targets_hit": [1.1], "missed_it": {"x": 1}, "reasoning": "Plan."},
        {"id": "T2", "coin": "ripple", "status": "closed", "exit_price": 2, "pnl_pct": -9, "direction": "short"},
        {"id": "T3", "coin": "ethereum", "status": "cancelled", "direction": "short"},
        {"id": "T4", "coin": "axelar", "status": "pending", "direction": "short", "expiry": "2026-10-26T00:00:00Z"},
    ],
}


class IdeasTest(unittest.TestCase):
    def test_only_active_and_no_outcomes(self):
        out = ideas.build(DOC)
        self.assertEqual([i["id"] for i in out["ideas"]], ["T1", "T4"])
        s = json.dumps(out)
        for bad in ("pnl", "mark_price", "targets_hit", "exit_price", "win_rate", "stats", "missed_it", '"closed"'):
            self.assertNotIn(bad, s)
        self.assertEqual(out["slate"]["coins"], {"bitcoin": {"trade_id": "T1"}, "solana": {"trade_id": None, "note": "No setup."}})
        self.assertEqual(out["ideas"][1]["expiry"], "2026-10-26T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
