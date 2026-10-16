// Shared helpers for the content pack step. No dependencies.

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export const MAX_PACKS = 5; // docs/DATA.md: up to 5 packs
export const MAX_LOG_ENTRIES = 60;

export const readJsonIfExists = (file) => (fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : null);

export function writeJson(file, data) {
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n");
  fs.renameSync(tmp, file);
}

export const isoNow = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");

// Joins X stories with their YouTube coverage and ranks them as gaps. A story
// with no coverage row yet counts as zero videos. gap_score falls back to the
// same formula the page uses when coverage didn't supply one.
export function rankGaps(xTrends, coverage) {
  const cov = new Map((coverage?.stories ?? []).map((c) => [c.story_id, c]));
  return (xTrends?.stories ?? [])
    .filter((s) => s.id && s.title)
    .map((story) => {
      const c = cov.get(story.id) ?? null;
      const videoCount = c?.video_count ?? 0;
      const gapScore = Number.isFinite(c?.gap_score) ? c.gap_score : Math.round((story.heat ?? 0) / (1 + videoCount / 3));
      return { id: story.id, title: story.title, gapScore, story, coverage: c };
    })
    .sort((a, b) => b.gapScore - a.gapScore);
}

// What the writer needs to know about one gap, trimmed to what matters for
// the angle: the X story, and how many videos exist and what they're called.
export function gapBrief(gap) {
  const { story, coverage } = gap;
  return {
    story_id: gap.id,
    gap_score: gap.gapScore,
    title: story.title,
    summary: story.summary,
    keywords: story.keywords,
    first_seen: story.first_seen,
    x_heat: story.heat,
    x_metrics: story.metrics,
    top_x_posts: (story.top_posts ?? []).map((p) => ({ author: p.author, text: p.text, likes: p.likes, url: p.url })),
    youtube: coverage
      ? {
          video_count: coverage.video_count,
          total_views: coverage.total_views,
          coverage: coverage.coverage,
          existing_videos: (coverage.top_videos ?? []).map((v) => ({ title: v.title, channel: v.channel, views: v.views })),
        }
      : { video_count: 0, coverage: "none" },
  };
}

// Changes when the story, its coverage count or the voice guide changes, so an
// unchanged story keeps its pack instead of being rewritten every run.
export function fingerprint(gap, voice) {
  const key = JSON.stringify({ title: gap.title, summary: gap.story.summary ?? "", videos: gap.coverage?.video_count ?? 0, voice });
  return crypto.createHash("sha256").update(key).digest("hex").slice(0, 16);
}

// The limits docs/DATA.md and scripts/validate-data.mjs enforce, plus the
// pieces the page renders, checked per pack so problems name the story.
export function checkPack(pack) {
  const problems = [];
  if (!pack.story_id) problems.push("missing story_id");
  if (!pack.video?.title || !pack.video?.thumbnail_text || !pack.video?.hook) problems.push("video needs title, thumbnail_text and hook");
  if (!Array.isArray(pack.short?.beats) || !pack.short.beats.length) problems.push("short.beats is empty");
  else if (pack.short.beats.some((b) => !b.t || !b.line)) problems.push("every short beat needs t and line");
  const n = pack.carousel?.slides?.length ?? 0;
  if (n < 5 || n > 8) problems.push(`carousel has ${n} slides (needs 5-8)`);
  else if (pack.carousel.slides.some((s) => !s.heading)) problems.push("every slide needs a heading");
  if (typeof pack.x_post !== "string" || !pack.x_post) problems.push("x_post must be a non-empty string");
  else if (pack.x_post.length > 280) problems.push(`x_post is ${pack.x_post.length} chars (max 280)`);
  return problems;
}

export function appendLog(logFile, entry) {
  const current = readJsonIfExists(logFile) ?? { schema_version: 1, entries: [] };
  const entries = [entry, ...(current.entries ?? [])].slice(0, MAX_LOG_ENTRIES);
  writeJson(logFile, { ...current, schema_version: 1, generated_at: entry.at, entries });
}

export function dataPaths(dataDir) {
  return {
    xTrends: path.join(dataDir, "x_trends.json"),
    coverage: path.join(dataDir, "youtube_coverage.json"),
    packs: path.join(dataDir, "content_packs.json"),
    log: path.join(dataDir, "refresh_log.json"),
    brief: path.join(dataDir, "..", "content-packs", ".brief.json"),
  };
}
