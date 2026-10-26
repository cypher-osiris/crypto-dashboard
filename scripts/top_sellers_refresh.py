#!/usr/bin/env python3
"""Refresh the data behind /top-sellers/ (read-only).

1. Collect every seller key Lumi has test-bought, from the box-side runner logs (read only, never written):
   - curated XRPL vendor ids  (lumi-api/src/vendors.ts)
   - Base hosts               (notes/vendor_research/base_buys/log.jsonl, "bought" events: tools/catalog_buys.ts)
   - XRPL Bazaar hosts        (notes/xrpl_testbuys_*.json bazaar_coverage)
   - Stellar hosts            (notes/trust_testbuys.log stellar plans + notes/stellar_testbuys_state.json)
2. For each key, GET the public, edge-cached badge JSON https://api.lumitrades.io/v1/badge/<key>.json. It holds the same
   stored results as https://api.lumitrades.io/trust/v/<key> (newest first, at most 10 tests). No auth, no writes.
3. Attach the seller's public catalog description (CDP x402 Bazaar "desc" from candidates_latest.json, or the curated
   vendor name) so top_sellers_page.py can sort sellers into categories.
Writes scripts/top_sellers_snapshot.json. Then run build_pages.py to rebuild the page from the snapshot.

Usage: python3 scripts/top_sellers_refresh.py [--box <workspace dir>] [--workers 4]
"""
import argparse, concurrent.futures as cf, datetime, glob, json, os, re, sys, time, urllib.parse, urllib.request

API = "https://api.lumitrades.io"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "top_sellers_snapshot.json")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}$")


def jl(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                pass


def host(u):
    try:
        return (urllib.parse.urlparse(u).hostname or "").lower()
    except ValueError:
        return ""


def collect(box):
    keys, desc = {}, {}  # key -> source set ; key -> description
    def add(k, src):
        k = (k or "").strip().lower()
        if k and k != "api.lumitrades.io" and (HOST_RE.match(k) or re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", k)):
            keys.setdefault(k, set()).add(src)
    vt = os.path.join(box, "lumi-api/src/vendors.ts")
    vendors = {}
    if os.path.exists(vt):
        src = open(vt, encoding="utf-8").read()
        for m in re.finditer(r'id:\s*"([^"]+)",\s*name:\s*"([^"]+)",\s*homepage:\s*"([^"]+)"', src):
            vendors[m.group(1)] = (m.group(2), host(m.group(3)))
            add(m.group(1), "xrpl-curated")
            desc[m.group(1)] = m.group(2)
    for r in jl(os.path.join(box, "notes/vendor_research/base_buys/log.jsonl")):
        if r.get("event") == "bought" and r.get("resource"):
            add(host(r["resource"]), "base")
    for p in sorted(glob.glob(os.path.join(box, "notes/xrpl_testbuys_*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except ValueError:
            continue
        for e in d.get("bazaar_coverage", []):
            add(e.get("host"), "xrpl-bazaar")
    for r in jl(os.path.join(box, "notes/trust_testbuys.log")):
        if r.get("chain") == "stellar" and r.get("vendor"):
            add(r["vendor"], "stellar")
    try:
        for k in json.load(open(os.path.join(box, "notes/stellar_testbuys_state.json"))).get("last", {}):
            add(k, "stellar")
    except (OSError, ValueError):
        pass
    # catalog descriptions (CDP x402 Bazaar), per exact host; keep the most-called resource's text
    best, by_res0 = {}, {}
    for p in [os.path.join(box, "notes/vendor_research/base_buys/candidates_latest.json")]:
        try:
            rows = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            rows = []
        for r in rows:
            h, d = host(r.get("resource", "")), (r.get("desc") or "").strip()
            if h and d:
                by_res0.setdefault(r.get("resource", "").split("?")[0], d)
            if h and d and r.get("calls", 0) >= best.get(h, (-1,))[0]:
                best[h] = (r.get("calls", 0), d, r.get("resource"))
    for h, (_c, d, _r) in best.items():
        desc.setdefault(h, d)
    # full CDP x402 Bazaar discovery snapshots (all networks): exact resource first, then host
    by_res = dict(by_res0)
    for p in sorted(glob.glob(os.path.join(box, "notes/research/bazaar_*/p*.json")) + glob.glob(os.path.join(box, "notes/vendor_research/catalog*/p*.json"))):
        try:
            items = json.load(open(p, encoding="utf-8")).get("items", [])
        except (OSError, ValueError, AttributeError):
            continue
        for it in items:
            r, d = it.get("resource", ""), (it.get("description") or "").strip()
            if r and d:
                by_res.setdefault(r.split("?")[0], d)
                desc.setdefault(host(r), d)
    return keys, desc, vendors, by_res


def fetch(key, tries=3):
    url = f"{API}/v1/badge/{urllib.parse.quote(key, safe='')}.json"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lumitrades-site-build/1 (+https://lumitrades.io/top-sellers/)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                return {"error": str(e)[:200]}
            time.sleep(1.5 * (i + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.environ.get("LUMI_BOX_DIR", "."))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    keys, desc, vendors, by_res = collect(a.box)
    print(f"{len(keys)} keys", file=sys.stderr)
    out, seen = [], set()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for k, b in zip(keys, ex.map(fetch, list(keys))):
            if "error" in b:
                print("ERR", k, b["error"], file=sys.stderr)
                continue
            if b.get("kind") != "lumi_badge" or b.get("verdict") == "not_tested":
                continue
            canon = b.get("vendor_id") or b.get("key") or k
            if canon in seen:
                continue
            seen.add(canon)
            tests = [{"at": t["at"], "chain": t.get("chain"), "verdict": t["verdict"], "endpoint": t.get("endpoint")} for t in b.get("tests", [])]
            ep = (tests[0]["endpoint"] or "") if tests else ""
            eh = host(ep)
            d = by_res.get(ep.split("?")[0]) or (vendors[canon][0] if canon in vendors else "") or desc.get(eh) or ""
            out.append({"key": canon, "name": b.get("name") or canon, "desc": d[:300], "tests": tests})
    out.sort(key=lambda r: r["key"])
    snap = {"generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"{API}/v1/badge/<key>.json (same stored results as {API}/trust/v/<key>)", "sellers": out}
    with open(OUT, "w", encoding="utf-8") as f:  # one seller per line: small, readable diffs
        f.write('{"generated_at": %s,\n "source": %s,\n "sellers": [\n' % (json.dumps(snap["generated_at"]), json.dumps(snap["source"])))
        f.write(",\n".join("  " + json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in out))
        f.write("\n ]}\n")
    print(f"wrote {OUT}: {len(out)} tested sellers", file=sys.stderr)


if __name__ == "__main__":
    main()
