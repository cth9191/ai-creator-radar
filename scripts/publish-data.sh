#!/usr/bin/env bash
# Commit data/ and push to main, retrying on a race with the X scan push.
set -uo pipefail
cd "$(dirname "$0")/.."
node scripts/validate-data.mjs || exit 1
git add data/
git diff --cached --quiet && { echo "nothing to publish"; exit 0; }
git -c user.name="AI Creator Radar" -c user.email="radar@users.noreply.github.com" \
  commit -qm "data: cloud refresh $(date -u +%Y-%m-%dT%H:%MZ)"
for i in 1 2 3 4; do
  git push -q origin HEAD:main && { echo "published"; exit 0; }
  sleep $((2 ** i))
  git pull -q --rebase origin main || { echo "rebase conflict"; exit 1; }
done
echo "push failed"; exit 1
