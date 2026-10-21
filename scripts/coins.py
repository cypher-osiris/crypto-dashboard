"""Loads data/coins.json — the single coin list shared by every script and the site."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "coins.json")


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
