# Twice-daily refresh

| When (UTC) | Where | What |
| --- | --- | --- |
| ~12:30 and ~22:30 | Chase's PC (local scheduled job) | X scan writes `data/x_trends.json`, pushes to `main` |
| 13:00 and 23:00 | Claude cloud scheduled task | `scripts/refresh.sh`, then `scripts/publish-data.sh` |

GitHub Pages rebuilds on every push to `main`, so the page updates within a minute or two of each push.

## Why a Claude cloud scheduled task

The YouTube Data API key exists only as a network secret on the Claude cloud environment: the
proxy adds it to requests to `googleapis.com`. It is never in code, in GitHub secrets, or on disk.
So the YouTube step has to run inside a Claude cloud session in that environment, and a scheduled
task that starts a fresh session there twice a day is the simplest way to do it. A fresh session per
run means no state carries over except what is in the repo.

Content packs need no API key: the scheduled session is Claude, so after `scripts/refresh.sh` it
writes `data/content_packs.json` itself, following `content-packs/WRITING.md` and
`content-packs/voice.md`. The only secret involved is the YouTube key.

## The scheduled task's prompt

```
AI Creator Radar cloud refresh. In the cth9191/ai-creator-radar repo:
1. Run `bash scripts/refresh.sh` and read its output.
2. It prints "content_packs SKIPPED": write the content packs yourself by following content-packs/WRITING.md
   (run `node content-packs/prepare.mjs`, write data/content_packs.json in the voice of content-packs/voice.md,
   then `node content-packs/finish.mjs`).
3. Run `bash scripts/publish-data.sh`. Commit only data/ files. Never put keys in the repo.
4. If any step failed, say which and why in your final message.
```
