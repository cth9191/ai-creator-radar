"use strict";
// AI Creator Radar: reads data/*.json (format in docs/DATA.md) and renders the console.

const FILES = ["x_trends", "youtube_coverage", "content_packs", "claude_code_news", "channel_stats", "refresh_log"];
const REFRESH_TIMES_UTC = [[12, 53], [22, 53]];
const STALE_HOURS = 14;
const TOP_GAPS = 5;
const GAP_MIN = 35;

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : null);
const link = (u, text) => (safeUrl(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener">${text}</a>` : text);
const fmt = (n) => {
  if (typeof n !== "number" || !Number.isFinite(n)) return "–";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  if (a >= 1e4) return Math.round(n / 1e3) + "K";
  if (a >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
  return String(Math.round(n));
};
const hoursSince = (iso) => (Date.now() - Date.parse(iso)) / 36e5;
const ago = (iso) => {
  if (!iso || Number.isNaN(Date.parse(iso))) return "–";
  const h = hoursSince(iso);
  if (h < 1 / 60) return "just now";
  if (h < 1) return Math.round(h * 60) + "m ago";
  if (h < 48) return Math.round(h) + "h ago";
  return Math.round(h / 24) + "d ago";
};
const utcStamp = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(+d) ? "–" : d.toISOString().slice(5, 16).replace("T", " ") + "Z";
};

async function loadAll() {
  const bust = Math.floor(Date.now() / 6e4);
  const out = {};
  await Promise.all(FILES.map(async (f) => {
    try {
      const r = await fetch(`data/${f}.json?v=${bust}`, { cache: "no-store" });
      out[f] = r.ok ? await r.json() : null;
    } catch { out[f] = null; }
  }));
  return out;
}

function buildStories(d) {
  const cov = new Map((d.youtube_coverage?.stories || []).map((s) => [s.story_id, s]));
  const packs = new Map((d.content_packs?.packs || []).map((p) => [p.story_id, p]));
  return (d.x_trends?.stories || []).map((s) => {
    const c = cov.get(s.id) || null;
    const vids = c?.video_count;
    let gap = c?.gap_score;
    if (typeof gap !== "number" && c) gap = Math.round((s.heat || 0) / (1 + (vids || 0) / 3));
    return { ...s, cov: c, pack: packs.get(s.id) || null, gap: typeof gap === "number" ? gap : null };
  });
}

/* ---------- system bar ---------- */
function renderSys(d) {
  const ledFor = (iso, err) => {
    if (!iso) return `<i class="led err"></i>none`;
    const cls = err ? "err" : hoursSince(iso) > STALE_HOURS ? "stale" : "";
    return `<i class="led ${cls}"></i>${ago(iso)}`;
  };
  const entries = d.refresh_log?.entries || [];
  const lastOf = (job) => entries.find((e) => e.job === job);
  const lx = lastOf("x_scan"), lc = lastOf("cloud_refresh");
  $("#sys-x").innerHTML = ledFor(lx?.at || d.x_trends?.generated_at, lx?.status === "error");
  $("#sys-cloud").innerHTML = ledFor(lc?.at || d.youtube_coverage?.generated_at, lc?.status === "error");
  const now = new Date();
  let next = null;
  for (let day = 0; day < 2 && !next; day++) {
    for (const [h, m] of REFRESH_TIMES_UTC) {
      const t = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + day, h, m));
      if (t > now) { next = t; break; }
    }
  }
  const mins = Math.round((next - now) / 6e4);
  $("#sys-next").textContent = `${next.toISOString().slice(11, 16)}Z · ${Math.floor(mins / 60)}h${String(mins % 60).padStart(2, "0")}`;

  let anySample = false;
  document.querySelectorAll("[data-sample]").forEach((el) => {
    const f = d[el.dataset.sample];
    const sample = !f || f.sample === true;
    el.hidden = !sample;
    if (!f) el.textContent = "NO DATA";
    anySample ||= sample;
  });
  $("#sample-banner").hidden = !anySample;
}

