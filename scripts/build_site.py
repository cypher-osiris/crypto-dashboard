#!/usr/bin/env python3
"""Copy only the public site into _site/ (git-ignored) for GitHub Pages (security finding M1).

The repo also holds build scripts, docs, caches and tests; none of them is published. Pages serves _site/ only,
via .github/workflows/pages.yml (Pages source: "GitHub Actions"). Anything not on the allowlist below stays out.
  python3 scripts/build_site.py            # rebuild _site/ from the checked-in pages
  python3 scripts/build_site.py --check    # also fail if a non-public file type slipped into _site/
"""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_site")
LANGS = ("es", "pt", "ja", "ko", "tr")
ROOT_FILES = (".nojekyll", "CNAME", "BingSiteAuth.xml", "a65be5c5e8044d1d7844e6c68287e837.txt", "favicon.ico",
              "feed.xml", "index.html", "llms.txt", "robots.txt", "site.webmanifest", "sitemap.xml")
WELL_KNOWN = ("security.txt", "x402", "x402.json", "trustline-merchant.txt", "xrp-ledger.toml")
PAGE_DIRS = ("about", "agents", "blog", "contact", "how-it-works", "preview", "prices", "pricing", "privacy", "sellers", "terms",
             "top-sellers", "trust", "trust-policy")
SHARED_DIRS = ("assets",)
PUBLIC_EXT = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".mp4",
              ".webm", ".woff", ".woff2", ".txt", ".xml", ".webmanifest", ".vtt"}
NEVER = ("__pycache__", ".py", ".md", ".sh", ".log", ".env")


def _ok(name):
    if name.startswith(".") or any(name.endswith(x) or name == x for x in NEVER):
        return False
    return os.path.splitext(name)[1].lower() in PUBLIC_EXT


def _copy_tree(src, dst):
    for d, subs, files in os.walk(src):
        subs[:] = [s for s in subs if not s.startswith(".") and s != "__pycache__"]
        for f in files:
            if _ok(f):
                rel = os.path.relpath(os.path.join(d, f), src)
                os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
                shutil.copy2(os.path.join(d, f), os.path.join(dst, rel))


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, ".well-known"))
    for f in ROOT_FILES:
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), os.path.join(OUT, f))
    for f in WELL_KNOWN:
        p = os.path.join(ROOT, ".well-known", f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(OUT, ".well-known", f))
    for d in SHARED_DIRS + PAGE_DIRS:
        if os.path.isdir(os.path.join(ROOT, d)):
            _copy_tree(os.path.join(ROOT, d), os.path.join(OUT, d))
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        if os.path.exists(os.path.join(base, "index.html")):
            os.makedirs(os.path.join(OUT, lang), exist_ok=True)
            shutil.copy2(os.path.join(base, "index.html"), os.path.join(OUT, lang, "index.html"))
        for d in PAGE_DIRS:
            if os.path.isdir(os.path.join(base, d)):
                _copy_tree(os.path.join(base, d), os.path.join(OUT, lang, d))


def check():
    bad = []
    for d, _, files in os.walk(OUT):
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), OUT)
            if rel.startswith(".well-known" + os.sep) or rel in ROOT_FILES:
                continue
            if not _ok(f):
                bad.append(rel)
    return bad


if __name__ == "__main__":
    build()
    n = sum(len(f) for _, _, f in os.walk(OUT))
    print(f"_site/: {n} files")
    if "--check" in sys.argv:
        bad = check()
        if bad:
            print("non-public files in _site/:", *bad, sep="\n  ")
            sys.exit(1)
