#!/usr/bin/env bash
# Cloud refresh: YouTube coverage + channel stats and Claude Code news.
# Content packs are written afterwards by the Claude session running this job.
# Runs twice daily in a scheduled Claude cloud session (see docs/REFRESH.md).
# Each step is independent: a failed step keeps its last good file and logs the error.
# Commits only data/ files, straight to main.
set -uo pipefail
cd "$(dirname "$0")/.."

git fetch -q origin main && git checkout -q -B main origin/main || { echo "could not sync main"; exit 1; }

step() {  # step <name> <command...>
  local name=$1; shift
  echo "::: $name"
  if "$@"; then echo "::: $name ok"; else echo "::: $name FAILED ($?)"; fi
}

[ -f fetchers/claude_code_news/fetch.py ] && step claude_code_news python3 fetchers/claude_code_news/fetch.py --out data/claude_code_news.json
[ -f youtube/run.py ] && step youtube python3 youtube/run.py
# Content packs are written by the scheduled Claude session itself (no API key), after this script.
echo "::: content_packs SKIPPED (written in-session by the scheduled Claude session, see docs/REFRESH.md)"

if ! node scripts/validate-data.mjs; then
  echo "validation failed; restoring data/ and not publishing"
  git checkout -- data/
  exit 1
fi
