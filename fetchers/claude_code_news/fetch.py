#!/usr/bin/env python3
"""Claude Code release news for AI Creator Radar.

Reads the public Claude Code changelog (anthropics/claude-code CHANGELOG.md)
and the npm registry's publish times, then writes a summary of the latest
releases as JSON for the dashboard. Standard library only, no API keys.

Usage:
    python3 fetchers/claude_code_news/fetch.py [--out data/claude_code_news.json] [--log data/refresh_log.json]

Output format: docs/DATA.md, section claude_code_news.json.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

CHANGELOG_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
CHANGELOG_PAGE = "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md"
NPM_URL = "https://registry.npmjs.org/@anthropic-ai/claude-code"
NPM_PAGE = "https://www.npmjs.com/package/@anthropic-ai/claude-code/v/{version}"

KINDS = ("added", "improved", "changed", "fixed", "removed")
# Kinds that make good headlines, best first.
HEADLINE_ORDER = ("added", "improved", "changed", "removed", "fixed")
HIGHLIGHTS_PER_RELEASE = 5
HIGHLIGHT_MAX_CHARS = 180
AREA_RE = re.compile(r"^\[([^\]]{1,40})\]\s*|^([A-Za-z][\w .+-]{0,30}):\s+(?=[A-Z])")
SYNONYMS = {"new": "added", "introduced": "added", "updated": "changed", "reverted": "changed"}


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-creator-radar"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def parse_item(line):
    """Split one changelog bullet into area, kind and text."""
    text = line.strip()
    areas = []
    while True:
        m = AREA_RE.match(text)
        if not m:
            break
        label = (m.group(1) or m.group(2)).strip()
        if m.group(2) and label.split(" ", 1)[0].lower() in KINDS + tuple(SYNONYMS):
            break  # "Improved artifact updates: ..." is a sentence, not an area
        areas.append(label)
        text = text[m.end():].strip()
    first = text.split(" ", 1)[0].lower()
    kind = first if first in KINDS else SYNONYMS.get(first, "other")
    return {"kind": kind, "area": " / ".join(areas) or None, "text": text}


def parse_changelog(md):
    """Return [{version, items}] in file order (newest first)."""
    releases, current, item = [], None, None
    for raw in md.splitlines():
        if raw.startswith("## "):
            current = {"version": raw[3:].strip(), "items": []}
            releases.append(current)
            item = None
        elif current is None:
            continue
        elif raw.startswith("- "):
            item = raw[2:]
            current["items"].append(item)
        elif raw.startswith("  ") and raw.strip() and current["items"]:
            # Continuation of a wrapped or nested bullet.
            current["items"][-1] += " " + raw.strip().lstrip("- ")
    for rel in releases:
        rel["items"] = [parse_item(i) for i in rel["items"]]
    return releases


def shorten(text, limit=HIGHLIGHT_MAX_CHARS):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def pick_highlights(items, n=HIGHLIGHTS_PER_RELEASE):
    ranked = sorted(
        enumerate(items),
        key=lambda p: (HEADLINE_ORDER.index(p[1]["kind"]) if p[1]["kind"] in HEADLINE_ORDER else len(HEADLINE_ORDER), p[0]),
    )
    out = []
    for _, it in ranked[:n]:
        text = shorten(it["text"])
        out.append({"kind": it["kind"], "area": it["area"], "text": text})
    return out


def summarize(rel):
    counts = {k: 0 for k in KINDS + ("other",)}
    for it in rel["items"]:
        counts[it["kind"]] += 1
    parts = []
    for k in ("added", "improved", "changed", "fixed", "removed"):
        if counts[k]:
            parts.append(f"{counts[k]} {k}")
    return counts, (", ".join(parts) if parts else f"{len(rel['items'])} changes")


def title(counts, summary):
    """Short release headline, e.g. "8 new features, 6 improvements, 37 fixes"."""
    parts = []
    for key, one, many in (("added", "new feature", "new features"),
                           ("improved", "improvement", "improvements"),
                           ("changed", "change", "changes"),
                           ("fixed", "fix", "fixes")):
        n = counts[key] + (counts["removed"] if key == "changed" else 0)
        if n:
            parts.append(f"{n} {one if n == 1 else many}")
    return ", ".join(parts) or summary


def plain(text):
    """One line of plain text for the page: no Markdown backticks."""
    return " ".join(text.replace("`", "").split())


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build(max_releases):
    """Return (news, partial_error) in the docs/DATA.md claude_code_news format."""
    releases = parse_changelog(fetch(CHANGELOG_URL))
    if not releases:
        raise RuntimeError("changelog had no '## <version>' sections")

    times, dist_tags, partial = {}, {}, None
    try:
        npm = json.loads(fetch(NPM_URL))
        times, dist_tags = npm.get("time", {}), npm.get("dist-tags", {})
    except Exception as e:  # dates are nice to have; the changelog is the source of truth
        partial = f"npm publish dates unavailable: {e}"

    items = []
    for rel in releases[:max_releases]:
        counts, summary = summarize(rel)
        v = rel["version"]
        highlights = [plain(f"{h['area']}: {h['text']}" if h["area"] else h["text"]) for h in pick_highlights(rel["items"])]
        released_at = times.get(v)
        items.append({
            "version": v,
            "date": released_at[:10] if released_at else None,
            "title": title(counts, summary),
            "highlights": [shorten(h, 140) for h in highlights],
            "url": NPM_PAGE.format(version=v) if released_at else CHANGELOG_PAGE,
            # Extras beyond docs/DATA.md; the page ignores fields it doesn't know.
            "released_at": released_at,
            "summary": summary,
            "counts": counts,
        })

    news = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "sample": False,
        "latest_version": items[0]["version"],
        "dist_tags": {k: dist_tags[k] for k in ("latest", "stable", "next") if k in dist_tags},
        "items": items,
    }
    return news, partial


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def append_log(path, entry, cap=60):
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        log = {}
    if log.get("sample"):
        log = {}  # drop placeholder entries the first time real data lands
    entries = [entry] + [e for e in log.get("entries", []) if not e.get("sample")]
    entries.sort(key=lambda e: e.get("at", ""), reverse=True)
    write_json(path, {"schema_version": 1, "generated_at": entries[0]["at"], "entries": entries[:cap]})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data/claude_code_news.json")
    ap.add_argument("--log", default="data/refresh_log.json", help="refresh log to append to; '' to skip")
    ap.add_argument("--releases", type=int, default=8, help="max 8 per docs/DATA.md")
    args = ap.parse_args(argv)
    started = time.monotonic()
    try:
        news, partial = build(min(args.releases, 8))
    except Exception as e:
        # Leave the last good file in place so the dashboard keeps showing it.
        status, message, code, counts = "error", f"failed, kept previous data: {e}", 1, None
    else:
        write_json(args.out, news)
        latest = news["items"][0]
        status = "partial" if partial else "ok"
        message = f"Latest {latest['version']} ({latest['summary']}), {len(news['items'])} releases"
        if partial:
            message += f"; {partial}"
        code, counts = 0, {"releases": len(news["items"])}
    print(f"claude_code_news: {status}: {message}", file=sys.stderr if code else sys.stdout)
    if args.log:
        entry = {"at": now_iso(), "job": "cloud_refresh", "step": "claude_code_news", "status": status,
                 "duration_s": round(time.monotonic() - started, 1), "message": message}
        if counts:
            entry["counts"] = counts
        append_log(args.log, entry)
    return code


if __name__ == "__main__":
    sys.exit(main())
