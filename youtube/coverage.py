"""YouTube coverage for each X story, and a gap score.

For each story: search recent YouTube videos (one search.list call, 100
quota units), keep the ones that are actually about the story, then fetch
their stats and their channels' sizes in batched calls (1 unit per 50).
"""

import math
import re
from datetime import datetime, timedelta, timezone

BIG_CHANNEL_SUBS = 100_000

STOPWORDS = set("""
a an and are as at be by for from has have how in into is it its new of on or
that the this to via vs was what when why will with you your just now out up
ai announces announced launch launches launched release releases released
""".split())


def story_fields(story, index):
    """Pull id / title / query / heat out of an X story, tolerating schemas."""
    title = (story.get("title") or story.get("headline") or story.get("topic")
             or story.get("name") or "").strip()
    query = story.get("youtube_query") or story.get("search_query") or story.get("query")
    if not query and story.get("keywords"):
        kw = story["keywords"]
        query = " ".join(kw) if isinstance(kw, list) else str(kw)
    query = (query or title).strip()
    heat = None
    for key in ("heat", "x_heat", "x_score", "score"):
        v = story.get(key)
        if isinstance(v, (int, float)):
            heat = float(v)
            break
    sid = str(story.get("id") or story.get("story_id") or slug(title or query) or index)
    return sid, title, query, heat


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9][a-z0-9.+#-]*", text.lower())
            if t not in STOPWORDS and len(t) > 1]


def is_match(query, title, description):
    """True when the video is plausibly about the story, not just nearby."""
    want = list(dict.fromkeys(tokens(query)))
    if not want:
        return True
    hay = f"{title} {description}".lower()
    hits = sum(1 for t in want if t in hay)
    need = min(3, max(1, math.ceil(0.6 * len(want))))
    return hits >= need


def coverage_label(video_count, score):
    if video_count == 0:
        return "none"
    return "low" if score < 35 else "medium" if score < 65 else "high"


def coverage_score(total_views, matching, big_videos):
    """0 (nobody covered it) to 100 (saturated)."""
    # 1k combined views or fewer -> 0, 1M or more -> 1, log scale between.
    views = min(1.0, max(0.0, (math.log10(1 + total_views) - 3) / 3))
    count = min(1.0, matching / 8)
    big = min(1.0, big_videos / 2)
    return round(100 * (0.5 * views + 0.3 * count + 0.2 * big))


def run(client, stories, lookback_hours=72, per_story=25, max_stories=15, now=None):
    now = now or datetime.now(timezone.utc)
    after = (now - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    parsed = [story_fields(s, i) for i, s in enumerate(stories)]
    # Spend the expensive search calls on the hottest stories first.
    parsed.sort(key=lambda p: -(p[3] if p[3] is not None else 0))
    parsed = parsed[:max_stories]

    found = {}  # story id -> matching search items
    errors = []
    for sid, title, query, _ in parsed:
        try:
            res = client.get("search", part="snippet", q=query, type="video",
                             order="relevance", publishedAfter=after,
                             maxResults=per_story, relevanceLanguage="en")
        except Exception as e:  # keep going; one bad story shouldn't sink the run
            errors.append(f"{sid}: {e}")
            found[sid] = None
            if "HTTP 403" in str(e) or "HTTP 400" in str(e):
                break  # bad key or quota spent: the rest would fail the same way
            continue
        found[sid] = [it for it in res.get("items", [])
                      if is_match(query, it["snippet"].get("title", ""),
                                  it["snippet"].get("description", ""))]

    video_ids = [it["id"]["videoId"] for items in found.values() if items for it in items]
    videos = {v["id"]: v for v in client.videos(video_ids, parts="snippet,statistics")}
    channel_ids = [v["snippet"]["channelId"] for v in videos.values()]
    subs = {}
    for c in client.channels(channel_ids, parts="statistics"):
        st = c.get("statistics", {})
        subs[c["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))

    out = []
    for sid, title, query, heat in parsed:
        items = found.get(sid)
        entry = {"story_id": sid, "title": title, "query": query, "ok": items is not None}
        vids = []
        for it in items or []:
            v = videos.get(it["id"]["videoId"])
            if not v:
                continue
            sn, st = v["snippet"], v.get("statistics", {})
            vids.append({
                "video_id": v["id"],
                "title": sn.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={v['id']}",
                "channel": sn.get("channelTitle", ""),
                "channel_subscribers": subs.get(sn["channelId"]),
                "published_at": sn.get("publishedAt"),
                "views": int(st.get("viewCount", 0)),
            })
        vids.sort(key=lambda v: -v["views"])
        total = sum(v["views"] for v in vids)
        big = sum(1 for v in vids if (v["channel_subscribers"] or 0) >= BIG_CHANNEL_SUBS)
        cov = coverage_score(total, len(vids), big)
        # heat is 0-100 from x_trends; a story with no heat counts as fully hot.
        hot = heat if heat is not None else 100.0
        entry.update({
            "video_count": len(vids),
            "total_views": total,
            "max_views": vids[0]["views"] if vids else 0,
            "big_channel_videos": big,
            "coverage": coverage_label(len(vids), cov) if items is not None else None,
            "coverage_score": cov if items is not None else None,
            "heat": heat,
            "gap_score": round(hot * (100 - cov) / 100) if items is not None else None,
            "top_videos": vids[:5],
        })
        out.append(entry)

    out.sort(key=lambda e: -(e["gap_score"] or -1))
    return out, errors
