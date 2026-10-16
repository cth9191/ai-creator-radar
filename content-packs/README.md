# Content packs

Turns the top gaps (AI stories big on X with little YouTube coverage) into
ready-to-make content with the Claude API (`claude-opus-5-5`). One pack per gap:

- **video**: title, two alternates, thumbnail text, a word-for-word opening hook, and an outline
- **short**: a timed 30-second script plus on-screen text
- **carousel**: 6 to 8 slides (heading, body, visual note) the page can preview, plus a caption
- **x_post**: a main post and an optional short thread
- **why_now**: one or two sentences on why to make it today

## Run it (refresh step)

```sh
cd content-packs && npm ci
node generate.mjs            # reads data/gaps.json, writes data/content_packs.json
```

Options: `--input FILE`, `--output FILE`, `--top N` (default 3), `--force`
(regenerate even if unchanged), `--dry-run` (placeholder packs, no API call).

- Input: `data/gaps.json` if it exists, otherwise `sample/gaps.json`. Accepts a
  bare array or `{ "gaps": [...] }`; each gap needs a `title` (or `headline`),
  and is ranked by `gap_score` (or `score`). The whole gap object is passed to
  Claude, so any extra fields upstream adds (posts, view counts) are used.
- Output: `{ schema_version, generated_at, source, packs: [...] }`, each pack
  carrying `gap_id`, `gap_title`, `model`, `generated_at` and the fields above.
  See `sample/content_packs.dry-run.json` for the exact shape.
- Cost control: a pack whose story, voice guide and model are unchanged is
  reused from the previous output instead of regenerated.
- If one story fails, its last good pack is kept (marked `stale: true`), or it
  gets an `error` field. The step exits non-zero only if every pack failed.

## API key

Reads `ANTHROPIC_API_KEY` from the environment only; never put a key in this
repo (it is public). Without the key the step logs that it skipped and leaves
the previous `data/content_packs.json` alone, so the rest of the refresh runs.

## Voice

`voice.md` is the style guide sent with every request. Edit it to tune how the
packs sound; changing it triggers a regeneration on the next refresh.

## Tests

`npm test` covers input parsing, a dry run, and the no-key skip.
