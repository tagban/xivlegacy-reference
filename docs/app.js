// XIVLegacy Reference: a static browser over docs/data/*.json.
// Routes: #<section>, #<section>/<id>, #search/<text>.
"use strict";

const D = {};            // loaded data, by section
const IX = {};           // id -> record, by section
const PAGE = 100;
const ZAM = "https://web.archive.org/web/2012/http://ffxiv.zam.com/en/";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const num = (n) => (n == null || n === "" ? "—" : Number(n).toLocaleString("en-US"));
const zone = (id) => (IX.zones[id] ? IX.zones[id].n : id ? `Zone ${id}` : "—");
const link = (sec, id, text) => `<a href="#${sec}/${id}">${esc(text ?? id)}</a>`;
const itemLink = (id) => (IX.items[id] ? link("items", id, IX.items[id].n) : `<span class="empty">item ${id}</span>`);
const zoneLink = (id) => (IX.zones[id] ? link("zones", id, IX.zones[id].n) : esc(zone(id)));
const lv = (a) => (Array.isArray(a) ? (a[0] === a[1] ? a[0] : `${a[0]}–${a[1]}`) : a || "—");

// --- sections --------------------------------------------------------------

const SECTIONS = {
  items: {
    title: "Items", lede: "Every item in the 1.23b client: gear, materials, food, key items.",
    cols: [
      ["Name", (r) => `<span class="name-cell">${icon(r.ic)}${link("items", r.id, r.n)}</span>`, (r) => r.n],
      ["Slot", (r) => esc(r.sl || r.c || ""), (r) => r.sl || r.c || ""],
      ["iLv", (r) => r.il || "", (r) => r.il || 0, "num"],
      ["Equip Lv", (r) => r.el || "", (r) => r.el || 0, "num hide-sm"],
      ["Sell", (r) => (r.sp ? num(r.sp) : ""), (r) => r.sp || 0, "num hide-sm"],
    ],
    filters: [["Slot", (r) => r.sl], ["Type", (r) => r.c]],
    text: (r) => r.n,
  },
  recipes: {
    title: "Recipes", lede: "What each Disciple of the Hand can make, and from what.",
    cols: [
      ["Makes", (r) => itemLink(r.i) + (r.q > 1 ? ` <span class="tag">×${r.q}</span>` : ""), (r) => IX.items[r.i]?.n || ""],
      ["Class", (r) => esc(r.j), (r) => r.j],
      ["Lv", (r) => r.lv, (r) => r.lv, "num"],
      ["Materials", (r) => r.m.map(itemLink).join(", "), (r) => r.m.length, "hide-sm"],
    ],
    filters: [["Class", (r) => r.j]],
    text: (r) => (IX.items[r.i]?.n || "") + " " + r.m.map((m) => IX.items[m]?.n || "").join(" "),
  },
  quests: {
    title: "Quests", lede: "Main scenario, side and guild quests. “On XIVLegacy” marks quests the server has a script for.",
    cols: [
      ["Quest", (r) => link("quests", r.id, r.n), (r) => r.n],
      ["Kind", (r) => esc(r.k), (r) => r.k],
      ["Lv", (r) => r.lv, (r) => r.lv, "num"],
      ["Giver", (r) => (r.giver?.n ? link("npcs", r.giver.id, r.giver.n) : ""), (r) => r.giver?.n || "", "hide-sm"],
      ["On XIVLegacy", (r) => (r.s ? '<span class="tag good">scripted</span>' : '<span class="tag">not yet</span>'), (r) => r.s],
    ],
    filters: [["Kind", (r) => r.k], ["On XIVLegacy", (r) => (r.s ? "scripted" : "not yet")]],
    text: (r) => `${r.n} ${r.code}`,
  },
  monsters: {
    title: "Monsters", lede: "Monster groups by zone with their level range and spawn points.",
    cols: [
      ["Monster", (r) => link("monsters", r.id, r.n), (r) => r.n],
      ["Family", (r) => esc(r.g || ""), (r) => r.g || ""],
      ["Lv", (r) => lv(r.lv), (r) => r.lv[0], "num"],
      ["Zone", (r) => zoneLink(r.z), (r) => zone(r.z)],
      ["Aggressive", (r) => (r.ag ? "Yes" : "No"), (r) => r.ag, "hide-sm"],
    ],
    filters: [["Zone", (r) => zone(r.z)], ["Family", (r) => r.g]],
    text: (r) => `${r.n} ${r.g || ""}`,
  },
  npcs: {
    title: "NPCs", lede: "Townsfolk and quest NPCs with where to find them.",
    cols: [
      ["Name", (r) => link("npcs", r.id, r.n), (r) => r.n],
      ["Zone", (r) => zoneLink(r.z), (r) => zone(r.z)],
      ["Position", (r) => r.p.join(", "), (r) => r.p[0], "hide-sm"],
      ["", (r) => (r.pa ? '<span class="tag">story instance</span>' : ""), (r) => (r.pa ? 1 : 0), "hide-sm"],
    ],
    filters: [["Zone", (r) => zone(r.z)]],
    text: (r) => r.n,
    key: (r) => r.id,
  },
  leves: {
    title: "Leves", lede: "Guildleves from ZAM's archived database.",
    cols: [
      ["Leve", (r) => link("leves", r.id, r.n), (r) => r.n],
      ["Lv", (r) => r.lv || "", (r) => r.lv || 0, "num"],
      ["Zone", (r) => zoneLink(r.z), (r) => zone(r.z)],
    ],
    filters: [],
    text: (r) => r.n,
  },
  harvest: {
    title: "Harvesting", lede: "Gathering nodes and what they yield. “On XIVLegacy” marks nodes the server has placed in the world; most still need placing.",
    cols: [
      ["Node", (r) => link("harvest", r.id, r.n), (r) => r.id],
      ["Grade", (r) => r.gr, (r) => r.gr, "num"],
      ["Yields", (r) => r.y.map((y) => itemLink(y[0])).join(", "), (r) => r.y.length],
      ["On XIVLegacy", (r) => (r.placed.length ? `<span class="tag good">placed: ${r.placed.map(zone).join(", ")}</span>` : '<span class="tag">not placed</span>'), (r) => r.placed.length],
    ],
    filters: [["Grade", (r) => r.gr], ["On XIVLegacy", (r) => (r.placed.length ? "placed" : "not placed")]],
    text: (r) => `${r.n} ${r.y.map((y) => IX.items[y[0]]?.n || "").join(" ")}`,
  },
  achievements: {
    title: "Achievements", lede: "All achievements in 1.23b.",
    cols: [
      ["Achievement", (r) => esc(r.n), (r) => r.n],
      ["Points", (r) => r.pts || "", (r) => r.pts || 0, "num"],
    ],
    filters: [],
    text: (r) => r.n,
  },
  zones: {
    title: "Zones", lede: "Regions, cities and dungeons, with who lives there.",
    cols: [
      ["Zone", (r) => link("zones", r.id, r.n), (r) => r.n],
      ["NPCs", (r) => num(D.npcs.filter((n) => n.z === r.id && !n.pa).length), () => 0, "num"],
      ["Monsters", (r) => num(D.monsters.filter((m) => m.z === r.id).length), () => 0, "num"],
    ],
    filters: [],
    text: (r) => r.n,
  },
};

