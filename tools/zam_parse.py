#!/usr/bin/env python3
"""Parse cached ZAM pages (tools/zam_fetch.py) into <cache>/parsed.json.

Keeps only the database facts: the page title, the infobox and the tab
tables (drops, harvesting, rewards, related NPCs, ...). User comments and
anything quoted in them are skipped.

    tools/zam_parse.py <cache dir>
"""
import html, json, os, re, sys

TAB_START = re.compile(r'<div id="(\w+?)_t" class="tbcont"[^>]*>')
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<t([dh])[^>]*>(.*?)</t[dh]>", re.S)
HREF = re.compile(r'href="/(?:en|db)/(\w+)\.html\?ffxiv\w+=(\d+)')


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def cell(fragment):
    """(text, linked id) — the id of the first database link in the cell."""
    m = HREF.search(fragment)
    return [text(fragment), int(m.group(2)) if m else None]


def table(fragment):
    head, rows = [], []
    for r in ROW.findall(fragment):
        cells = CELL.findall(r)
        if cells and all(kind == "h" for kind, _ in cells):
            head = [text(c) for _, c in cells]
        elif cells:
            rows.append([cell(c) for _, c in cells])
    return {"h": head, "rows": rows}


def tooltip(page):
    """ZAM's in-game item card ("xivtt"): icon, type, flags, requirements,
    resists, attributes, delay/slot, wear and repair."""
    a = page.find('class="xivtt-inner"')
    if a < 0:
        return None
    b = page.find('class="tabwrapper"', a)
    tt = page[a:b if b > 0 else a + 20000]
    out = {}
    icon = re.search(r'<img src="[^"]*/([0-9A-Fa-f]{8})\.png"', tt)
    if icon:
        out["icon"] = icon.group(1).upper()
    head = re.search(r"</h2>(.*?)<div class=\"xivtt-flags\">(.*?)</div>", tt, re.S)
    if head:
        out["type"] = text(head.group(1))
        out["flags"] = [text(f) for f in re.findall(r"<span[^>]*>(.*?)</span>", head.group(2), re.S)]
    for cls, key in (("xivtt-subhead", "base"), ("xivtt-desc", "desc"), ("xivtt-misc", "misc")):
        m = re.search(rf'<div class="{cls}">(.*?)</div>', tt, re.S)
        if m:
            lines = [text(x) for x in re.split(r"<br\s*/?>", m.group(1))]
            lines = [x for x in lines if x]
            if lines:
                out[key] = lines
    res = re.findall(r'<div class="xivtt-res-\w+" title="([^"]+)"><b>([^<]*)</b>', tt)
    if res and any(v.strip() not in ("0", "") for _, v in res):
        out["resists"] = [[t.replace(" Resistance", ""), v] for t, v in res]
    stats = re.search(r'<div class="xivtt-maininfo">.*?<table>(.*?)</table>', tt, re.S)
    if stats:
        t = table(stats.group(1))
        rows = [[c[0] for c in r] for r in t["rows"] if any(c[0] for c in r)]
        if rows:
            out["stats"] = {"h": t["h"], "rows": rows}
    foot = re.search(r'<table class="wearAndRepair">(.*?)</table>', tt, re.S)
    if foot:
        t = table(foot.group(1))
        if t["rows"]:
            out["repair"] = {"h": t["h"], "row": t["rows"][0]}
    return out


def journal(page):
    """A quest's Journal tab: the in-game journal card (name, NPC, text)."""
    a = page.find('id="Journal_t"')
    if a < 0:
        return None
    seg = page[a:page.find("<script", a)]
    npc = re.search(r'<div class="right i">(.*?)</div>', seg, re.S)
    body = re.search(r'<div class="xivtt-body">(.*?)<div class="clear">', seg, re.S)
    if not body:
        return None
    raw = text(body.group(1))
    # the journal's entries (one per step) run together: ".When" / ".The"
    entries = [e.strip() for e in re.split(r"(?<=[.!?])(?=[A-Z])", raw) if e.strip()]
    return {"npc": cell(npc.group(1)) if npc else None, "entries": entries}


def parse(page):
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    name = text(title.group(1)).split(" :: ")[0] if title else None
    info = {}
    box = re.search(r'<table class="db-infobox[^"]*"[^>]*>(.*?)</table>', page, re.S)
    if box:
        for r in ROW.findall(box.group(1)):
            th = re.search(r"<th[^>]*>(.*?)</th>", r, re.S)
            td = re.search(r"<td[^>]*>(.*?)</td>", r, re.S)
            if th and td:
                info[text(th.group(1))] = cell(td.group(1))
    tabs = {}
    starts = list(TAB_START.finditer(page))
    for n, m in enumerate(starts):
        end = starts[n + 1].start() if n + 1 < len(starts) else len(page)
        body = page[m.end():end]
        if m.group(1) != "Comments" and "<table" in body:
            tabs[m.group(1)] = table(body[: body.find("</table>")])
    return {"name": name, "info": info, "tabs": tabs, "tt": tooltip(page), "journal": journal(page)}


def main():
    cache = sys.argv[1]
    out = {}
    for kind in ("item", "mob", "quest", "leve"):
        folder = os.path.join(cache, kind)
        out[kind] = {}
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith(".html"):
                page = open(os.path.join(folder, f), errors="ignore").read()
                out[kind][f[:-5]] = parse(page)
        print(f"{kind}: {len(out[kind])}")
    with open(os.path.join(cache, "parsed.json"), "w") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)


if __name__ == "__main__":
    main()