function tickClock() {
  $("#clock").textContent = new Date().toISOString().slice(11, 19);
}

/* ---------- gaps hero ---------- */
let selectedId = null;

function renderScope(stories, gapIds) {
  const W = 400, H = 300, L = 34, R = 12, T = 14, B = 34;
  const pw = W - L - R, ph = H - T - B;
  const maxV = Math.max(12, ...stories.map((s) => s.cov?.video_count || 0));
  const sx = (v) => L + (Math.sqrt(v) / Math.sqrt(maxV)) * pw;
  const sy = (h) => T + (1 - h / 100) * ph;
  const zx = sx(3), zy = sy(55);
  let g = `<rect class="zone" x="${L}" y="${T}" width="${zx - L}" height="${zy - T}"/>`;
  g += `<text class="zone-lbl" x="${L + 6}" y="${T + 12}">GAP ZONE</text>`;
  for (const h of [25, 50, 75]) g += `<line class="grid" x1="${L}" x2="${W - R}" y1="${sy(h)}" y2="${sy(h)}"/><text x="${L - 6}" y="${sy(h) + 3}" text-anchor="end">${h}</text>`;
  const ticks = [0, 1, 3, 10, 30, 100, 300].filter((v) => v <= maxV);
  for (const v of ticks) g += `<line class="grid" y1="${T}" y2="${H - B}" x1="${sx(v)}" x2="${sx(v)}"/><text x="${sx(v)}" y="${H - B + 13}" text-anchor="middle">${v}</text>`;
  g += `<line class="axis" x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}"/><line class="axis" x1="${L}" x2="${L}" y1="${T}" y2="${H - B}"/>`;
  g += `<text x="${L + pw / 2}" y="${H - 6}" text-anchor="middle">YOUTUBE VIDEOS →</text>`;
  g += `<text transform="translate(10 ${T + ph / 2}) rotate(-90)" text-anchor="middle">X HEAT →</text>`;
  const order = [...stories].sort((a, b) => gapIds.includes(a.id) - gapIds.includes(b.id));
  for (const s of order) {
    if (!s.cov) continue;
    const rank = gapIds.indexOf(s.id);
    const hot = rank >= 0;
    const x = sx(s.cov.video_count || 0), y = sy(s.heat || 0);
    g += `<g data-id="${esc(s.id)}"><title>${esc(s.title)} · heat ${s.heat} · ${s.cov.video_count} videos</title>`;
    g += `<circle class="pt${hot ? " hot" : ""}${s.id === selectedId ? " sel" : ""}" cx="${x}" cy="${y}" r="${hot ? 7 : 5}"/>`;
    if (hot) g += `<text class="pt-lbl" x="${x + 10}" y="${y + 3}">${rank + 1}</text>`;
    g += `</g>`;
  }
  const svg = $("#scope");
  svg.innerHTML = g;
  svg.querySelectorAll("g[data-id]").forEach((el) => el.addEventListener("click", () => select(el.dataset.id)));
}

