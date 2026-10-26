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
      ["Name", (r) => link("items", r.id, r.n), (r) => r.n],
      ["Type", (r) => esc(r.c || ""), (r) => r.c || ""],
      ["iLv", (r) => r.il || "", (r) => r.il || 0, "num"],
      ["Equip Lv", (r) => r.el || "", (r) => r.el || 0, "num hide-sm"],
      ["Sell", (r) => (r.sp ? num(r.sp) : ""), (r) => r.sp || 0, "num hide-sm"],
    ],
    filters: [["Type", (r) => r.c]],
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
    const z = r.zam || {};
    return `<div class="card"><h1>${esc(r.n)}</h1>
      ${r.rare ? '<span class="tag gold">Unique</span>' : ""}${r.ex ? '<span class="tag gold">Untradable</span>' : ""}<span class="tag">${esc(r.c || "Item")}</span>
      ${facts([["Item level", r.il], ["Equip level", r.el], ["Stack", r.st], ["Sells for", r.sp && num(r.sp) + " gil"], ["Buy price", r.bp && num(r.bp) + " gil"],
        ["Damage", r.w?.dmg], ["Delay", r.w?.dly], ["Attack", r.w?.atk], ["Magic attack", r.w?.matk], ["Parry", r.w?.par],
        ["Defense", r.a?.def], ["Magic defense", r.a?.mdef], ["Evasion", r.a?.eva], ["Catalog id", r.id]])}
      ${z.desc ? `<p>${esc(z.desc)}</p>` : ""}</div>
      ${D.madeFrom[r.id] ? `<h2>Crafted by</h2>${recipeList(D.madeFrom[r.id])}` : ""}
      ${D.usedIn[r.id] ? `<h2>Used in ${D.usedIn[r.id].length} recipes</h2>${recipeList(D.usedIn[r.id].slice(0, 60))}` : ""}
      ${z.drops?.length ? `<h2>Dropped by</h2><div class="table-box"><table><thead><tr><th>Monster</th><th>Zone</th><th class="num">Level</th></tr></thead><tbody>${z.drops.map((d) => `<tr><td>${esc(d[0])}</td><td>${esc(d[1])}</td><td class="num">${esc(d[2])}</td></tr>`).join("")}</tbody></table></div>` : ""}
      ${z.harvest?.length ? `<h2>Harvested from</h2><ul class="plain">${z.harvest.map((h) => `<li>${esc(h[0])} · grade ${esc(h[1])} · ${esc(h[2])}</li>`).join("")}</ul>` : ""}
      <p class="src">${z.drops || z.harvest ? "Drops and harvesting from ZAM. " : ""}<a href="${ZAM}item.html?ffxivitem=${r.id}">ZAM's archived page</a></p>`;
  },
  quests(r) {
    const pre = r.pre ? (IX.quests[r.pre] ? link("quests", r.pre, IX.quests[r.pre].n) : r.pre) : null;
    const next = D.quests.filter((q) => q.pre === r.id);
    return `<div class="card"><h1>${esc(r.n)}</h1><span class="tag">${esc(r.k)}</span>${r.s ? '<span class="tag good">scripted on XIVLegacy</span>' : '<span class="tag warn">no server script yet</span>'}
      ${facts([["Level", r.lv], ["Code", esc(r.code)], ["Quest id", r.id], ["Starts with", r.giver?.n ? link("npcs", r.giver.id, r.giver.n) : null],
        ["Where", r.giver?.z ? zoneLink(r.giver.z) : r.zam?.zone ? esc(r.zam.zone) : null], ["Requires", pre], ["ZAM category", r.zam?.cat ? esc(r.zam.cat) : null]])}</div>
      ${r.zam?.rewards?.length ? `<h2>Rewards</h2><ul class="plain">${r.zam.rewards.map((w) => `<li>${itemLink(w[0])}${w[2] && w[2] !== "1" ? ` ×${esc(w[2])}` : ""}</li>`).join("")}</ul>` : ""}
      ${next.length ? `<h2>Leads to</h2><ul class="plain">${next.map((q) => `<li>${link("quests", q.id, q.n)}</li>`).join("")}</ul>` : ""}
      <p class="src"><a href="${ZAM}quest.html?ffxivquest=${r.id}">ZAM's archived page</a></p>`;
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
  return `<div class="crumb">${link(sec, "", SECTIONS[sec].title).replace(`#${sec}/`, `#${sec}`)} ›</div>${DETAIL[sec](r)}`;
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
