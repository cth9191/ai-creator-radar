#!/usr/bin/env node
// Step 3 of writing content packs in the refresh session (see WRITING.md).
//
// Checks data/content_packs.json against docs/DATA.md limits pack by pack, and
// prepends one refresh_log entry (job cloud_refresh, step content_packs).
// If a pack is out of spec it logs nothing, lists the problems and exits 1, so
// they can be fixed and finish.mjs run again. --skip REASON logs a skipped run
// (status ok); --error REASON logs a failed one after restoring the old file.
//
// Usage: node content-packs/finish.mjs [--data-dir DIR] [--written N] [--kept N]
//        node content-packs/finish.mjs --skip REASON | --error REASON

import path from "node:path";
import { fileURLToPath } from "node:url";
import { MAX_PACKS, appendLog, checkPack, dataPaths, isoNow, readJsonIfExists } from "./lib.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export function finish({ dataDir, skip, error, written, kept }) {
  const p = dataPaths(dataDir);
  const entry = (status, message, counts) => ({ at: isoNow(), job: "cloud_refresh", step: "content_packs", status, message, ...(counts ? { counts } : {}) });
  if (skip) {
    appendLog(p.log, entry("ok", `Skipped: ${skip}; kept previous packs`));
    return { ok: true, problems: [] };
  }
  if (error) {
    appendLog(p.log, entry("error", `${error}; kept previous packs`));
    return { ok: true, problems: [] };
  }
  const data = readJsonIfExists(p.packs);
  const problems = [];
  if (!data) problems.push("data/content_packs.json is missing");
  else {
    if (data.schema_version !== 1) problems.push("schema_version must be 1");
    if (Number.isNaN(Date.parse(data.generated_at))) problems.push("generated_at must be ISO 8601");
    const packs = data.packs ?? [];
    if (!packs.length) problems.push("packs is empty");
    if (packs.length > MAX_PACKS) problems.push(`${packs.length} packs (max ${MAX_PACKS})`);
    packs.forEach((pk, i) => checkPack(pk).forEach((m) => problems.push(`packs[${i}] ${pk.story_id ?? "?"}: ${m}`)));
  }
  if (problems.length) return { ok: false, problems };
  const n = data.packs.length;
  const detail = written != null ? `: ${written} new, ${kept ?? n - written} unchanged` : "";
  appendLog(p.log, entry("ok", `Wrote ${n} pack(s)${detail}`, { packs: n, ...(written != null ? { new: written } : {}) }));
  return { ok: true, problems };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opt = (name) => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : undefined);
  const num = (v) => (v == null ? undefined : Number(v));
  const result = finish({
    dataDir: path.resolve(opt("--data-dir") ?? path.join(HERE, "..", "data")),
    skip: opt("--skip"),
    error: opt("--error"),
    written: num(opt("--written")),
    kept: num(opt("--kept")),
  });
  if (!result.ok) {
    console.error("content_packs: fix these, then run finish.mjs again:\n  " + result.problems.join("\n  "));
    process.exit(1);
  }
  console.log("content_packs: OK, logged");
}