// --- data ------------------------------------------------------------------

async function load() {
  const names = [...Object.keys(SECTIONS), "meta"];
  const got = await Promise.all(names.map((n) => fetch(`data/${n}.json`).then((r) => (r.ok ? r.json() : n === "meta" ? {} : []))));
  names.forEach((n, i) => (D[n] = got[i]));
  for (const n of Object.keys(SECTIONS)) {
    IX[n] = {};
    for (const r of D[n]) if (!(r.id in IX[n])) IX[n][r.id] = r;
  }
  // relations used by detail pages
  D.madeFrom = {}; D.usedIn = {};
  for (const r of D.recipes) {
    (D.madeFrom[r.i] ||= []).push(r);
    for (const m of r.m) (D.usedIn[m] ||= []).push(r);
  }
}

// --- views -----------------------------------------------------------------

const state = { sort: {}, filter: {}, shown: {} };

function tabs(active) {
  $("#tabs").innerHTML = Object.entries(SECTIONS)
    .filter(([k]) => D[k].length)
    .map(([k, s]) => `<a href="#${k}"${k === active ? ' aria-current="page"' : ""}>${s.title}<span class="n">${num(D[k].length)}</span></a>`)
    .join("");
}

function home() {
  tabs(null);
  const tiles = Object.entries(SECTIONS).filter(([k]) => D[k].length)
    .map(([k, s]) => `<a class="tile" href="#${k}"><b>${s.title}</b><span>${num(D[k].length)}</span><small>${esc(s.lede)}</small></a>`).join("");
  const scripted = D.quests.filter((q) => q.s).length;
  return `<section class="hero"><h1>Eorzea, as it was</h1>
    <p class="lede">A reference for FINAL FANTASY XIV version 1.0 at its last patch, 1.23b: built from the game's own data and the community records ZAM kept from 2010 to 2012. It doubles as the checklist for the <a href="https://github.com/tagban/xivlegacy-server">XIVLegacy server</a>: ${num(scripted)} of ${num(D.quests.length)} quests have a server script so far.</p></section>
    <div class="tiles">${tiles}</div>`;
}

