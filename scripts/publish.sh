#!/usr/bin/env bash
# Publish data updates to GitHub Pages without prompts.
#   scripts/publish.sh                    # stage everything under data/
#   scripts/publish.sh data/trades.json data/log.json data/signals.json   # stage only these paths
#   PUBLISH_MSG="custom message" scripts/publish.sh
# Steps: take state/lock -> git pull --rebase --autostash -> validate JSON -> git add -> commit only if changed -> push.
# Exit codes: 0 ok / nothing to publish, 2 invalid JSON, 3 lock timeout, other = git failure.
set -euo pipefail
cd "$(dirname "$0")/.."
export GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true
mkdir -p state
paths=("$@"); [ ${#paths[@]} -eq 0 ] && paths=(data)

exec 9>>state/lock
if ! flock -w 300 9; then echo "publish: could not acquire state/lock" >&2; exit 3; fi

git pull --rebase --autostash --quiet

bad=0
while IFS= read -r -d '' f; do
  python3 -m json.tool "$f" >/dev/null 2>&1 || { echo "publish: invalid JSON: $f" >&2; bad=1; }
done < <(find "${paths[@]}" -name '*.json' -print0)
[ "$bad" -eq 0 ] || exit 2

git add -- "${paths[@]}"
if git diff --cached --quiet -- "${paths[@]}"; then
  echo "publish: nothing to commit"
  exit 0
fi
msg="${PUBLISH_MSG:-Data update $(TZ=America/Chicago date '+%Y-%m-%d %H:%M %Z')}"
git commit --quiet -m "$msg" -- "${paths[@]}"
for i in 1 2 3; do
  if git push --quiet; then echo "publish: pushed $(git rev-parse --short HEAD) — $msg"; exit 0; fi
  echo "publish: push failed (attempt $i), rebasing and retrying" >&2
  sleep $((i * 3)); git pull --rebase --autostash --quiet
done
exit 1