function renderGaps(stories) {
  const ranked = stories.filter((s) => s.gap != null).sort((a, b) => b.gap - a.gap);
  let gaps = ranked.filter((s) => s.gap >= GAP_MIN).slice(0, TOP_GAPS);
  if (!gaps.length) gaps = ranked.slice(0, 3);
  const list = $("#gaps");
  if (!stories.length) {
    list.innerHTML = `<li class="empty">No X stories yet. Waiting for the first X scan.</li>`;
  } else if (!gaps.length) {
    list.innerHTML = `<li class="empty">X stories are in, YouTube coverage hasn't been checked yet.</li>`;
  } else {
    list.innerHTML = gaps.map((s, i) => {
      const c = s.cov;
      const covPct = Math.min(100, (Math.sqrt(c.video_count || 0) / Math.sqrt(30)) * 100);
      return `<li><button class="gap${i === 0 ? " top" : ""}" data-id="${esc(s.id)}" aria-pressed="false">
        <div class="gap-score"><b>${s.gap}</b><span>GAP</span></div>
        <div>
          <div class="gap-title">${esc(s.title)}</div>
          <div class="bars">
            <span>X</span><div class="bar x"><i style="width:${Math.max(0, Math.min(100, s.heat || 0))}%"></i></div><em>${s.heat ?? "–"} heat</em>
            <span>YT</span><div class="bar"><i style="width:${covPct}%"></i></div><em>${c.video_count} vids</em>
          </div>
          <div class="gap-meta">
            <span class="cov cov-${esc(c.coverage || "low")}">${esc((c.coverage || "?").toUpperCase())} COVERAGE</span>
            ${s.metrics?.posts ? `<span>${fmt(s.metrics.posts)} posts</span>` : ""}
            ${s.metrics?.views ? `<span>${fmt(s.metrics.views)} views on X</span>` : ""}
            ${s.first_seen ? `<span>since ${ago(s.first_seen)}</span>` : ""}
            ${s.pack ? `<span class="has-pack">■ pack ready</span>` : ""}
          </div>
        </div>
      </button></li>`;
    }).join("");
    list.querySelectorAll(".gap").forEach((b) => b.addEventListener("click", () => select(b.dataset.id, true)));
  }
  return gaps;
}

/* ---------- content pack ---------- */
let state = { stories: [], gaps: [], tab: "video" };

function copyBtn(text) {
  return `<button class="copy" type="button" data-copy="${esc(text)}">COPY</button>`;
}

function thumbText(t) {
  const words = String(t || "").split(/\s+/).filter(Boolean);
  if (words.length < 2) return esc(t);
  const last = words.pop();
  return `${esc(words.join(" "))} <span>${esc(last)}</span>`;
}

function renderPack() {
  const s = state.stories.find((x) => x.id === selectedId);
  const root = $("#pack");
  $("#pack-for").textContent = s ? `for: ${s.title}` : "";
  if (!s) { root.innerHTML = `<p class="empty">Pick a gap above to see its content pack.</p>`; return; }
  const p = s.pack;
  if (!p) { root.innerHTML = `<p class="empty">No content pack for this story yet. Packs are written for the top gaps on each refresh.</p>`; return; }

  const v = p.video || {};
  const beats = p.short?.beats || [];
  const slides = p.carousel?.slides || [];
  const script = beats.map((b) => `[${b.t}] ${b.line}`).join("\n");
  const tabs = [["video", "VIDEO"], ["short", "SHORT · " + (p.short?.duration_s || 30) + "S"], ["carousel", `CAROUSEL · ${slides.length}`], ["x", "X POST"]];
  const xlen = (p.x_post || "").length;

  root.innerHTML = `
    <div class="tabs" role="tablist">${tabs.map(([k, l]) => `<button role="tab" data-tab="${k}" aria-selected="${state.tab === k}">${l}</button>`).join("")}</div>

    <div class="pack-pane" data-pane="video">
      <div class="pack-grid">
        <div class="thumb"><small>THUMBNAIL</small><b>${thumbText(v.thumbnail_text)}</b></div>
        <div>
          <div class="field"><div class="field-lbl">TITLE ${copyBtn(v.title || "")}</div><div class="field-val title">${esc(v.title)}</div></div>
          <div class="field"><div class="field-lbl">THUMBNAIL TEXT ${copyBtn(v.thumbnail_text || "")}</div><div class="field-val">${esc(v.thumbnail_text)}</div></div>
          <div class="field"><div class="field-lbl">OPENING HOOK ${copyBtn(v.hook || "")}</div><div class="field-val">${esc(v.hook)}</div></div>
        </div>
      </div>
    </div>

    <div class="pack-pane" data-pane="short">
      <div class="field-lbl">SCRIPT ${copyBtn(script)}</div>
      <ol class="beats">${beats.map((b) => `<li class="beat"><time>${esc(b.t)}</time><div><p>${esc(b.line)}</p>${b.visual ? `<small>▸ ${esc(b.visual)}</small>` : ""}</div></li>`).join("")}</ol>
    </div>

    <div class="pack-pane" data-pane="carousel">
      <div class="field-lbl">SLIDES · swipe ${copyBtn(slides.map((sl, i) => `${i + 1}. ${sl.heading}\n${sl.body || ""}`).join("\n\n"))}</div>
      <div class="slides">${slides.map((sl, i) => {
        const cls = i === 0 ? "cover" : i === slides.length - 1 ? "cta" : "";
        return `<div class="slide ${cls}"><span class="n">${i + 1}/${slides.length}</span><h4>${esc(sl.heading)}</h4><p>${esc(sl.body)}</p><span class="brandline">CHASE AI</span></div>`;
      }).join("")}</div>
    </div>

    <div class="pack-pane" data-pane="x">
      <div class="xpost">
        <div class="xpost-head"><div class="xpost-av">C</div><div><div class="xpost-name">Chase AI</div><div class="xpost-handle">draft · not posted</div></div></div>
        <div class="xpost-body">${esc(p.x_post)}</div>
        <div class="xpost-foot"><span class="${xlen > 280 ? "over" : ""}">${xlen}/280</span>${copyBtn(p.x_post || "")}</div>
      </div>
    </div>`;

  const showTab = (k) => {
    state.tab = k;
    root.querySelectorAll("[role=tab]").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === k));
    root.querySelectorAll(".pack-pane").forEach((pn) => (pn.hidden = pn.dataset.pane !== k));
  };
  root.querySelectorAll("[role=tab]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  showTab(state.tab);
}

