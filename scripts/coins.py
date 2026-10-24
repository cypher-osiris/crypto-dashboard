"""Loads data/coins.json — the single coin list shared by every script and the site."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "coins.json")
# Paper-trade ideas are NOT published since Oct 24, 2026 (lumitrades.io/data/trades.json was taken down): the working
# trades doc (the old public view, hand-editable) is state/trades.json and the full doc state/trades_full.json, both
# git-ignored. data/trades.json is git-ignored too and scripts/publish.sh never stages it.
TRADES = os.path.join(ROOT, "state", "trades.json")
LEGACY_TRADES = os.path.join(ROOT, "data", "trades.json")


def trades_path():
    """Path of the private trades doc. A data/trades.json left by an old checkout or an old hand-edit habit is adopted
    (when newer than state/trades.json) and moved out of data/ to state/trades.legacy.json, so it never lingers there."""
    if os.path.exists(LEGACY_TRADES):
        import shutil
        os.makedirs(os.path.dirname(TRADES), exist_ok=True)
        if not os.path.exists(TRADES) or os.path.getmtime(LEGACY_TRADES) > os.path.getmtime(TRADES):
            shutil.copyfile(LEGACY_TRADES, TRADES)
        os.replace(LEGACY_TRADES, os.path.join(os.path.dirname(TRADES), "trades.legacy.json"))
    return TRADES


def load_trades(default=None):
    """The private trades doc (state/trades.json), or default ({"trades": []}) when there is none."""
    p = trades_path()
    if not os.path.exists(p):
        return {"trades": []} if default is None else default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def config():
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def coins():
    """List of coin dicts in display order (groups in config order, coins in file order within a group)."""
    cfg = config()
    order = {g["id"]: i for i, g in enumerate(cfg.get("groups", []))}
    return sorted(cfg["coins"], key=lambda c: order.get(c.get("group"), 99))


def source(c):
    """(source, product) for candles: coinbase preferred, else kraken REST pair, else coingecko."""
    if c.get("coinbase"):
        return "coinbase", c["coinbase"]
    if c.get("kraken"):
        return "kraken", c["kraken"].replace("/", "")
    return "coingecko", c["id"]


def by_id():
    return {c["id"]: c for c in coins()}


def backdrop():
    return config().get("backdrop", "bitcoin")


def slate_max():
    return int(config().get("slate_max", 6))