function list(sec, query) {
  const S = SECTIONS[sec];
  tabs(sec);
  let rows = D[sec];
  if (S.key) { const seen = new Set(); rows = rows.filter((r) => !seen.has(S.key(r)) && seen.add(S.key(r))); }
  const f = (state.filter[sec] ||= {});
  const q = (query ?? $("#q").value).trim().toLowerCase();
  const filtered = rows.filter((r) => (!q || S.text(r).toLowerCase().includes(q)) &&
    S.filters.every(([label, fn]) => !f[label] || String(fn(r) ?? "") === f[label]));
  const sort = state.sort[sec];
  if (sort) {
    const key = S.cols[sort.col][2];
    filtered.sort((a, b) => { const x = key(a), y = key(b); return (x > y ? 1 : x < y ? -1 : 0) * sort.dir; });
  }
  const shown = Math.min(filtered.length, state.shown[sec] || PAGE);
  const filterHtml = S.filters.map(([label, fn]) => {
    const vals = [...new Set(rows.map(fn).filter((v) => v != null && v !== ""))].sort();
    return `<label>${label} <select data-filter="${esc(label)}"><option value="">All</option>${vals.map((v) => `<option${f[label] === String(v) ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`;
  }).join("");
  return `<h1>${S.title}</h1><p class="lede">${esc(S.lede)}</p>
    <div class="filters">${filterHtml}<span class="count">${num(filtered.length)} of ${num(rows.length)}</span></div>
    <div class="table-box"><table><thead><tr>${S.cols.map((c, i) => `<th class="${c[3] || ""}" data-col="${i}">${c[0]}${sort?.col === i ? (sort.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
    <tbody>${filtered.slice(0, shown).map((r) => `<tr>${S.cols.map((c) => `<td class="${c[3] || ""}">${c[1](r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    ${shown < filtered.length ? `<button class="more" data-more="${sec}">Show more (${num(filtered.length - shown)} left)</button>` : ""}`;
}

function facts(pairs) {
  return `<dl class="facts">${pairs.filter((p) => p[1] != null && p[1] !== "" && p[1] !== "—" && p[1] !== 0)
    .map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>`;
}

function recipeList(rs) {
  if (!rs?.length) return "";
  return `<ul class="plain">${rs.map((r) => `<li>${itemLink(r.i)}${r.q > 1 ? ` ×${r.q}` : ""} <span class="tag">${esc(r.j)} ${r.lv}</span> from ${r.m.map(itemLink).join(", ")}</li>`).join("")}</ul>`;
}

const DETAIL = {
  items(r) {
    // ZAM's item page: the in-game card, then tabs. ZAM's facts load per item.
    setTimeout(() => itemDetail(r), 0);
    const crumbs = `<a href="#items">Items</a>${r.sl ? ` › <a href="#items" data-slot="${esc(r.sl)}">${esc(r.sl)}</a>` : ""} › ${esc(r.n)}`;
    return `<div class="crumb-path">${crumbs}</div><div class="item-layout"><div id="tt">${card(r, null)}</div><div id="item-tabs" class="item-tabs"></div></div>`;
  },
  quests(r) {
    // ZAM's quest page: infobox, then Journal / Rewards / Related tabs, plus
    // the server script's steps.
    const z = r.zam || {};
    const pre = r.pre ? (IX.quests[r.pre] ? link("quests", r.pre, IX.quests[r.pre].n) : r.pre) : null;
    const next = D.quests.filter((q) => q.pre === r.id);
    const npcRef = (name, id) => (id && IX.npcs[id] ? link("npcs", id, name) : id && D.monsters.find((m) => m.cls === id) ? link("monsters", D.monsters.find((m) => m.cls === id).id, name) : esc(name));
    const start = z.npc ? npcRef(z.npc[0], z.npc[1]) : r.giver?.n ? link("npcs", r.giver.id, r.giver.n) : null;
    const info = [["Rank", z.rank || r.lv], ["Category", esc(z.cat || r.k)], ["Zone", z.zone ? esc(z.zone) : r.giver?.z ? zoneLink(r.giver.z) : null],
      ["Start NPC", start], ["Requires", pre], ["On XIVLegacy", r.s ? '<span class="tag good">scripted</span>' : '<span class="tag warn">no script yet</span>']]
      .filter((x) => x[1] != null && x[1] !== "");
    const steps = r.steps || [];
    const entries = z.journal?.entries || [];
    const journal = entries.length ? `<div class="tt journal"><div class="tt-head"><div><h1>${esc(r.n)}</h1>${z.journal.npc ? `<div class="tt-type">${npcRef(z.journal.npc[0], z.journal.npc[1])}</div>` : ""}</div></div><hr>${entries.map((e) => `<p>${esc(e)}</p>`).join("")}</div>` : "";
    const stepList = steps.length ? `<ol class="steps">${steps.map(([seq, note], k) => `<li><span class="tag">step ${seq}</span> ${esc(note)}${entries[k] && entries.length === steps.length ? `<div class="step-journal">${esc(entries[k])}</div>` : ""}</li>`).join("")}</ol><p class="src">Steps from the XIVLegacy server's quest script.</p>` : "";
    const actors = (r.act || []).map((id) => (IX.npcs[id] ? [link("npcs", id, IX.npcs[id].n), "NPC"] : D.monsters.find((m) => m.cls === id) ? [link("monsters", D.monsters.find((m) => m.cls === id).id, D.monsters.find((m) => m.cls === id).n), "Monster"] : null)).filter(Boolean);
    const relRows = (z.rel || []).map((x) => `<tr><td>${npcRef(x[0], x[1])}</td><td>${esc(x[2])}</td><td>${esc(x[3])}</td><td>${esc(x[4])}</td></tr>`).join("");
    const related = relRows || actors.length ? `${relRows ? `<div class="table-box"><table><thead><tr><th>Name</th><th>Zone</th><th>Role</th><th>Relation</th></tr></thead><tbody>${relRows}</tbody></table></div>` : ""}
      ${actors.length ? `<h2>Named in the server script</h2><ul class="plain">${actors.map(([l, kind]) => `<li>${l} <span class="tag">${kind}</span></li>`).join("")}</ul>` : ""}` : "";
    return `<div class="crumb-path"><a href="#quests">Quests</a> › ${esc(z.cat || r.k)} › ${esc(r.n)}</div>
      <div class="item-layout"><div><div class="card"><h1>${esc(r.n)}</h1><table class="infobox">${info.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("")}</table></div>
        ${next.length ? `<h2>Leads to</h2><ul class="plain">${next.map((q) => `<li>${link("quests", q.id, q.n)}</li>`).join("")}</ul>` : ""}</div>
      <div class="item-tabs">${tabsHtml([
        ["journal", "Journal", journal || (entries.length ? "" : stepList && ""), null],
        ["steps", "Steps", stepList, steps.length],
        ["rewards", "Rewards", z.rewards?.length && `<ul class="plain">${z.rewards.map((w) => `<li><span class="name-cell">${icon(IX.items[w[0]]?.ic)}${itemLink(w[0])}</span>${w[2] && w[2] !== "1" ? ` ×${esc(w[2])}` : ""}</li>`).join("")}</ul>`, z.rewards?.length],
        ["zones", "Related Zones", z.zones?.length && `<ul class="plain">${z.zones.map((x) => `<li>${esc(x[0])} <span class="tag">${esc(x[1])}</span> ${esc(x[2])}</li>`).join("")}</ul>`, z.zones?.length],
        ["related", "Related NPCs / Mobs", related, (z.rel?.length || 0) + actors.length],
      ])}
      <p class="src">${r.zam ? "Rank, journal, rewards and related NPCs from ZAM. " : ""}<a href="${ZAM}quest.html?ffxivquest=${r.id}">ZAM's archived page</a></p></div></div>`;
  },
  monsters(r) {
    const same = D.monsters.filter((m) => m.n === r.n && m.id !== r.id);
    return `<div class="card"><h1>${esc(r.n)}</h1><span class="tag">${esc(r.g || "Monster")}</span>${r.ag ? '<span class="tag warn">aggressive</span>' : ""}
      ${facts([["Level", lv(r.lv)], ["Zone", zoneLink(r.z)], ["Spawn points", r.sp], ["Respawn", r.re ? r.re + " s" : null], ["Family", esc(r.g)]])}</div>
      ${same.length ? `<h2>Also found</h2><ul class="plain">${same.map((m) => `<li>${link("monsters", m.id, m.n)} · ${zoneLink(m.z)} · level ${lv(m.lv)}</li>`).join("")}</ul>` : ""}`;
  },
  npcs(r) {
    const all = D.npcs.filter((n) => n.id === r.id);
    const gives = D.quests.filter((q) => q.giver?.id === r.id);
    return `<div class="card"><h1>${esc(r.n)}</h1>
      ${facts([["Zone", zoneLink(r.z)], ["Position", r.p.join(", ")], ["Class id", r.id]])}</div>
      ${gives.length ? `<h2>Quests</h2><ul class="plain">${gives.map((q) => `<li>${link("quests", q.id, q.n)} <span class="tag">level ${q.lv}</span></li>`).join("")}</ul>` : ""}
      ${all.length > 1 ? `<h2>Appears in</h2><ul class="plain">${all.map((n) => `<li>${zoneLink(n.z)} at ${n.p.join(", ")}${n.pa ? ' <span class="tag">story instance</span>' : ""}</li>`).join("")}</ul>` : ""}`;
  },
  leves(r) {
    return `<div class="card"><h1>${esc(r.n)}</h1>${facts([["Level", r.lv], ["Zone", zoneLink(r.z)], ["Leve id", r.id]])}${r.desc ? `<p>${esc(r.desc)}</p>` : ""}</div>
      <p class="src">From ZAM. <a href="${ZAM}leve.html?ffxivleve=${r.id}">ZAM's archived page</a></p>`;
  },
  harvest(r) {
    return `<div class="card"><h1>${esc(r.n)}</h1>${r.placed.length ? `<span class="tag good">placed on XIVLegacy</span>` : '<span class="tag warn">not placed on XIVLegacy yet</span>'}
      ${facts([["Grade", r.gr], ["Attempts", r.at], ["Placed in", r.placed.map(zoneLink).join(", ") || null]])}</div>
      <h2>Yields</h2><ul class="plain">${r.y.map((y) => `<li>${itemLink(y[0])} <span class="tag">up to ${y[1]}</span></li>`).join("")}</ul>`;
  },
  zones(r) {
    const npcs = D.npcs.filter((n) => n.z === r.id && !n.pa);
    const mobs = D.monsters.filter((m) => m.z === r.id);
    return `<div class="card"><h1>${esc(r.n)}</h1>${facts([["NPCs", num(npcs.length)], ["Monster groups", num(mobs.length)], ["Zone id", r.id]])}</div>
      ${mobs.length ? `<h2>Monsters</h2><ul class="plain">${mobs.sort((a, b) => a.lv[0] - b.lv[0]).map((m) => `<li>${link("monsters", m.id, m.n)} <span class="tag">level ${lv(m.lv)}</span></li>`).join("")}</ul>` : ""}
      ${npcs.length ? `<h2>NPCs</h2><ul class="plain">${npcs.map((n) => `<li>${link("npcs", n.id, n.n)}</li>`).join("")}</ul>` : ""}`;
  },
};

function detail(sec, id) {
  tabs(sec);
  const r = IX[sec]?.[id];
  if (!r || !DETAIL[sec]) return `<p class="empty">Nothing here with id ${esc(id)}.</p>`;
  document.title = `${r.n} · XIVLegacy Reference`;
  const crumb = sec === "items" || sec === "quests" ? "" : `<div class="crumb">${link(sec, "", SECTIONS[sec].title).replace(`#${sec}/`, `#${sec}`)} ›</div>`;
  return crumb + DETAIL[sec](r);
}

function search(text) {
  tabs(null);
  const q = text.trim().toLowerCase();
  if (!q) return home();
  const parts = Object.entries(SECTIONS).map(([k, S]) => {
    const hits = D[k].filter((r) => S.text(r).toLowerCase().includes(q));
    if (!hits.length) return "";
    const uniq = S.key ? [...new Map(hits.map((h) => [S.key(h), h])).values()] : hits;
    return `<h2>${S.title} <span class="tag">${num(uniq.length)}</span></h2><ul class="plain">${uniq.slice(0, 12).map((r) =>
      `<li>${DETAIL[k] ? link(k, r.id, r.n) : esc(r.n)}</li>`).join("")}</ul>${uniq.length > 12 ? `<a href="#${k}" data-carry="${esc(text)}">All ${num(uniq.length)} ${S.title.toLowerCase()} →</a>` : ""}`;
  }).join("");
  return `<h1>Search: ${esc(text)}</h1>${parts || '<p class="empty">No matches.</p>'}`;
}


// --- the item card (ZAM's "xivtt", after the in-game tooltip) -----------------

const icon = (code, alt = "") => (code ? `<img class="icon" src="icons/${esc(code)}.png" alt="${esc(alt)}" loading="lazy" onerror="this.style.visibility='hidden'">` : `<span class="icon"></span>`);

function card(r, z) {
  const tt = z?.tt || {};
  const flags = (tt.flags?.length ? tt.flags : [r.rare && "Unique", r.ex && "Untradable"].filter(Boolean))
    .map((f) => `<span class="tag ${f.toLowerCase()}">${esc(f)}</span>`).join(" ");
  const type = tt.type || r.c || "";
  const desc = (tt.desc || []).map((l) => (/^(Requires|Optimal Rank)/.test(l) ? `<div class="tt-req">${esc(l)}</div>` : `<div>${esc(l)}</div>`)).join("");
  const own = [["Item level", r.il], ["Equip level", r.el], ["Damage", r.w?.dmg], ["Delay", r.w?.dly], ["Attack", r.w?.atk], ["Magic attack", r.w?.matk],
    ["Parry", r.w?.par], ["Defense", r.a?.def], ["Magic defense", r.a?.mdef], ["Evasion", r.a?.eva]].filter((p) => p[1]);
  const stats = tt.stats ? `<table class="tt-stats"><thead><tr>${tt.stats.h.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${tt.stats.rows.map((row) => `<tr>${row.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>` : "";
  const resists = tt.resists ? `<div class="tt-res">${tt.resists.map(([n, v]) => `<span title="${esc(n)}" class="res res-${esc(n.toLowerCase())}">${esc(v)}</span>`).join("")}</div>` : "";
  const rep = tt.repair ? `<table class="tt-foot"><tr>${tt.repair.h.map((h) => `<th>${esc(h)}</th>`).join("")}</tr><tr>${tt.repair.row.map((c) => `<td>${c[1] && IX.items[c[1]] ? link("items", c[1], c[0]) : esc(c[0])}</td>`).join("")}</tr></table>` : "";
  return `<div class="tt">
    <div class="tt-head">${icon(r.ic, r.n)}<div><h1>${esc(r.n)}</h1><div class="tt-type">${esc(type)}</div><div class="tt-flags">${flags}</div></div></div>
    ${tt.base ? `<div class="tt-base">${tt.base.map(esc).join("<br>")}</div>` : ""}
    ${desc ? `<div class="tt-desc">${desc}</div>` : ""}
    ${resists || stats ? `<hr>${resists}${stats}` : ""}
    ${own.length ? `<hr><dl class="tt-own">${own.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>` : ""}
    ${tt.misc ? `<hr><div class="tt-misc">${tt.misc.map(esc).join("<br>")}</div>` : ""}
    ${rep}
    <div class="tt-price">${r.sp ? `Sells for ${num(r.sp)} gil` : "Cannot be sold"}${r.bp ? ` · Buy ${num(r.bp)} gil` : ""}</div>
  </div>`;
}

function tabsHtml(tabs) {
  const live = tabs.filter((t) => t[2]);
  if (!live.length) return "";
  return `<ul class="tablist" role="tablist">${live.map(([id, label, , n], i) => `<li><button role="tab" data-tab="${id}" aria-selected="${i === 0}">${label}${n != null ? ` (${num(n)})` : ""}</button></li>`).join("")}</ul>
    ${live.map(([id, , html], i) => `<div class="tabpane" data-pane="${id}"${i ? " hidden" : ""}>${html}</div>`).join("")}`;
}

async function itemDetail(r) {
  let z = null;
  if (r.zam) {
    try { z = await fetch(`data/item/${r.id}.json`).then((x) => (x.ok ? x.json() : null)); } catch { z = null; }
  }
  const tt = $("#tt"), box = $("#item-tabs");
  if (!tt || !box) return;
  if (z) tt.innerHTML = card(r, z);
  const nodes = D.harvest.filter((h) => h.y.some((y) => y[0] === r.id));
  const mobRow = (d) => { const m = d[3] && D.monsters.find((x) => x.cls === d[3]); return `<tr><td>${m ? link("monsters", m.id, d[0]) : esc(d[0])}</td><td>${esc(d[1])}</td><td class="num">${esc(d[2])}</td></tr>`; };
  box.innerHTML = tabsHtml([
    ["crafted", "Recipe", D.madeFrom[r.id] && recipeList(D.madeFrom[r.id]), D.madeFrom[r.id]?.length],
    ["used", "Used In", D.usedIn[r.id] && recipeList(D.usedIn[r.id]), D.usedIn[r.id]?.length],
    ["drops", "Dropped By", z?.drops?.length && `<div class="table-box"><table><thead><tr><th>Name</th><th>Zone</th><th class="num">Rank</th></tr></thead><tbody>${z.drops.map(mobRow).join("")}</tbody></table></div>`, z?.drops?.length],
    ["harvest", "Harvested From", z?.harvest?.length && `<div class="table-box"><table><thead><tr><th>Node</th><th class="num">Grade</th><th>Zone</th></tr></thead><tbody>${z.harvest.map((h) => `<tr><td>${esc(h[0])}</td><td class="num">${esc(h[1])}</td><td>${esc(h[2])}</td></tr>`).join("")}</tbody></table></div>`, z?.harvest?.length],
    ["sold", "Sold By", z?.sold?.length && `<div class="table-box"><table><thead><tr><th>Vendor</th><th>Zone</th><th class="num">Price</th></tr></thead><tbody>${z.sold.map((v) => `<tr><td>${v[3] && IX.npcs[v[3]] ? link("npcs", v[3], v[0]) : esc(v[0])}</td><td>${esc(v[1])}</td><td class="num">${esc(v[2])}</td></tr>`).join("")}</tbody></table></div>`, z?.sold?.length],
    ["nodes", "Gathering Nodes", nodes.length && `<ul class="plain">${nodes.map((h) => `<li>${link("harvest", h.id, h.n)} <span class="tag">grade ${h.gr}</span>${h.placed.length ? ' <span class="tag good">placed</span>' : ' <span class="tag">not placed on XIVLegacy</span>'}</li>`).join("")}</ul>`, nodes.length],
  ]) + `<p class="src">${z ? "Card, drops, harvesting and vendors from ZAM's FFXIV database. " : ""}<a href="${ZAM}item.html?ffxivitem=${r.id}">ZAM's archived page</a></p>`;
}

// --- routing ---------------------------------------------------------------

function render() {
  const h = decodeURIComponent(location.hash.slice(1));
  const [sec, ...rest] = h.split("/");
  const id = rest.join("/");
  document.title = "XIVLegacy Reference";
  let html;
  if (!sec) html = home();
  else if (sec === "search") html = search(id);
  else if (!SECTIONS[sec]) html = home();
  else if (id) html = detail(sec, id);
  else html = list(sec);
  $("#main").innerHTML = html;
}

function wire() {
  let timer;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const [sec, id] = location.hash.slice(1).split("/");
      if (SECTIONS[sec] && !id) { state.shown[sec] = PAGE; $("#main").innerHTML = list(sec); }
      else location.hash = e.target.value.trim() ? `search/${encodeURIComponent(e.target.value.trim())}` : "";
    }, 180);
  });
  $("#main").addEventListener("change", (e) => {
    const sel = e.target.closest("[data-filter]");
    if (!sel) return;
    const sec = location.hash.slice(1).split("/")[0];
    state.filter[sec][sel.dataset.filter] = sel.value;
    state.shown[sec] = PAGE;
    $("#main").innerHTML = list(sec);
  });
  $("#main").addEventListener("click", (e) => {
    const tab = e.target.closest("[data-tab]");
    if (tab) {
      const box = tab.closest(".item-tabs") || tab.closest("main");
      box.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", b === tab));
      box.querySelectorAll("[data-pane]").forEach((p) => (p.hidden = p.dataset.pane !== tab.dataset.tab));
      return;
    }
    const slot = e.target.closest("[data-slot]");
    if (slot) { (state.filter.items ||= {}).Slot = slot.dataset.slot; }
    const th = e.target.closest("th[data-col]");
    const more = e.target.closest("[data-more]");
    const sec = location.hash.slice(1).split("/")[0];
    if (th) {
      const col = +th.dataset.col, cur = state.sort[sec];
      state.sort[sec] = { col, dir: cur?.col === col ? -cur.dir : 1 };
      $("#main").innerHTML = list(sec);
    } else if (more) {
      state.shown[sec] = (state.shown[sec] || PAGE) + PAGE * 3;
      $("#main").innerHTML = list(sec);
    }
  });
  window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
}

load().then(() => { wire(); render(); }).catch((e) => { $("#main").innerHTML = `<p class="empty">Couldn't load the data (${esc(e.message)}).</p>`; });
