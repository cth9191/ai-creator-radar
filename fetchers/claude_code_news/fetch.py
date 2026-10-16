#!/usr/bin/env python3
"""Claude Code release news for AI Creator Radar.

Reads the public Claude Code changelog (anthropics/claude-code CHANGELOG.md)
and the npm registry's publish times, then writes a summary of the latest
releases as JSON for the dashboard. Standard library only, no API keys.

Usage:
    python3 fetchers/claude_code_news/fetch.py [--out data/claude_code_news.json] [--releases 8]
"""
import argparse
import json
import re
import sys
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


def build(max_releases):
    md = fetch(CHANGELOG_URL)
    releases = parse_changelog(md)
    if not releases:
        raise RuntimeError("changelog had no '## <version>' sections")

    times, dist_tags = {}, {}
    npm_error = None
    try:
        npm = json.loads(fetch(NPM_URL))
        times, dist_tags = npm.get("time", {}), npm.get("dist-tags", {})
    except Exception as e:  # dates are nice to have; the changelog is the source of truth
        npm_error = str(e)

    out_releases = []
    for rel in releases[:max_releases]:
        counts, summary = summarize(rel)
        v = rel["version"]
        out_releases.append({
            "version": v,
            "released_at": times.get(v),
            "url": NPM_PAGE.format(version=v) if v in times else CHANGELOG_PAGE,
            "summary": summary,
            "counts": counts,
            "highlights": pick_highlights(rel["items"]),
            # Everything but bug fixes (counted above), which keep the file small enough for a phone.
            "notable": [it for it in rel["items"] if it["kind"] != "fixed"],
        })

    latest = out_releases[0]
    top = latest["highlights"][0]["text"] if latest["highlights"] else latest["summary"]
    result = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "ok" if npm_error is None else "partial",
        "error": None if npm_error is None else f"npm publish dates unavailable: {npm_error}",
        "sources": [
            {"name": "Claude Code CHANGELOG.md", "url": CHANGELOG_PAGE},
            {"name": "npm @anthropic-ai/claude-code", "url": "https://www.npmjs.com/package/@anthropic-ai/claude-code"},
        ],
        "latest_version": latest["version"],
        "latest_released_at": latest["released_at"],
        "dist_tags": {k: dist_tags[k] for k in ("latest", "stable", "next") if k in dist_tags},
        "headline": f"Claude Code {latest['version']}: {shorten(top, 120)}",
        "releases": out_releases,
    }
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data/claude_code_news.json")
    ap.add_argument("--releases", type=int, default=8)
    args = ap.parse_args(argv)
    try:
        result = build(args.releases)
    except Exception as e:
        # Leave the last good file in place so the dashboard keeps showing it.
        print(f"claude_code_news: failed, keeping previous data: {e}", file=sys.stderr)
        return 1
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, args.out)
    print(f"claude_code_news: wrote {len(result['releases'])} releases, latest {result['latest_version']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
