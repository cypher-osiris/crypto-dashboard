#!/usr/bin/env python3
"""Brand assets from the generated logo artwork (Pillow + numpy, <1 s).

    python3 scripts/make_brand.py     # assets/brand/logo-source.jpg -> logo.png, x_avatar.png + favicons

Crops the "L" chart-line mark (drops the baked-in wordmark), keys out the dark background into
real alpha (glow kept as soft alpha), then writes:
  assets/brand/logo.png        transparent mark (512x512)
  assets/brand/x_avatar.png    400x400 square avatar on the site's dark bg
  assets/favicon-32.png, apple-touch-icon.png (180), icon-192.png, icon-512.png, favicon.ico (repo root)
"""
import os
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
BRAND = os.path.join(ASSETS, "brand")
SRC = os.path.join(BRAND, "logo-source.jpg")
TILE = (11, 15, 24)  # dark tile for icons/avatar (close to site bg #070a10, a touch lighter so it reads in dark tabs)
CROP = (106, 274, 538, 706)  # square around the mark (+ star glow) in the 1024px source


def mark():
    """RGBA of the cropped mark with the background keyed out."""
    a = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
    bg = np.median(a.reshape(-1, 3), axis=0)
    a[540:, 395:] = bg  # wipe the baked-in "LUMI TRADES" text (starts x~410, y~560)
    x0, y0, x1, y1 = CROP
    a = a[y0:y1, x0:x1]
    d = np.abs(a - bg).max(axis=2)
    alpha = np.clip((d - 6) / 70.0, 0, 1)
    n = alpha.shape[0]; r = np.minimum(np.arange(n), np.arange(n)[::-1]) / 16.0
    alpha *= np.clip(np.minimum.outer(r, r), 0, 1)  # feather the crop edge so the glow never ends in a hard line
    rgb = bg + (a - bg) / np.maximum(alpha, 1e-3)[..., None]  # un-blend from the dark bg
    rgb = np.clip(rgb, 0, 255)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def tile(m, px, pad, radius):
    """Mark centered on a dark (rounded) tile."""
    big = px * 4
    t = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(t).rounded_rectangle([0, 0, big - 1, big - 1], radius=int(radius * big), fill=TILE + (255,))
    inner = int(big * (1 - 2 * pad))
    mm = m.resize((inner, inner), Image.LANCZOS)
    o = (big - inner) // 2
    t.alpha_composite(mm, (o, o))
    return t.resize((px, px), Image.LANCZOS)


def build():
    m = mark()
    m.resize((512, 512), Image.LANCZOS).save(os.path.join(BRAND, "logo.png"), optimize=True)
    tile(m, 400, 0.12, 0).convert("RGB").save(os.path.join(BRAND, "x_avatar.png"), optimize=True)
    tile(m, 32, 0.04, 0.22).save(os.path.join(ASSETS, "favicon-32.png"), optimize=True)
    for name, px in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
        tile(m, px, 0.12, 0).convert("RGB").save(os.path.join(ASSETS, name), optimize=True)  # full-bleed (iOS/Android mask it)
    ico = tile(m, 256, 0.04, 0.22)
    ico.save(os.path.join(ROOT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return ["assets/brand/logo.png", "assets/brand/x_avatar.png", "assets/favicon-32.png", "assets/apple-touch-icon.png",
            "assets/icon-192.png", "assets/icon-512.png", "favicon.ico"]


if __name__ == "__main__":
    print(" ".join(build()))
