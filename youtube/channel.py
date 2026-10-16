"""Channel stats: how the latest videos compare to the channel's usual.

"Usual" means the median views of the channel's earlier videos at the same
age. The API only gives current view counts, so every run appends a
snapshot (age in hours, views) per video to a history file; once enough
earlier videos have been seen at a given age, that median is used. Until
then the comparison falls back to the median lifetime views of videos at
least 30 days old, and says so in "basis".
"""

import re
import statistics
from datetime import datetime, timezone

SHORT_MAX_SECONDS = 180
MIN_PEERS = 5
SNAPSHOT_TOLERANCE = 0.25  # a snapshot counts as "same age" within +/-25%
MATURE_HOURS = 30 * 24


def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def duration_seconds(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def views_at_age(snaps, age):
    """Views at `age` hours from a list of [age_hours, views], or None."""
    snaps = sorted(snaps)
    for (a0, v0), (a1, v1) in zip(snaps, snaps[1:]):
        if a0 <= age <= a1:
            return v0 if a1 == a0 else v0 + (v1 - v0) * (age - a0) / (a1 - a0)
    close = [(abs(a - age), v) for a, v in snaps if abs(a - age) <= SNAPSHOT_TOLERANCE * age]
    return min(close)[1] if close else None


def resolve_channel(client, handle):
    data = client.get("channels", part="snippet,statistics,contentDetails",
                      forHandle=handle.lstrip("@"))
    items = data.get("items") or []
    if not items:
        raise RuntimeError(f"no channel found for handle {handle}")
    return items[0]


def run(client, handle, history, latest_n=5, sample=50, now=None):
    now = now or datetime.now(timezone.utc)
    ch = resolve_channel(client, handle)
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = client.get("playlistItems", part="contentDetails", playlistId=uploads,
                    maxResults=min(sample, 50))
    ids = [it["contentDetails"]["videoId"] for it in pl.get("items", [])]

    vids = []
    for v in client.videos(ids):
        sn, st = v["snippet"], v.get("statistics", {})
        if sn.get("liveBroadcastContent") in ("live", "upcoming"):
            continue
        age = (now - parse_time(sn["publishedAt"])).total_seconds() / 3600
        vids.append({
            "id": v["id"],
            "title": sn.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={v['id']}",
            "published_at": sn["publishedAt"],
            "age_hours": round(age, 1),
            "is_short": duration_seconds(v["contentDetails"].get("duration")) <= SHORT_MAX_SECONDS,
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)) if "likeCount" in st else None,
            "comments": int(st.get("commentCount", 0)) if "commentCount" in st else None,
        })
    vids.sort(key=lambda v: v["published_at"], reverse=True)

    # Record this run's snapshot before comparing, so history grows each run.
    for v in vids:
        snaps = history.setdefault(v["id"], [])
        snaps.append([v["age_hours"], v["views"]])
        # Same-age comparisons only matter for young videos; keep the file small.
        snaps[:] = [x for x in snaps if x[0] <= 2 * MATURE_HOURS][-60:]
    current = {v["id"] for v in vids}
    for vid in [k for k in history if k not in current or not history[k]]:
        del history[vid]  # fell out of the sample, or too old to matter

    def baseline(v, peers):
        at_age = [views_at_age(history.get(p["id"], []), v["age_hours"]) for p in peers]
        at_age = [x for x in at_age if x is not None]
        if len(at_age) >= MIN_PEERS:
            return statistics.median(at_age), "same_age", len(at_age)
        mature = [p["views"] for p in peers if p["age_hours"] >= MATURE_HOURS]
        if len(mature) >= MIN_PEERS:
            return statistics.median(mature), "lifetime_median", len(mature)
        return None, "not_enough_history", 0

    latest = []
    for i, v in enumerate(vids[:latest_n]):
        peers = [p for p in vids[i + 1:] if p["is_short"] == v["is_short"]]
        expected, basis, n = baseline(v, peers)
        ratio = round(v["views"] / expected, 2) if expected else None
        if ratio is None:
            verdict = "unknown"
        elif ratio >= 1.5:
            verdict = "outperforming"
        elif ratio >= 0.75:
            verdict = "on_par"
        else:
            verdict = "under"
        latest.append({
            "video_id": v["id"],
            "title": v["title"],
            "published_at": v["published_at"],
            "url": v["url"],
            "views": v["views"],
            "likes": v["likes"],
            "comments": v["comments"],
            "views_per_day": round(v["views"] / max(v["age_hours"] / 24, 1)),
            "vs_baseline": ratio,
            "age_hours": v["age_hours"],
            "is_short": v["is_short"],
            "expected_views": round(expected) if expected else None,
            "basis": basis,
            "peer_count": n,
            "verdict": verdict,
        })

    mature_long = [v for v in vids if not v["is_short"] and v["age_hours"] >= MATURE_HOURS]
    mature_short = [v for v in vids if v["is_short"] and v["age_hours"] >= MATURE_HOURS]

    def med(xs):
        return round(statistics.median(xs)) if xs else None

    st = ch.get("statistics", {})
    handle = handle if handle.startswith("@") else "@" + handle
    return {
        "channel": {
            "id": ch["id"],
            "title": ch["snippet"].get("title"),
            "handle": handle,
            "url": f"https://www.youtube.com/{handle}",
            "subscribers": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0)),
            "total_views": int(st.get("viewCount", 0)),
            "video_count": int(st.get("videoCount", 0)),
        },
        "baseline": {
            "description": (
                "Each video is compared with earlier videos of the same type (Short or long-form) "
                "at the same age, from twice-daily view snapshots. Until 5 such videos exist it uses "
                "the median lifetime views of videos 30+ days old. median_views below is that "
                "lifetime median for long-form videos."),
            "median_views": med([v["views"] for v in mature_long]),
            "median_views_per_day": med([v["views"] / (v["age_hours"] / 24) for v in mature_long]),
            "shorts_median_views": med([v["views"] for v in mature_short]),
            "sample_size": len(vids),
        },
        "recent_videos": latest,
    }
