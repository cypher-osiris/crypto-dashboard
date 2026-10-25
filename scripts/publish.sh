#!/usr/bin/env bash
# Publish data updates to GitHub Pages without prompts.
#   scripts/publish.sh                    # stage everything under data/
#   scripts/publish.sh data/log.json data/signals.json   # stage only these paths
# data/trades.json is never published (taken down Oct 24, 2026; the trades doc is private in state/): it is dropped
# from the paths and kept out of every commit.
#   PUBLISH_MSG="custom message" scripts/publish.sh
# Steps (git pull/push bounded by GIT_NET_TIMEOUT, default 120 s): take state/lock -> git pull --rebase --autostash -> (data paths: scripts/privacy.py, scripts/build_pages.py) -> validate JSON -> git add -> commit only if changed -> push
#   -> data/ideas.json refresh (scripts/ideas.py, every publish) -> IndexNow ping (scripts/indexnow_ping.py: one POST with the sitemap URLs whose files changed in the pushed commit; INDEXNOW=0 skips; a failed ping never fails the publish).
# Exit codes: 0 ok / nothing to publish, 2 invalid JSON, 3 lock timeout, 4 privacy scrub failed, other = git failure.
set -euo pipefail
cd "$(dirname "$0")/.."
export GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true
# Network steps are bounded so a stalled GitHub connection can't hold state/lock forever (124 = timed out).
GIT_NET_TIMEOUT="${GIT_NET_TIMEOUT:-120}"
gitnet() { timeout -k 10 "$GIT_NET_TIMEOUT" git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60 "$@"; }
mkdir -p state
paths=()
for p in "$@"; do
  [ "$p" = data/trades.json ] && { echo "publish: data/trades.json is private and never published; skipping it" >&2; continue; }
  paths+=("$p")
done
if [ ${#paths[@]} -eq 0 ]; then
  [ $# -gt 0 ] && { echo "publish: nothing to publish"; exit 0; }
  paths=(data)
fi

exec 9>>state/lock
if ! flock -w 300 9; then echo "publish: could not acquire state/lock" >&2; exit 3; fi

gitnet pull --rebase --autostash --quiet

# Data publishes first scrub paper-trade results out of the public files (scripts/privacy.py; the full trades doc is
# state/trades_full.json, git-ignored). A failed scrub stops the publish so results never go out by accident.
if [ -f scripts/privacy.py ] && printf '%s\n' "${paths[@]}" | grep -q '^data\(/\|$\)'; then
  if scrubbed=$(python3 scripts/privacy.py --lock-held --paths); then
    while IFS= read -r p; do [ -n "$p" ] && paths+=("$p"); done <<< "$scrubbed"
  else
    echo "publish: privacy scrub failed; not publishing" >&2; exit 4
  fi
fi

# Data publishes also regenerate the static coin pages (/xdc/ etc.) + sitemap.xml and publish them in the same commit.
# Set BUILD_PAGES=0 to skip. A failed build only warns: the data publish still goes out.
if [ "${BUILD_PAGES:-1}" != 0 ] && [ -f scripts/build_pages.py ] && printf '%s\n' "${paths[@]}" | grep -q '^data\(/\|$\)'; then
  if built=$(python3 scripts/build_pages.py --paths); then
    while IFS= read -r p; do [ -n "$p" ] && paths+=("$p"); done <<< "$built"
  else
    echo "publish: WARNING build_pages.py failed; publishing data without regenerating pages" >&2
  fi
fi

# Current paper-trade ideas for api.lumitrades.io /v1/slate and /v1/brief: data/ideas.json (pending/open ideas only, no
# closed ideas, outcomes or P&L; scripts/ideas.py) is regenerated from the private trades doc and staged on EVERY publish.
if [ -f scripts/ideas.py ]; then
  python3 scripts/ideas.py >/dev/null || echo "publish: WARNING scripts/ideas.py failed; data/ideas.json not refreshed" >&2
  [ -f data/ideas.json ] && paths+=(data/ideas.json)
fi

# Search-engine ownership files at the site root must stay published: always stage them
# (IndexNow key <32 hex>.txt with name == content, and Bing Webmaster Tools' BingSiteAuth.xml).
for k in [0-9a-f]*.txt; do
  [[ "$k" =~ ^[0-9a-f]{32}\.txt$ ]] && [ -f "$k" ] && paths+=("$k")
done
[ -f BingSiteAuth.xml ] && paths+=(BingSiteAuth.xml)

bad=0
while IFS= read -r -d '' f; do
  python3 -m json.tool "$f" >/dev/null 2>&1 || { echo "publish: invalid JSON: $f" >&2; bad=1; }
done < <(find "${paths[@]}" -name '*.json' -print0)
[ "$bad" -eq 0 ] || exit 2

git add -- "${paths[@]}"
git rm --cached -q --ignore-unmatch -- data/trades.json  # private: never in a commit
if git diff --cached --quiet -- "${paths[@]}"; then
  echo "publish: nothing to commit"
  exit 0
fi
msg="${PUBLISH_MSG:-Data update $(TZ=America/Chicago date '+%Y-%m-%d %H:%M %Z')}"
git commit --quiet -m "$msg" -- "${paths[@]}"
for i in 1 2 3; do
  if gitnet push --quiet; then
    echo "publish: pushed $(git rev-parse --short HEAD) — $msg"
    if [ "${INDEXNOW:-1}" != 0 ] && [ -f scripts/indexnow_ping.py ]; then
      timeout -k 5 45 python3 scripts/indexnow_ping.py --commit HEAD || echo "publish: WARNING IndexNow ping failed (publish is fine)" >&2
    fi
    exit 0
  fi
  echo "publish: push failed (attempt $i), rebasing and retrying" >&2
  sleep $((i * 3)); gitnet pull --rebase --autostash --quiet
done
exit 1
