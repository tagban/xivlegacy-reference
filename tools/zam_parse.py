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
    return {"name": name, "info": info, "tabs": tabs}


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