function select(id, scroll) {
  selectedId = id;
  document.querySelectorAll(".gap").forEach((b) => b.setAttribute("aria-pressed", b.dataset.id === id));
  renderScope(state.stories, state.gaps.map((g) => g.id));
  renderPack();
  if (scroll && window.matchMedia("(max-width: 900px)").matches) $("#pack-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- X trends table ---------- */
function renderTrends(d, stories) {
  const x = d.x_trends;
  $("#x-window").textContent = x ? `last ${x.window_hours || 24}h · updated ${ago(x.generated_at)}` : "";
  const t = $("#trends");
  if (!stories.length) { t.innerHTML = `<tr><td class="empty">No X data yet.</td></tr>`; return; }
  t.innerHTML = `<thead><tr><th>STORY</th><th>HEAT</th><th class="num">POSTS</th><th class="num">/HR</th><th class="num">X VIEWS</th><th class="num">YT VIDS</th><th class="num">GAP</th></tr></thead><tbody>` +
    stories.map((s) => {
      const posts = (s.top_posts || []).slice(0, 3).map((p) => link(p.url, `${esc(p.author || "post")} · ${fmt(p.likes)}♥`)).join("");
      return `<tr>
        <td><div class="t-title">${esc(s.title)}</div>${s.summary ? `<div class="t-sum">${esc(s.summary)}</div>` : ""}${posts ? `<div class="t-posts">${posts}</div>` : ""}</td>
        <td><span class="heat"><span class="bar x"><i style="width:${Math.max(0, Math.min(100, s.heat || 0))}%"></i></span>${s.heat ?? "–"}</span></td>
        <td class="num">${fmt(s.metrics?.posts)}</td>
        <td class="num">${fmt(s.metrics?.velocity_per_hour)}</td>
        <td class="num">${fmt(s.metrics?.views)}</td>
        <td class="num">${s.cov ? s.cov.video_count : "–"}</td>
        <td class="num">${s.gap != null ? `<b>${s.gap}</b>` : "–"}</td>
      </tr>`;
    }).join("") + `</tbody>`;
}

/* ---------- channel ---------- */
function renderChannel(d) {
  const c = d.channel_stats, root = $("#channel");
  if (!c) { root.innerHTML = `<p class="empty">No channel stats yet.</p>`; return; }
  const ch = c.channel || {};
  const vids = c.recent_videos || [];
  root.innerHTML = `
    <div class="kpis">
      <div class="kpi"><span>SUBSCRIBERS</span><b>${fmt(ch.subscribers)}</b></div>
      <div class="kpi"><span>TOTAL VIEWS</span><b>${fmt(ch.total_views)}</b></div>
      <div class="kpi"><span>USUAL VIEWS</span><b>${fmt(c.baseline?.median_views)}</b></div>
    </div>
    <ol class="vids">${vids.map((v) => {
      const r = typeof v.vs_baseline === "number" ? v.vs_baseline : null;
      const w = r == null ? 0 : Math.min(100, (r / 3) * 100);
      return `<li class="vid">
        <div><div class="vid-title">${link(v.url, esc(v.title))}</div>
          <div class="vid-meta">${fmt(v.views)} views · ${ago(v.published_at)}${v.is_short ? " · short" : ""}${v.verdict ? ` · ${esc(v.verdict)}` : ""}</div></div>
        <div class="ratio${r != null && r >= 1 ? " up" : ""}" title="vs usual"><i style="width:${w}%"></i><b>${r == null ? "–" : r.toFixed(1) + "×"}</b></div>
      </li>`;
    }).join("")}</ol>
    <div class="ratio-key">Bar: vs usual (line = 1×). ${esc(c.baseline?.description || "")}</div>`;
}

/* ---------- news ---------- */
function renderNews(d) {
  const n = d.claude_code_news, root = $("#news");
  const items = n?.items || [];
  if (!items.length) { root.innerHTML = `<p class="empty">No Claude Code news yet.</p>`; return; }
  root.innerHTML = `<ol class="news">${items.slice(0, 5).map((it, i) => `<li>
    <div class="news-head"><span class="ver">${link(it.url, "v" + esc(String(it.version).replace(/^v/, "")))}</span><span class="news-date">${esc(it.date || "")}</span></div>
    <div class="news-title">${esc(it.title)}</div>
    ${(it.highlights || []).length ? `<ul>${it.highlights.slice(0, i === 0 ? 5 : 2).map((h) => `<li>${esc(typeof h === "string" ? h : h.text)}</li>`).join("")}</ul>` : ""}
    ${it.creator_angle ? `<div class="angle">${esc(it.creator_angle)}</div>` : ""}
  </li>`).join("")}</ol>`;
}

/* ---------- log ---------- */
function renderLog(d) {
  const entries = d.refresh_log?.entries || [];
  $("#log").innerHTML = entries.length ? entries.map((e) => `<li>
    <time>${utcStamp(e.at)}</time>
    <span class="log-job">${esc(e.job)}${e.step ? " · " + esc(e.step) : ""}</span>
    <span class="st-${esc(e.status)}">${esc(String(e.status).toUpperCase())}</span>
    <span class="log-msg">${esc(e.message || "")}${e.duration_s ? ` <span style="color:var(--ink-3)">(${e.duration_s}s)</span>` : ""}</span>
  </li>`).join("") : `<li class="empty">No refreshes logged yet.</li>`;
}

/* ---------- boot ---------- */
async function boot() {
  const d = await loadAll();
  const stories = buildStories(d);
  state.stories = stories;
  renderSys(d);
  state.gaps = renderGaps(stories);
  if (!selectedId || !stories.some((s) => s.id === selectedId)) selectedId = state.gaps[0]?.id || null;
  select(selectedId);
  renderTrends(d, stories);
  renderChannel(d);
  renderNews(d);
  renderLog(d);
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest(".copy");
  if (!b) return;
  try {
    await navigator.clipboard.writeText(b.dataset.copy);
    b.textContent = "COPIED"; b.classList.add("done");
    setTimeout(() => { b.textContent = "COPY"; b.classList.remove("done"); }, 1400);
  } catch { b.textContent = "COPY FAILED"; }
});

tickClock();
setInterval(tickClock, 1000);
boot();
// Pick up a fresh refresh without a reload when the page stays open.
setInterval(boot, 10 * 60 * 1000);
