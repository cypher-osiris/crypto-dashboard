#!/usr/bin/env python3
"""Trade ideas were retired on Oct 25, 2026: data/ideas.json stays (the API reads it) but is empty and neutral."""
import json
import re  # noqa: F401
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class IdeasRetiredTest(unittest.TestCase):
    def test_ideas_json_is_empty_and_neutral(self):
        d = json.load(open(os.path.join(ROOT, "data", "ideas.json"), encoding="utf-8"))
        self.assertEqual(d.get("ideas"), [])
        self.assertEqual((d.get("slate") or {}).get("coins"), {})
        s = json.dumps(d)
        self.assertNotRegex(s, r"(?i)pnl|win_rate|leverage|\bstops?\b|\btargets?\b|\bentry\b|\blong\b|\bshort\b|bit[u]nix")

    def test_generator_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "scripts", "ideas.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "scripts", "trade_pages.py")))


if __name__ == "__main__":
    unittest.main()
