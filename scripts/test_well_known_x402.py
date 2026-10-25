import importlib.util, os
spec = importlib.util.spec_from_file_location("c", os.path.join(os.path.dirname(__file__), "check_well_known_x402.py"))
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


def test_pointer_valid():
    feat = c.check(c.load())
    prices = {f["url"].rsplit("/v1/", 1)[1]: f["price_usd"] for f in feat}
    assert prices == {"trust/check": "0.02", "verdict": "0.01"}  # Oct 25, 2026: no trading-signal routes featured
