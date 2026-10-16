# Content packs

For each of the top 5 gaps (AI stories big on X with little YouTube coverage),
a ready-to-make content pack: a YouTube angle (title, thumbnail text, hook), a
timed 30-second Short script, a 5 to 8 slide carousel and an X post.

No API key: the scheduled refresh session is Claude, and it writes the packs
itself following [WRITING.md](WRITING.md) and [voice.md](voice.md). The scripts
here only do the mechanical parts, with no dependencies:

- `prepare.mjs` joins `data/x_trends.json` and `data/youtube_coverage.json` on
  story id, ranks by `gap_score`, skips sample inputs, and writes a brief of the
  top gaps, marking unchanged stories whose pack can be kept as is.
- `finish.mjs` checks `data/content_packs.json` against `docs/DATA.md` pack by
  pack and logs the run to `data/refresh_log.json`.

Edit `voice.md` to change how the packs sound. Editing it also makes every
story count as changed, so the next refresh rewrites all packs in the new voice.

Tests: `node --test content-packs/`.
