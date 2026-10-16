import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { rankGaps, checkPack } from "./generate.mjs";

const ROOT = path.resolve(import.meta.dirname, "..");

// A scratch copy of the repo's data/ so runs never touch the real files.
function scratchData() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cp-"));
  for (const f of ["x_trends.json", "youtube_coverage.json", "refresh_log.json"]) {
    fs.copyFileSync(path.join(ROOT, "data", f), path.join(dir, f));
  }
  return dir;
}

function run(dir, extra = [], env = {}) {
  const e = { ...process.env, ...env };
  if (!("ANTHROPIC_API_KEY" in env)) delete e.ANTHROPIC_API_KEY;
  return execFileSync(process.execPath, ["generate.mjs", "--data-dir", dir, ...extra], { cwd: import.meta.dirname, env: e, encoding: "utf8" });
}

test("rankGaps joins on story id, prefers gap_score, falls back to the page formula", () => {
  const x = { stories: [
    { id: "a", title: "A", heat: 90 },
    { id: "b", title: "B", heat: 60 },
    { id: "c", title: "C", heat: 99 },
  ] };
  const cov = { stories: [{ story_id: "a", video_count: 6, gap_score: 30 }, { story_id: "b", video_count: 0, gap_score: 60 }] };
  const ranked = rankGaps(x, cov);
  assert.deepEqual(ranked.map((g) => [g.id, g.gapScore]), [["c", 99], ["b", 60], ["a", 30]]);
});

test("checkPack enforces the slide count and the X post length", () => {
  const ok = { video: { title: "t", thumbnail_text: "x", hook: "h" }, short: { beats: [{}] }, carousel: { slides: Array(5).fill({}) }, x_post: "hi" };
  assert.deepEqual(checkPack(ok), []);
  assert.equal(checkPack({ ...ok, carousel: { slides: [{}] } }).length, 1);
  assert.equal(checkPack({ ...ok, x_post: "x".repeat(281) }).length, 1);
});

test("dry run writes packs the shared validator accepts", () => {
  const dir = scratchData();
  const out = path.join(dir, "content_packs.json");
  run(dir, ["--dry-run"]);
  const data = JSON.parse(fs.readFileSync(out, "utf8"));
  assert.equal(data.packs.length, 5);
  assert.equal(data.sample, true);
  // The validator reads ROOT/data, so check our file by swapping it in a copy of the repo layout.
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "cp-repo-"));
  fs.cpSync(path.join(ROOT, "scripts"), path.join(repo, "scripts"), { recursive: true });
  fs.cpSync(path.join(ROOT, "data"), path.join(repo, "data"), { recursive: true });
  fs.copyFileSync(out, path.join(repo, "data", "content_packs.json"));
  execFileSync(process.execPath, [path.join(repo, "scripts", "validate-data.mjs")], { cwd: repo });
});

test("sample inputs are skipped without spending API calls, and logged", () => {
  const dir = scratchData();
  run(dir, [], { ANTHROPIC_API_KEY: "not-used" });
  assert.equal(fs.existsSync(path.join(dir, "content_packs.json")), false);
  const entry = JSON.parse(fs.readFileSync(path.join(dir, "refresh_log.json"), "utf8")).entries[0];
  assert.equal(entry.step, "content_packs");
  assert.equal(entry.job, "cloud_refresh");
});

test("without an API key the step keeps previous packs and logs an error", () => {
  const dir = scratchData();
  for (const f of ["x_trends.json", "youtube_coverage.json"]) {
    const p = path.join(dir, f);
    fs.writeFileSync(p, JSON.stringify({ ...JSON.parse(fs.readFileSync(p, "utf8")), sample: false }));
  }
  run(dir);
  assert.equal(fs.existsSync(path.join(dir, "content_packs.json")), false);
  const log = JSON.parse(fs.readFileSync(path.join(dir, "refresh_log.json"), "utf8"));
  assert.equal(log.entries[0].status, "error");
  assert.match(log.entries[0].message, /ANTHROPIC_API_KEY/);
  assert.equal(log.generated_at, log.entries[0].at);
});
