# Lumi Trades: an independent trust service for x402 sellers

Live site: https://lumitrades.io/ · X: [@Lumisinsite](https://x.com/Lumisinsite) · YouTube: [@lumitradesio](https://www.youtube.com/@lumitradesio) · TikTok: [@lumitradesio](https://www.tiktok.com/@lumitradesio).

Lumi test-buys x402 sellers on Base, XRPL and Stellar with its own money and publishes the signed evidence, so people
and AI agents can check who delivers before they pay. Paying Lumi never changes a seller's label. The site is
informational only and is not financial advice.

Since Oct 25, 2026 the site is trust-only: the market pages, trade ideas, coin pages, signals, newsletter form and
referral links were retired. Their old URLs are small `noindex` pages that point to the vendor trust list, and they
are not in the sitemap.

## Pages
```
index.html               homepage (hand-edited English source; /<lang>/index.html is generated from it)
trust/                   vendor trust list (scripts/site_pages.py; live rows from assets/trust.js)
sellers/<slug>/          one page per tested seller (scripts/seller_pages.py)
agents/                  for AI agents: API, prices, paid report (#paid-report), badge embed (assets/badge.js)
how-it-works/            how the testing works (scripts/how_page.py)
trust-policy/            conflicts policy and scoring method (scripts/policy_page.py)
top-sellers/, contact/, privacy/, blog/   (scripts/top_sellers*.py, contact_page.py, privacy_page.py, blog_index.py)
sitemap.xml, feed.xml, llms.txt          written by scripts/build_pages.py (feed: blog posts only)
```

## Build and publish
```sh
python3 scripts/build_pages.py          # every page in every language + sitemap/feed/llms.txt; --paths lists what it wrote
python3 scripts/i18n.py check           # missing translations per language (exit 1 if any)
python3 -m unittest discover -s scripts -p 'test_*.py'
scripts/publish.sh                      # lock (state/lock), pull --rebase, scrub, build, validate JSON, commit if changed, push
```
GitHub Pages builds from `main` (folder `/`, `.nojekyll`). Keep the `CNAME` file. If you change CSS/JS, bump the `?v=`
version in `index.html` (build_pages.py copies it to every generated page).

Rules for public copy: no trade ideas, levels, leverage, signals or P/L; no track record; no referral links; neutral,
apolitical wording; observations, not endorsements or guarantees.

## Badge
"Tested by Lumi" is shown only when it is earned (score 80 or more, at least 3 paid test-buys, latest test-buy delivered),
from the feed's `badge` field or `GET https://api.lumitrades.io/v1/badge/{id}.json` (`earned`). A separate
"Last test-buy" pill shows the result of the most recent paid test-buy. A seller with no score shows "Not scored yet".

## Languages
English at `/`, translations under `/es/ /pt/ /tr/ /ko/ /ja/`. Strings live in `assets/i18n/<lang>.json`, keyed by the
English text. Edit only the English sources; run `python3 scripts/i18n.py check` and add any missing keys.
