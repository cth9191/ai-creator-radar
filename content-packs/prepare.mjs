#!/usr/bin/env node
// Step 1 of writing content packs in the refresh session (see WRITING.md).
//
// Joins data/x_trends.json with data/youtube_coverage.json, takes the top gaps
// by gap_score and writes content-packs/.brief.json: for each gap, the story
// data to write from, its fingerprint, and the existing pack if the story is
// unchanged and can be kept as is. Prints a short summary.
//
// Usage: node content-packs/prepare.mjs [--data-dir DIR] [--top N]

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { MAX_PACKS, dataPaths, fingerprint, gapBrief, rankGaps, readJsonIfExists, writeJson } from "./lib.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export function prepare({ dataDir, top = MAX_PACKS }) {
  const p = dataPaths(dataDir);
  const xTrends = readJsonIfExists(p.xTrends);
  const coverage = readJsonIfExists(p.coverage);
  const voice = fs.readFileSync(path.join(HERE, "voice.md"), "utf8");
  if (!xTrends) return { skip: "no data/x_trends.json yet" };
  if (xTrends.sample || coverage?.sample || !coverage) {
    return { skip: !coverage ? "no data/youtube_coverage.json yet" : "inputs are still sample data" };
  }
  const previous = new Map((readJsonIfExists(p.packs)?.packs ?? []).map((pk) => [pk.story_id, pk]));
  const gaps = rankGaps(xTrends, coverage).slice(0, top).map((gap) => {
    const fp = fingerprint(gap, voice);
    const prev = previous.get(gap.id);
    const keep = prev && prev.fingerprint === fp ? prev : null;
    return { story_id: gap.id, fingerprint: fp, keep_existing: keep, brief: keep ? undefined : gapBrief(gap) };
  });
  return { gaps };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opt = (name, dflt) => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : dflt);
  const dataDir = path.resolve(opt("--data-dir", path.join(HERE, "..", "data")));
  const result = prepare({ dataDir, top: Number(opt("--top", MAX_PACKS)) });
  const out = path.join(HERE, ".brief.json");
  writeJson(out, { generated_at: new Date().toISOString(), ...result });
  if (result.skip) {
    console.log(`content_packs SKIP: ${result.skip}. Keep the existing data/content_packs.json.`);
  } else {
    const keep = result.gaps.filter((g) => g.keep_existing).length;
    console.log(`content_packs: ${result.gaps.length} gap(s), ${result.gaps.length - keep} to write, ${keep} unchanged. Brief: content-packs/.brief.json`);
    for (const g of result.gaps) console.log(`  ${g.keep_existing ? "keep " : "write"} ${g.story_id}`);
  }
}
