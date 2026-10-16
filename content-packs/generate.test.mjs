import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { normalizeGaps } from "./generate.mjs";

test("normalizeGaps accepts an object or array, sorts by score, tolerates field names", () => {
  const gaps = normalizeGaps({ gaps: [{ headline: "B", score: 0.2 }, { id: "a", title: "A", gap_score: 0.9 }, { nope: 1 }] });
  assert.deepEqual(gaps.map((g) => g.id), ["a", "b"]);
  assert.equal(normalizeGaps([{ title: "x" }]).length, 1);
});

test("dry run writes one pack per top gap from the sample", () => {
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "cp-")), "packs.json");
  execFileSync(process.execPath, ["generate.mjs", "--dry-run", "--top", "2", "--output", out], { cwd: import.meta.dirname });
  const data = JSON.parse(fs.readFileSync(out, "utf8"));
  assert.equal(data.packs.length, 2);
  assert.equal(data.packs[0].gap_id, "sample-open-weights-agent-model");
  for (const p of data.packs) for (const k of ["video", "short", "carousel", "x_post"]) assert.ok(p[k], k);
});

test("without an API key the step exits 0 and writes nothing", () => {
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "cp-")), "packs.json");
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  execFileSync(process.execPath, ["generate.mjs", "--output", out], { cwd: import.meta.dirname, env });
  assert.equal(fs.existsSync(out), false);
});
