#!/usr/bin/env python3
"""NPC display names from the 1.23b client's text sheets.

A name sheet is two files side by side in data/0B/45: an index (u32 row
offsets, a repeated offset marks an empty row) and the rows (name, "NONE").
Row k of a sheet whose ids start at B is display name id B + k + 1. Each
id block (1500001..) has a sheet per language; the English one is the one
whose rows match the names we already know from spawn data (uniqueId).

Writes <out>/npc_names.json: {displayNameId: name}.

    tools/game_names.py "<1.23b install>" <server db> <out dir>
"""
import json, os, re, sqlite3, struct, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_text


def sheet_rows(index_bytes, data_bytes):
    if len(index_bytes) % 4 or len(index_bytes) < 8:
        return None
    off = struct.unpack("<%dI" % (len(index_bytes) // 4), index_bytes)
    if off[0] != 0 or any(b < a for a, b in zip(off, off[1:])):
        return None
    names = [s for _, s in game_text.fields(data_bytes) if s and s != "NONE"]
    rows, it = [], iter(names)
    for k in range(len(off)):
        empty = k + 1 < len(off) and off[k + 1] == off[k]
        rows.append(None if empty else next(it, None))
    return rows


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def main():
    base = os.path.join(sys.argv[1], "data", "0B", "45")
    db = sqlite3.connect(f"file:{sys.argv[2]}?mode=ro", uri=True)
    known = defaultdict(dict)   # block -> {id: uniqueId}
    for dn, uid in db.execute("""SELECT DISTINCT a.displayNameId, s.uniqueId FROM gamedata_actor_class a
                                 JOIN server_spawn_locations s ON s.actorClassId = a.id
                                 WHERE a.displayNameId > 0 AND s.uniqueId != ''"""):
        known[dn // 100000][dn] = uid
    files = []
    for sub in sorted(os.listdir(base)):
        folder = os.path.join(base, sub)
        if os.path.isdir(folder):
            files += [os.path.join(folder, f) for f in sorted(os.listdir(folder))]
    candidates = []
    for a, b in zip(files, files[1:]):
        if os.path.dirname(a) != os.path.dirname(b):
            continue
        rows = sheet_rows(open(a, "rb").read(), open(b, "rb").read())
        if rows and sum(1 for r in rows if r) >= 5:
            candidates.append((b, rows))
    names = {}
    for block, ids in sorted(known.items()):
        start = block * 100000 + 1
        best = None
        for path, rows in candidates:
            hits = sum(1 for dn, uid in ids.items()
                       if 0 <= dn - start < len(rows) and len(norm(rows[dn - start])) >= 3
                       and norm(rows[dn - start]) in norm(uid))
            if hits and (best is None or hits > best[0]):
                best = (hits, path, rows)
        if not best or best[0] < max(2, len(ids) // 3):
            print(f"block {block}: no English sheet found ({len(ids)} known)")
            continue
        hits, path, rows = best
        for k, r in enumerate(rows):
            if r:
                names[start + k] = r
        print(f"block {block}: {os.path.relpath(path, base)} matches {hits}/{len(ids)}, {sum(1 for r in rows if r)} names")
    os.makedirs(sys.argv[3], exist_ok=True)
    with open(os.path.join(sys.argv[3], "npc_names.json"), "w") as fh:
        json.dump(names, fh, ensure_ascii=False)
    print(f"{len(names)} names")


if __name__ == "__main__":
    main()
