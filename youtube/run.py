#!/usr/bin/env python3
"""YouTube step of the AI Creator Radar cloud refresh. One command, from the repo root:

    python3 youtube/run.py

Reads data/x_trends.json and writes, per docs/DATA.md:
  data/youtube_coverage.json   coverage + gap score per X story
  data/channel_stats.json      @Chase-H-AI latest videos vs. usual
  data/refresh_log.json        one entry per step (youtube_coverage, channel_stats)
  data/youtube_history.json    view snapshots for same-age comparisons (not read by the page)

A step that fails leaves its previous data file in place and logs the error.
Stdlib only; no key in code (see yt_api.py). Exit 1 only if both steps fail.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import channel  # noqa: E402
import coverage  # noqa: E402
from yt_api import YouTubeClient  # noqa: E402

LOG_MAX = 60


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def append_log(path, entries):
    log = load_json(path, {})
    if log.get("sample"):
        log = {}  # drop placeholder entries on the first real run
    merged = sorted(entries + log.get("entries", []), key=lambda e: e["at"], reverse=True)[:LOG_MAX]
    write_json(path, {"schema_version": 1, "generated_at": merged[0]["at"], "entries": merged})


def run_coverage(client, args, now):
    x = load_json(os.path.join(args.data, "x_trends.json"), None)
    if x is None:
        raise RuntimeError("data/x_trends.json not found")
    stories, errors = coverage.run(client, x.get("stories", []), lookback_hours=args.lookback_hours,
                                   max_stories=args.max_stories, now=now)
    good = [s for s in stories if s.pop("ok")]
    if stories and not good:
        raise RuntimeError("; ".join(errors[:3]) or "every search failed")
    write_json(os.path.join(args.data, "youtube_coverage.json"), {
        "schema_version": 1,
        "generated_at": iso(now),
        "x_trends_generated_at": x.get("generated_at"),
        "x_trends_sample": bool(x.get("sample")),
        "lookback_hours": args.lookback_hours,
        "stories": good,
    })
    gaps = sum(1 for s in good if (s["gap_score"] or 0) >= 50)
    msg = f"Checked {len(good)} stories, {gaps} gaps (gap score 50+)"
    if errors:
        msg += f"; {len(errors)} failed: {errors[0]}"
    return ("partial" if errors else "ok"), msg, {"stories": len(good), "gaps": gaps}


def run_channel(client, args, now):
    hist_path = os.path.join(args.data, "youtube_history.json")
    history = load_json(hist_path, {})
    out = channel.run(client, args.handle, history, latest_n=args.latest, now=now)
    write_json(os.path.join(args.data, "channel_stats.json"),
               {"schema_version": 1, "generated_at": iso(now), **out})
    write_json(hist_path, history)
    known = sum(1 for v in out["recent_videos"] if v["vs_baseline"] is not None)
    return "ok", f"{len(out['recent_videos'])} recent videos, {known} compared to usual", \
        {"videos": len(out["recent_videos"])}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data", help="data directory (default: data)")
    p.add_argument("--handle", default="@Chase-H-AI")
    p.add_argument("--max-stories", type=int, default=15,
                   help="stories to search, hottest first (100 quota units each)")
    p.add_argument("--lookback-hours", type=int, default=72, help="how far back YouTube coverage counts")
    p.add_argument("--latest", type=int, default=5, help="recent uploads to compare (5-8)")
    args = p.parse_args(argv)

    client = YouTubeClient()
    now = datetime.now(timezone.utc)
    entries, failed = [], 0
    for step, fn in (("youtube_coverage", run_coverage), ("channel_stats", run_channel)):
        t0, used0 = time.monotonic(), client.quota_used
        try:
            status, msg, counts = fn(client, args, now)
        except Exception as e:
            status, msg, counts, failed = "error", f"{type(e).__name__}: {e}", {}, failed + 1
        counts["quota_units"] = client.quota_used - used0
        entries.append({"at": iso(datetime.now(timezone.utc)), "job": "cloud_refresh", "step": step,
                        "status": status, "duration_s": round(time.monotonic() - t0),
                        "message": msg[:300], "counts": counts})
        print(f"{step}: {status}: {msg}", file=sys.stderr if status == "error" else sys.stdout)

    append_log(os.path.join(args.data, "refresh_log.json"), entries)
    print(f"YouTube quota used: ~{client.quota_used} units")
    return 1 if failed == 2 else 0


if __name__ == "__main__":
    sys.exit(main())
