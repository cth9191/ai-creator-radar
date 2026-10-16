# Content packs

Turns the top gaps (AI stories big on X with little YouTube coverage) into
ready-to-make content with the Claude API (`claude-opus-5-5`). One pack per gap,
up to 5, in the `data/content_packs.json` shape from `docs/DATA.md`:

- **video**: title, thumbnail text, a word-for-word opening hook (plus alternate titles and an outline)
- **short**: a timed 30-second script as beats (`t`, `line`, `visual`)
- **carousel**: 6 to 7 slides (heading, body) for the page's square previews, plus a caption
- **x_post**: the post, 280 characters max (plus an optional `x_thread`)
- **why_now**: one or two sentences on why to make it today

## Run it (cloud refresh step, after YouTube coverage)

```sh
cd content-packs && npm ci && node generate.mjs
```

It reads `data/x_trends.json` and `data/youtube_coverage.json`, joins them on
story id, ranks by `gap_score` (falling back to the page's formula), writes
`data/content_packs.json` and appends a `content_packs` entry to
`data/refresh_log.json`. Committing and pushing is left to the refresh job.

Options: `--top N` (1 to 5, default 5), `--force` (regenerate even if
unchanged), `--allow-sample` (generate even when inputs are sample data),
`--data-dir DIR`, `--output FILE`, `--dry-run` (placeholder packs, no API call,
no log entry).

The step always exits 0 so the rest of the refresh still runs; problems show up
in the refresh log. It keeps the previous packs when:

- the inputs are still sample data (no API calls are spent on made-up stories),
- `ANTHROPIC_API_KEY` isn't set, or
- every story failed. A single failed story keeps its last good pack, marked `stale: true`.

A pack whose story, voice guide, prompt and model are unchanged is reused
instead of regenerated, which keeps cost down across twice-daily runs.

## API key

Reads `ANTHROPIC_API_KEY` from the environment only. Never put a key in this
repo; it is public.

## Voice

`voice.md` is the style guide sent with every request. Edit it to tune how the
packs sound; changing it regenerates the packs on the next refresh.

## Tests

`npm test`: gap ranking, pack limits, a dry run checked with
`scripts/validate-data.mjs`, and the sample and no-key skips.
