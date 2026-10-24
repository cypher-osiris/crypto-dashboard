#!/usr/bin/env python3
"""Submit lumitrades.io URLs to IndexNow (Bing, Yandex, Seznam, Naver, ... share submissions via api.indexnow.org).

  python3 scripts/indexnow_ping.py --commit HEAD     # only sitemap URLs whose files changed in that commit (publish.sh)
  python3 scripts/indexnow_ping.py --all             # every URL in the sitemap (initial / full submission)
  python3 scripts/indexnow_ping.py --all --dry-run   # print what would be sent
  --sitemap-url https://lumitrades.io/sitemap.xml    # read the live sitemap instead of the local sitemap.xml

The key is the public <32 hex>.txt file at the site root (its name equals its content); keyLocation points at it.
One POST per run (urlList capped at 10,000). Never raises: exit 0 on success/skip, 1 on a failed submission.
"""
import argparse, glob, json, os, re, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET

HOST = "lumitrades.io"
BASE = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 10000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def find_key(root=ROOT):
    for p in sorted(glob.glob(os.path.join(root, "*.txt"))):
        name = os.path.basename(p)[:-4]
        if re.fullmatch(r"[0-9a-f]{32}", name):
            with open(p, encoding="utf-8") as f:
                if f.read().strip() == name:
                    return name
    return None


def _read(src, timeout=20):
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "lumitrades-indexnow/1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    with open(src, "rb") as f:
        return f.read()


def sitemap_urls(src, _depth=0):
    """<loc> URLs from a sitemap or sitemap index (sub-sitemaps followed, max depth 2), order kept, deduped."""
    tree = ET.fromstring(_read(src))
    out = []
    if tree.tag == NS + "sitemapindex":
        if _depth < 2:
            for loc in tree.iter(NS + "loc"):
                sub = loc.text.strip()
                if not src.startswith("http") and sub.startswith(BASE + "/"):  # local mode: read the repo copy
                    sub = os.path.join(ROOT, sub[len(BASE) + 1:])
                out += sitemap_urls(sub, _depth + 1)
    else:
        for u in tree.findall(NS + "url"):
            loc = u.find(NS + "loc")
            if loc is not None and loc.text:
                out.append(loc.text.strip())
    seen = set()
    return [u for u in out if u.startswith(BASE + "/") and not (u in seen or seen.add(u))]


def path_to_url(path):
    """Repo file path -> public URL it serves (index.html -> directory URL)."""
    path = path.lstrip("./")
    if path == "index.html":
        return BASE + "/"
    if path.endswith("/index.html"):
        return f"{BASE}/{path[:-len('index.html')]}"
    return f"{BASE}/{path}"


def changed_urls(commit, allowed):
    files = subprocess.run(["git", "-C", ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit],
                           capture_output=True, text=True, check=True).stdout.split()
    allowed_set = set(allowed)
    return [u for u in dict.fromkeys(path_to_url(f) for f in files) if u in allowed_set]


def submit(urls, key, timeout=20):
    body = json.dumps({"host": HOST, "key": key, "keyLocation": f"{BASE}/{key}.txt", "urlList": urls[:MAX_URLS]}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "lumitrades-indexnow/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(500).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(500).decode("utf-8", "replace")


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--commit", help="submit only sitemap URLs whose files changed in this commit")
    g.add_argument("--all", action="store_true", help="submit every sitemap URL")
    ap.add_argument("--sitemap-url", default=None, help="sitemap URL (default: local sitemap.xml)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        key = find_key()
        if not key:
            print("indexnow: no key file at site root; skipping"); return 0
        allowed = sitemap_urls(a.sitemap_url or os.path.join(ROOT, "sitemap.xml"))
        urls = allowed if a.all else changed_urls(a.commit, allowed)
        if not urls:
            print("indexnow: no changed sitemap URLs; skipping"); return 0
        if len(urls) > MAX_URLS:
            print(f"indexnow: {len(urls)} URLs, sending first {MAX_URLS}")
            urls = urls[:MAX_URLS]
        if a.dry_run:
            print(f"indexnow: dry run, {len(urls)} URLs"); print("\n".join(urls)); return 0
        status, text = submit(urls, key)
        ok = status in (200, 202)
        print(f"indexnow: HTTP {status} for {len(urls)} URLs" + ("" if ok else f" — {text.strip()[:200]}"))
        return 0 if ok else 1
    except Exception as e:  # never break the caller
        print(f"indexnow: error {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
