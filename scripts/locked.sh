#!/usr/bin/env bash
# Run any command while holding state/lock (same lock as track_trades.py / update_prices.py / publish.sh).
# Use it for hand edits of state/trades.json (private) or data/log.json so the 30-min tracker can't overwrite them:
#   scripts/locked.sh python3 my_edit.py
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p state
exec flock -w 300 state/lock "$@"
