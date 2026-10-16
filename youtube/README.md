# YouTube step

Run from the repo root as part of the cloud refresh, after the X scan has landed:

```
python3 youtube/run.py
```

Stdlib Python 3, no installs. Reads `data/x_trends.json` and writes, per `docs/DATA.md`:

- `data/youtube_coverage.json`: coverage and gap score per X story
- `data/channel_stats.json`: @Chase-H-AI's latest uploads vs. usual
- `data/refresh_log.json`: one `cloud_refresh` entry per step (`youtube_coverage`, `channel_stats`)
- `data/youtube_history.json`: public view snapshots for same-age comparisons (not read by the page)

A step that fails keeps its previous data file and logs the error. The command exits 1 only when
both steps fail. It does not commit; the refresh job commits the files above.

**Key.** Never in code. Read from `YOUTUBE_API_KEY` if set; otherwise requests go out keyless
so the environment's network secret can add it.

**Coverage.** For the hottest 15 stories, one `search.list` over the last 72 hours using the
story's `keywords` (or title), keeping only videos whose title/description contain most of the
key terms. Stats and channel sizes come from batched calls. `coverage_score` (0 to 100) blends
combined views (log scale, 1k to 1M), video count and videos from 100k+ subscriber channels.
`coverage` is `none` for 0 videos, then `low` under 35, `medium` under 65, else `high`.
`gap_score = round(heat * (100 - coverage_score) / 100)`.

**Channel.** The last 50 uploads. Each of the latest 5 is compared with earlier videos of the
same kind (Short = 3 minutes or less, or long-form) at the same age, using the snapshot history.
Until 5 such peers exist it falls back to the median lifetime views of videos 30+ days old;
`basis` says which. `vs_baseline` is views / expected; `verdict` is outperforming (1.5x+),
on_par, or under (below 0.75x).

**Quota.** About 100 units per story plus ~5 per run: ~1,505 per run, ~3,000 a day at two runs,
of the 10,000 daily limit. A 403 (bad key or quota spent) stops further searches. Tune with
`--max-stories`.

Tests: `python3 -m unittest discover -s youtube`
