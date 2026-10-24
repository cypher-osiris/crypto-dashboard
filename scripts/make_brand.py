#!/usr/bin/env python3
"""Brand assets from the approved Lumi artwork (Pillow + numpy, ~2 s).

    python3 scripts/make_brand.py     # assets/brand/*-source.* -> logo.png, wordmark, header sky, banner, x_avatar.png + favicons

Sources (approved 2026-10-23, all in assets/brand/):
  icon-source.png               1024 rounded-square app icon (neon "L" + North Star spark on dark navy, transparent corners)
  icon-square-source.png        the same icon full-bleed (no transparent corners), for iOS/Android icons that get masked
  wordmark-source.jpg           "lumi" wordmark on flat navy (3,4,22), 1280x720, spark at (880,267)
  wordmark-milkyway-source.jpg  the wordmark over a Milky Way + mountains photo, 1280x720
Writes:
  assets/brand/logo.png               512 rounded icon (JSON-LD logo, small in-page marks)
  assets/brand/wordmark.png           transparent "lumi" wordmark for the site header (navy keyed out, spark glow kept as soft alpha)
  assets/brand/header-sky.jpg         Milky Way strip (no lettering) behind the header wordmark
  assets/brand/banner.jpg             Milky Way wordmark banner, 1280 wide (home page brand band above the footer)
  assets/brand/x_avatar.png           400x400 square avatar
  assets/favicon-32.png, apple-touch-icon.png (180), icon-192.png, icon-512.png, favicon.ico (repo root)
assets/og.png is the approved static card; scripts/make_og.py leaves it alone unless run with --slate.
"""
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
BRAND = os.path.join(ASSETS, "brand")
ICON = os.path.join(BRAND, "icon-source.png")
ICON_SQ = os.path.join(BRAND, "icon-square-source.png")
WORD = os.path.join(BRAND, "wordmark-source.jpg")
SKY = os.path.join(BRAND, "wordmark-milkyway-source.jpg")
NAVY = np.array([3, 4, 22], np.float32)
WORD_CROP = (362, 150, 1002, 486)   # wordmark + spark glow in the 1280x720 source (text ~382-939 x 215-469)
SKY_CROP = (240, 0, 1280, 168)      # Milky Way band above the lettering (spark glow starts lower)
BANNER_CROP = (0, 120, 1280, 600)   # wordmark, galaxy and the mountain line


def wordmark():
    """RGBA wordmark: color-to-alpha against the flat navy, then un-blend so the glow keeps its color.
    The faint glow is keyed from a blurred copy (kills JPEG block noise); letter edges use the sharp source."""
    from PIL import ImageFilter
    src = Image.open(WORD).convert("RGB")
    x0, y0, x1, y1 = WORD_CROP
    sharp = np.asarray(src).astype(np.float32)[y0:y1, x0:x1]
    soft = np.asarray(src.filter(ImageFilter.GaussianBlur(3))).astype(np.float32)[y0:y1, x0:x1]
    key = lambda a: (np.clip(a - NAVY, 0, None) / (255 - NAVY)).max(axis=2)  # only brighter-than-navy counts
    ks, kb = key(sharp), key(soft)
    m = np.clip((ks - 0.25) / 0.35, 0, 1)[..., None]          # 0 in the glow, 1 on/near the letters and the spark core
    a = sharp * m + soft * (1 - m)
    alpha = ks * m[..., 0] + kb * (1 - m[..., 0])
    alpha = np.clip((alpha - 0.035) / 0.965, 0, 1)             # drop the noise floor / faint vignette
    h, w = alpha.shape
    ry = np.minimum(np.arange(h), np.arange(h)[::-1]) / 24.0
    rx = np.minimum(np.arange(w), np.arange(w)[::-1]) / 40.0
    f = np.clip(np.minimum.outer(ry, rx), 0, 1)
    alpha *= f + (1 - f) * m[..., 0]                           # feather the glow at the crop edges (letters stay solid)
    rgb = NAVY + (a - NAVY) / np.maximum(alpha, 1e-3)[..., None]
    rgb = np.clip(rgb, 0, 255)
    rgb[alpha < 1 / 255] = 0
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")


def build():
    out = []
    def save(im, rel, **kw):
        im.save(os.path.join(ROOT, rel), **kw); out.append(rel)
    icon = Image.open(ICON).convert("RGBA")
    sq = Image.open(ICON_SQ).convert("RGB")
    r = lambda im, px: im.resize((px, px), Image.LANCZOS)
    save(r(icon, 512), "assets/brand/logo.png", optimize=True)
    save(r(sq, 400), "assets/brand/x_avatar.png", optimize=True)
    save(r(icon, 32), "assets/favicon-32.png", optimize=True)
    for name, px in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
        save(r(sq, px), f"assets/{name}", optimize=True)   # full-bleed: iOS/Android apply their own mask
    save(r(icon, 256), "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    # header wordmark: 2x of the largest CSS size (~92x48), plus headroom for 3x phones
    wm = wordmark()
    wm = wm.resize((320, round(320 * wm.height / wm.width)), Image.LANCZOS)
    save(wm, "assets/brand/wordmark.png", optimize=True)
    sky = Image.open(SKY).convert("RGB")
    strip = sky.crop(SKY_CROP)
    save(strip, "assets/brand/header-sky.jpg", quality=72, optimize=True, progressive=True)
    ban = sky.crop(BANNER_CROP)
    save(ban, "assets/brand/banner.jpg", quality=78, optimize=True, progressive=True)
    return out


if __name__ == "__main__":
    print(" ".join(build()))
