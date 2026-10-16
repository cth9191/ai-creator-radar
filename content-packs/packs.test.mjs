import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { checkPack, rankGaps } from "./lib.mjs";
import { prepare } from "./prepare.mjs";
import { finish } from "./finish.mjs";

const x = { schema_version: 1, sample: false, stories: [
  { id: "a", title: "A", heat: 90, summary: "a" },
  { id: "b", title: "B", heat: 60 },
  { id: "c", title: "C", heat: 99 },
] };
const cov = { schema_version: 1, sample: false, stories: [
  { story_id: "a", video_count: 6, gap_score: 30 },
  { story_id: "b", video_count: 0, gap_score: 60 },
] };

const goodPack = (id, extra = {}) => ({
  story_id: id,
  video: { title: "t", thumbnail_text: "x", hook: "h" },
  short: { duration_s: 30, beats: [{ t: "0-3s", line: "l" }] },
  carousel: { slides: Array.from({ length: 5 }, (_, i) => ({ heading: `s${i}`, body: "" })) },
  x_post: "hi",
  ...extra,
});

function dir(files) {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "cp-"));
  for (const [name, data] of Object.entries(files)) fs.writeFileSync(path.join(d, `${name}.json`), JSON.stringify(data));
  return d;
}
const read = (d, name) => JSON.parse(fs.readFileSync(path.join(d, `${name}.json`), "utf8"));

test("rankGaps joins on story id, prefers gap_score, falls back to the page formula", () => {
  assert.deepEqual(rankGaps(x, cov).map((g) => [g.id, g.gapScore]), [["c", 99], ["b", 60], ["a", 30]]);
});

test("checkPack enforces slide count, X post length and required fields", () => {
  assert.deepEqual(checkPack(goodPack("a")), []);
  assert.equal(checkPack(goodPack("a", { carousel: { slides: [{ heading: "x" }] } })).length, 1);
  assert.equal(checkPack(goodPack("a", { x_post: "x".repeat(281) })).length, 1);
  assert.equal(checkPack(goodPack("a", { video: { title: "t" } })).length, 1);
});

test("prepare skips sample inputs", () => {
  assert.match(prepare({ dataDir: dir({ x_trends: { ...x, sample: true }, youtube_coverage: cov }) }).skip, /sample/);
  assert.match(prepare({ dataDir: dir({ x_trends: x }) }).skip, /youtube_coverage/);
});

test("prepare briefs new stories and keeps unchanged ones", () => {
  const d = dir({ x_trends: x, youtube_coverage: cov });
  const first = prepare({ dataDir: d, top: 2 });
  assert.deepEqual(first.gaps.map((g) => g.story_id), ["c", "b"]);
  assert.ok(first.gaps.every((g) => g.brief && !g.keep_existing));
  assert.equal(first.gaps[1].brief.youtube.video_count, 0);
  // Write a pack for c carrying its fingerprint; it should be kept next time.
  fs.writeFileSync(path.join(d, "content_packs.json"), JSON.stringify({ packs: [goodPack("c", { fingerprint: first.gaps[0].fingerprint })] }));
  const second = prepare({ dataDir: d, top: 2 });
  assert.equal(second.gaps[0].keep_existing.story_id, "c");
  assert.ok(second.gaps[1].brief);
});

test("finish logs a good run and refuses an out-of-spec one without logging", () => {
  const log = { schema_version: 1, generated_at: "2026-10-16T00:00:00Z", entries: [] };
  const d = dir({ refresh_log: log, content_packs: { schema_version: 1, generated_at: "2026-10-16T13:00:00Z", packs: [goodPack("c"), goodPack("b", { x_post: "" })] } });
  const bad = finish({ dataDir: d });
  assert.equal(bad.ok, false);
  assert.match(bad.problems[0], /packs\[1\] b: x_post/);
  assert.equal(read(d, "refresh_log").entries.length, 0);

  fs.writeFileSync(path.join(d, "content_packs.json"), JSON.stringify({ schema_version: 1, generated_at: "2026-10-16T13:00:00Z", packs: [goodPack("c"), goodPack("b")] }));
  assert.equal(finish({ dataDir: d, written: 1, kept: 1 }).ok, true);
  const entry = read(d, "refresh_log").entries[0];
  assert.deepEqual([entry.job, entry.step, entry.status, entry.message], ["cloud_refresh", "content_packs", "ok", "Wrote 2 pack(s): 1 new, 1 unchanged"]);
  assert.equal(read(d, "refresh_log").generated_at, entry.at);
});

test("finish --skip and --error log without reading packs", () => {
  const d = dir({ refresh_log: { schema_version: 1, entries: [] } });
  finish({ dataDir: d, skip: "inputs are still sample data" });
  finish({ dataDir: d, error: "could not write packs" });
  const [e, s] = read(d, "refresh_log").entries;
  assert.equal(s.status, "ok");
  assert.equal(e.status, "error");
});
