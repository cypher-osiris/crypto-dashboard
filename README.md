# Crypto Dashboard (paper trading only — not financial advice)

Static site (plain HTML/CSS/JS, no build step) for GitHub Pages. Everything on the page is rendered by
`assets/app.js` from the JSON files in `data/`. Times display in US Central (America/Chicago).

```
index.html            page shell (Chart.js 4 + chartjs-plugin-annotation 3 from jsDelivr CDN)
assets/style.css      dark, mobile-friendly theme
assets/app.js         renders all sections from data/*.json
data/prices.json      GENERATED  – quotes + 30-day ~hourly history (CoinGecko)
data/trades.json      HAND-EDITED ideas + GENERATED status/P&L/stats
data/analysis.json    HAND-EDITED commentary, support/resistance, bull/base/bear projections
data/log.json         update log (script prepends an "auto" entry; analysis runs add "analysis" entries)
scripts/update_prices.py   fetch + evaluate script (Python 3.9+, stdlib only)
```

Coins (CoinGecko IDs, verified 2026-10-21): `hedera-hashgraph` HBAR, `stellar` XLM, `ripple` XRP,
`zebec-network` ZBCN, `axelar` AXL (**not** `axelar-network`), plus `bitcoin` as the backdrop.
To change coins edit `COINS` in the script and add a matching block under `coins` in `analysis.json`.

## Each update (3× a day)

1. `python3 scripts/update_prices.py` – ~15 s (7 API calls, 2.5 s apart, retries/backoff on HTTP 429).
   Optional: `export COINGECKO_DEMO_API_KEY=...` for a free demo key. `--no-fetch` re-evaluates trades on the
   existing `prices.json` without calling the API.
2. Edit `data/analysis.json`: bump `as_of` (ISO UTC) and `author`, update each coin's `commentary`, `bias`,
   `support`/`resistance` (arrays of prices), `projection` (`horizon_days`, `bull`, `base`, `bear`), `sources`
   (`[{title,url}]` – only things actually read).
3. New trade idea: append to `trades` in `data/trades.json` and set `current_idea_id` to its id
   (set it to `null` for "no trade today"). Never edit generated fields of closed trades.
   ```json
   {"id":"T003","coin":"stellar","direction":"long","leverage":5,"entry":0.18,"stop":0.174,
    "targets":[0.19,0.198],"opened_at":"2026-10-22T08:00:00-05:00","status":"open",
    "reasoning":"...","source":"analysis run"}
   ```
   Use `"status":"pending"` (+ optional `"fill_by"` time) for a limit entry that only counts once price trades
   through `entry`; it becomes `cancelled` if unfilled by `fill_by`. Optional `"expires"` closes an open trade at
   market at that time. Timestamps without an offset are read as Central time.
4. Prepend an `{"t": ISO-UTC, "kind":"analysis", "author":"...", "text":"..."}` entry to `data/log.json`.
5. Publish (see below). GitHub Pages serves the new JSON; the page fetches it with cache-busting.

## Trade evaluation rules (script)
Walks the ~hourly price points after `opened_at`/`filled_at` (incrementally via `last_checked_ms`):
size split equally across targets; stop hit before any target → **stopped**; after target 1 fills the stop moves
to entry (`"move_stop_to_be": false` to disable); all targets → **won**; partial targets then stop → **won** if
blended P&L > 0 else **lost**. P&L % = price move × leverage (no fees/funding). Hourly data can miss brief wicks,
so results are approximate. Stats: win rate = won / closed; cumulative P&L = simple sum of closed trades' P&L %.

## Local preview
`python3 -m http.server 8000` in this folder, open http://localhost:8000 (opening index.html via file:// will not
load the JSON).

## Publishing (GitHub Pages)
Live site: https://cypher-osiris.github.io/crypto-dashboard/ · repo: https://github.com/cypher-osiris/crypto-dashboard
(Pages builds from `main`, folder `/`; `.nojekyll` disables Jekyll processing.)

```sh
cd crypto-dashboard
python3 scripts/update_prices.py        # then hand-edit analysis/trades/log as needed
git add -A
git commit -m "Update $(TZ=America/Chicago date '+%Y-%m-%d %H:%M %Z')"
git push                                # non-interactive via gh credential helper (gh auth setup-git)
```
A Pages rebuild usually takes under a minute; check with
`gh api repos/cypher-osiris/crypto-dashboard/pages/builds/latest --jq .status`.
Never commit API keys: pass `COINGECKO_DEMO_API_KEY` via the environment only (`.env*` is git-ignored).
