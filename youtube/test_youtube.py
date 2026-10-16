"""Offline tests: python3 -m unittest discover -s youtube"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import channel  # noqa: E402
import coverage  # noqa: E402

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def ts(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeClient:
    """Answers the handful of endpoints the radar uses from canned data."""

    def __init__(self, search=None, videos=None, channels=None, uploads=None):
        self.search = search or {}
        self.vids = videos or {}
        self.chans = channels or {}
        self.uploads = uploads or []
        self.calls = []
        self.quota_used = 0

    def get(self, endpoint, **params):
        self.calls.append(endpoint)
        if endpoint == "search":
            return {"items": self.search.get(params["q"], [])}
        if endpoint == "channels":
            return {"items": [{"id": "UCchase", "snippet": {"title": "Chase AI"},
                               "statistics": {"subscriberCount": "50000", "viewCount": "1000000", "videoCount": "60"},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UUchase"}}}]}
        if endpoint == "playlistItems":
            return {"items": [{"contentDetails": {"videoId": v}} for v in self.uploads]}
        raise AssertionError(endpoint)

    def videos(self, ids, parts=None):
        self.calls.append("videos")
        return [self.vids[i] for i in ids if i in self.vids]

    def channels(self, ids, parts=None):
        self.calls.append("channels")
        return [{"id": c, "statistics": {"subscriberCount": str(self.chans[c])}} for c in ids if c in self.chans]


def search_item(vid, title, desc=""):
    return {"id": {"videoId": vid}, "snippet": {"title": title, "description": desc}}


def video(vid, views, channel_id="UCx", hours_ago=10, duration="PT12M", title="t"):
    return {"id": vid,
            "snippet": {"title": title, "channelId": channel_id, "channelTitle": channel_id,
                        "publishedAt": ts(hours_ago)},
            "statistics": {"viewCount": str(views)},
            "contentDetails": {"duration": duration}}


class CoverageTests(unittest.TestCase):
    def test_gap_ranks_uncovered_hot_story_first(self):
        stories = [
            {"id": "a", "title": "Claude Opus 6 benchmarks", "heat": 100},
            {"id": "b", "title": "Gemini 4 Ultra launch", "keywords": ["gemini 4", "ultra"], "heat": 80},
        ]
        client = FakeClient(
            search={
                "Claude Opus 6 benchmarks": [search_item("v1", "Some unrelated cooking video")],
                "gemini 4 ultra": [search_item("v2", "Gemini 4 Ultra is here"),
                                          search_item("v3", "Gemini 4 Ultra first test")],
            },
            videos={"v1": video("v1", 5), "v2": video("v2", 900_000, "UCbig"),
                    "v3": video("v3", 300_000, "UCbig")},
            channels={"UCbig": 2_000_000},
        )
        out, errors = coverage.run(client, stories, now=NOW)
        self.assertEqual(errors, [])
        self.assertEqual(out[0]["story_id"], "a")
        self.assertEqual(out[0]["video_count"], 0)  # the cooking video is filtered out
        self.assertEqual(out[0]["gap_score"], 100)
        self.assertEqual(out[0]["coverage"], "none")
        b = out[1]
        self.assertEqual(b["video_count"], 2)
        self.assertEqual(b["big_channel_videos"], 2)
        self.assertGreater(b["coverage_score"], 60)
        self.assertEqual(b["coverage"], "high")
        self.assertLess(b["gap_score"], 30)
        self.assertEqual(b["top_videos"][0]["video_id"], "v2")

    def test_max_stories_caps_search_calls(self):
        stories = [{"title": f"story {i}", "heat": i} for i in range(30)]
        client = FakeClient()
        out, _ = coverage.run(client, stories, max_stories=4, now=NOW)
        self.assertEqual(client.calls.count("search"), 4)
        self.assertEqual({o["title"] for o in out}, {"story 29", "story 28", "story 27", "story 26"})

    def test_match_needs_most_key_terms(self):
        self.assertTrue(coverage.is_match("OpenAI Sora 3 release", "Sora 3 from OpenAI is wild", ""))
        self.assertFalse(coverage.is_match("OpenAI Sora 3 release", "OpenAI earnings call", ""))


class ChannelTests(unittest.TestCase):
    def test_lifetime_fallback_then_same_age(self):
        # newest first: one fresh long video, one fresh short, then mature peers
        vids = {"new": video("new", 6000, hours_ago=24),
                "short": video("short", 100, hours_ago=30, duration="PT45S")}
        uploads = ["new", "short"]
        for i in range(8):
            vid = f"old{i}"
            vids[vid] = video(vid, 4000 + i * 100, hours_ago=24 * (40 + i))
            uploads.append(vid)
        client = FakeClient(videos=vids, uploads=uploads)

        history = {}
        out = channel.run(client, "@Chase-H-AI", history, latest_n=2, now=NOW)
        new = out["recent_videos"][0]
        self.assertEqual(new["video_id"], "new")
        self.assertEqual(new["basis"], "lifetime_median")
        self.assertEqual(new["expected_views"], 4350)
        self.assertEqual(new["verdict"], "on_par")  # 6000 / 4350 = 1.38
        self.assertEqual(out["recent_videos"][1]["basis"], "not_enough_history")  # no other shorts
        self.assertIn("new", history)

        # Peers that were snapshotted at ~24h make the comparison same-age.
        for i in range(8):
            history[f"old{i}"] = [[20, 2000], [30, 3000]]
        out = channel.run(client, "@Chase-H-AI", history, latest_n=1, now=NOW)
        self.assertEqual(out["recent_videos"][0]["basis"], "same_age")
        self.assertEqual(out["recent_videos"][0]["expected_views"], 2400)
        self.assertEqual(out["recent_videos"][0]["vs_baseline"], 2.5)

    def test_old_snapshots_pruned(self):
        vids = {"v": video("v", 10, hours_ago=24 * 90)}
        history = {"v": [[24, 1]], "gone": [[5, 5]]}
        channel.run(FakeClient(videos=vids, uploads=["v"]), "Chase-H-AI", history, now=NOW)
        self.assertEqual(history, {"v": [[24, 1]]})

    def test_duration(self):
        self.assertEqual(channel.duration_seconds("PT1H2M3S"), 3723)
        self.assertEqual(channel.duration_seconds("PT59S"), 59)


class RunTests(unittest.TestCase):
    def test_writes_shared_format_and_keeps_old_file_on_error(self):
        import json
        import tempfile
        import run

        d = tempfile.mkdtemp()
        with open(os.path.join(d, "x_trends.json"), "w") as f:
            json.dump({"generated_at": "2026-10-16T12:30:00Z",
                       "stories": [{"id": "s1", "title": "Sora 3 release", "heat": 90}]}, f)
        with open(os.path.join(d, "channel_stats.json"), "w") as f:
            f.write('{"previous": true}')
        with open(os.path.join(d, "refresh_log.json"), "w") as f:
            json.dump({"sample": True, "entries": [{"at": "2026-10-16T00:00:00Z"}]}, f)

        class Client(FakeClient):
            def get(self, endpoint, **params):
                if endpoint == "channels":
                    raise RuntimeError("boom")
                return super().get(endpoint, **params)

        run.YouTubeClient = lambda: Client()
        self.assertEqual(run.main(["--data", d]), 0)
        cov = json.load(open(os.path.join(d, "youtube_coverage.json")))
        self.assertEqual(cov["schema_version"], 1)
        self.assertEqual(cov["x_trends_generated_at"], "2026-10-16T12:30:00Z")
        self.assertEqual(cov["stories"][0]["story_id"], "s1")
        self.assertNotIn("ok", cov["stories"][0])
        self.assertEqual(open(os.path.join(d, "channel_stats.json")).read(), '{"previous": true}')
        log = json.load(open(os.path.join(d, "refresh_log.json")))
        self.assertEqual({e["step"]: e["status"] for e in log["entries"]},
                         {"channel_stats": "error", "youtube_coverage": "ok"})  # sample entry dropped


if __name__ == "__main__":
    unittest.main()
