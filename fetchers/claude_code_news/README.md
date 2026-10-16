# Claude Code news

Pulls the latest Claude Code releases for the dashboard's release news panel.

- **Sources (public, no keys):** the [Claude Code CHANGELOG.md](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md) for what changed, and the npm registry for when each version was published and which version is `latest`, `stable` and `next`.
- **Run (refresh step):** `python3 fetchers/claude_code_news/fetch.py --out data/claude_code_news.json`
  Python 3 standard library only. On a network or parse failure it exits 1 and leaves the previous file in place.
- **Test:** `cd fetchers/claude_code_news && python3 -m unittest test_fetch`

## Output

`sample.json` is a real run. Top level:

| field | meaning |
| --- | --- |
| `generated_at` | UTC time of this run |
| `status` / `error` | `ok`, or `partial` when npm dates were unavailable |
| `latest_version`, `latest_released_at` | newest version in the changelog and its npm publish time |
| `dist_tags` | npm `latest` / `stable` / `next` versions |
| `headline` | one line for the panel header |
| `releases[]` | newest first, 8 by default (`--releases N`) |

Each release has `version`, `released_at`, `url`, `summary` (e.g. "8 added, 4 improved, 2 changed, 37 fixed"), `counts`, `highlights` (up to 5 items, new features first, trimmed to 180 characters) and `notable` (every non-fix item). Items are `{kind, area, text}`, where `kind` is added, improved, changed, removed or fixed, `area` is a surface tag such as `VSCode` or `Cloud sessions` (or null), and `text` keeps the changelog's Markdown backticks.
