#!/usr/bin/env python3
"""Social preview + icons for the site (run after each slate update; ~1 s).

    python3 scripts/make_og.py            # no-op for og.png: assets/og.png is the approved static brand card (2026-10-23)
    python3 scripts/make_og.py --icons    # rebuild logo.png, wordmark, header sky, banner, favicons, x_avatar.png (scripts/make_brand.py)
    python3 scripts/make_og.py --slate    # legacy: overwrite assets/og.png with the 1200x630 card drawn from the current slate

Uses the same data/fonts as scripts/make_post.py. Needs matplotlib (+ fontTools for bold weights) and Pillow.
The card's logo mark is assets/brand/logo.png (transparent "L" chart-line mark).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_post as mp  # noqa: E402

ASSETS = os.path.join(mp.ROOT, "assets")
CYAN, BLUE = "#22d3ee", "#60a5fa"
LOGO = os.path.join(ASSETS, "brand", "logo.png")  # same mark as the site header


def og(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
    sans, mono = mp.font_setup(fm)
    F = mp.gather()
    W, H = 1200, 630
    fig = plt.figure(figsize=(12, 6.3), dpi=100, facecolor=mp.BG)
    g = fig.add_axes([0, 0, 1, 1]); g.axis("off"); g.set_xlim(0, W); g.set_ylim(H, 0)
    yy, xx = np.mgrid[0:1:150j, 0:1:260j]
    glow = np.exp(-((xx - 0.08) ** 2 / 0.12 + yy ** 2 / 0.2)) * 0.55 + np.exp(-((xx - 1) ** 2 / 0.08 + (yy - 1) ** 2 / 0.12)) * 0.25
    g.imshow(glow, extent=(0, W, H, 0), cmap=matplotlib.colors.LinearSegmentedColormap.from_list("g", [mp.BG, "#0f2a3d"]), aspect="auto")
    T = lambda x, y, s, **k: g.text(x, y, s, **{"color": mp.TXT, "family": sans, "va": "center", **k})
    # logo mark + brand
    if os.path.exists(LOGO):
        from PIL import Image
        g.imshow(np.asarray(Image.open(LOGO).convert("RGBA").resize((192, 192), Image.LANCZOS)), extent=(56, 140, 126, 42), zorder=3)
    T(150, 84, "Lumi Trades", fontsize=40, weight="bold")
    T(64, 168, "x402 seller trust from real paid test-buys", fontsize=24, color=mp.MUTED)
    T(64, 204, "Live prices · signals · daily trade slate · pay-per-call API for AI agents", fontsize=16, color=mp.DIM)
    # slate rows (max 3), compact
    rows = F["slate"][:3]
    T(64, 268, "TODAY'S SLATE" if rows else "TODAY", fontsize=13, weight="bold", color=CYAN)
    y = 316
    if not rows:
        T(64, y, "No setups right now. Waiting for prices worth trading.", fontsize=24, color=mp.MUTED)
    for r in rows:
        long_ = r["side"] == "long"; col = mp.GREEN if long_ else mp.RED
        T(64, y, r["sym"], fontsize=30, weight="bold")
        g.add_patch(FancyBboxPatch((210, y - 16), 86, 32, boxstyle="round,pad=0,rounding_size=16", fc=col + "26", ec=col, lw=1.2))
        T(253, y, "LONG" if long_ else "SHORT", fontsize=12, weight="bold", color=col, ha="center")
        lo, hi = r["zone"]
        T(326, y, (f"{mp.pfmt(lo)}–{mp.lvl(hi)}" if lo != hi else mp.pfmt(lo)) if r["status"] == "pending" else f"in at {mp.pfmt(r.get('entry'))}", fontsize=24, family=mono)
        T(W - 64, y, r.get("vs_zone") or r["status"], fontsize=15, color=mp.MUTED, ha="right")
        y += 66
    T(64, H - 56, "Paper trades · not financial advice", fontsize=14, color=mp.AMBER)
    T(W - 64, H - 56, "lumitrades.io  ·  @lumisinsite", fontsize=14, color=mp.DIM, ha="right")
    fig.savefig(path, dpi=100, facecolor=mp.BG)
    plt.close(fig)


def icons():
    import make_brand
    return make_brand.build()


if __name__ == "__main__":
    out = icons() if "--icons" in sys.argv else []
    if "--slate" in sys.argv:  # the brand card is static now; only redraw the slate card when asked
        og(os.path.join(ASSETS, "og.png"))
        out = ["assets/og.png"] + out
    print(" ".join(out))
