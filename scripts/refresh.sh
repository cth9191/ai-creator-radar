#!/usr/bin/env bash
# Cloud refresh: YouTube coverage + channel stats, Claude Code news, content packs.
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
if [ -f content-packs/generate.mjs ]; then
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    step content_packs bash -c 'cd content-packs && npm ci --silent && node generate.mjs'
  else
    echo "::: content_packs SKIPPED (no ANTHROPIC_API_KEY): write packs in-session per docs/REFRESH.md"
  fi
fi

if ! node scripts/validate-data.mjs; then
  echo "validation failed; restoring data/ and not publishing"
  git checkout -- data/
  exit 1
fi
