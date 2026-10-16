# Claude Code news

Pulls the latest Claude Code releases for the dashboard's release news panel.

- **Sources (public, no keys):** the [Claude Code CHANGELOG.md](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md) for what changed, and the npm registry for when each version was published and which version is `latest`, `stable` and `next`.
- **Refresh step:** `python3 fetchers/claude_code_news/fetch.py`
  Writes `data/claude_code_news.json` and appends a `cloud_refresh` / `claude_code_news` entry to `data/refresh_log.json` (`--out`, `--log ''` to change or skip). Python 3 standard library only. On a network or parse failure it logs an `error` entry, exits 1 and leaves the previous news file in place.
- **Test:** `cd fetchers/claude_code_news && python3 -m unittest test_fetch`

## Output

Follows `claude_code_news.json` in [docs/DATA.md](../../docs/DATA.md): the last 8 releases, newest first, each with `version`, `date`, `title` (e.g. "8 new features, 4 improvements, 2 changes, 37 fixes"), up to 5 plain-text `highlights` (new features first, prefixed with the area such as `VSCode:` when the changelog names one) and an npm `url`.

Extra fields the page may use: top-level `dist_tags`, and per release `released_at` (full timestamp), `summary` and `counts` by kind.
