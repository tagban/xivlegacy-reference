#!/usr/bin/env python3
"""List the 1.23b client's cutscenes for the Cutscenes section.

    tools/cutscenes.py "<1.23b install>" [<server db>]

Reads the folder names under client/cut and, from each scene file, only
names and counts: the maps it names (e.g. sea_s0_dun06), how many camera
clips it holds, and which client scripts name it. Nothing from the files is
copied: no models, textures, motion or dialogue. Quest names come from
docs/data/quests.json (run tools/build.py first); zone names come from the
server database's server_zones table when one is given (a SQLite file, as
for build.py, or a MariaDB database name via tools/mariadb_export.py's
connection settings).

Writes docs/data/cutscenes.json.
"""
import json, os, re, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data")

# Map file names: <region>_<letter><n>_<kind><nn>, e.g. sea_s0_dun06.
MAP_RE = re.compile(rb"([a-z]{3})_([a-z])([0-9])_([a-z]{3})([0-9]{2})")
REGIONS = {"sea": "La Noscea", "fst": "The Black Shroud", "wil": "Thanalan", "roc": "Coerthas",
           "lak": "Mor Dhona", "ocn": "Rhotano Sea", "prv": "Private area"}
CITY = {"s": "Limsa Lominsa", "f": "Gridania", "w": "Ul'dah"}
TOWNS = {"sea": "Limsa Lominsa", "fst": "Gridania", "wil": "Ul'dah"}
MAP_KINDS = {"fld": "Field", "dun": "Dungeon", "twn": "Town"}
MAP_WORDS = {"ind": "interior", "sip": "ship", "air": "airship landing", "inn": "inn room",
             "gov": "Grand Company office", "hal": "hall", "mlt": "private area", "lin": "map"}

# Name prefixes that aren't quests.
CLASSES = {"alc": "Alchemist", "arc": "Archer", "bsm": "Blacksmith", "cnj": "Conjurer",
           "cul": "Culinarian", "exc": "Marauder", "fsh": "Fisher", "gla": "Gladiator",
           "gld": "Goldsmith", "hrv": "Botanist", "lnc": "Lancer", "min": "Miner",
           "pgl": "Pugilist", "tan": "Leatherworker", "thm": "Thaumaturge", "wdk": "Carpenter",
           "wvr": "Weaver", "arm": "Armorer"}
JOBS = {"whm": "White Mage", "blm": "Black Mage", "pld": "Paladin", "war": "Warrior",
        "mnk": "Monk", "drg": "Dragoon", "brd": "Bard"}
OTHER = {
    "man": "Main scenario", "com": "Grand Company", "gc0": "Grand Company", "etc": "Side quest",
    "sum": "Primal quest", "spl": "Seasonal event",
    "bcn": "Raid: Battle for the Beacon", "ham": "Hamlet Defense", "cho": "Chocobo",
    "drm": "Inn bed dream", "elv": "Lift (elevator)", "rtn": "Retainer", "vsl": "Ferry",
    "zep": "Airship", "wpn": "Weapon", "rad": "Dungeon",
}
# Dungeon scenes (rad0<region><n>): the zone they belong to.
DUNGEONS = {"rad0f3": "The Thousand Maws of Toto-Rak", "rad0r1": "Dzemael Darkhold",
            "rad0r4": "The Aurum Vale", "rad0w5": "Cutter's Cry"}
GC_NATIONS = {"l": "Gcl", "g": "Gcg", "u": "Gcu"}


def zones_from_db(db):
    if not db:
        return {}
    if os.path.isfile(db):
        con = sqlite3.connect(db)
        rows = con.execute("SELECT id, zoneName, placeName FROM server_zones").fetchall()
    else:
        cmd = ["mariadb", "-N", "-B", db, "-e", "SELECT id, zoneName, placeName FROM server_zones"]
        for env, opt in (("DB_USER", "-u"), ("DB_HOST", "-h"), ("DB_PORT", "-P")):
            if os.environ.get(env):
                cmd[1:1] = [opt, os.environ[env]]
        out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        rows = [line.split("\t") for line in out.splitlines() if line.strip()]
    best = {}
    for zid, name, place in rows:
        if not name or name == "NULL":
            continue
        zid = int(zid)
        if name not in best or zid < best[name][0]:
            best[name] = (zid, place)
    return best


def map_label(code, zones):
    """(zone id or None, readable name) for a map file name."""
    m = MAP_RE.fullmatch(code.encode())
    region, letter, n, kind, num = (g.decode() for g in m.groups())
    zone_name = f"{region}{n}{MAP_KINDS.get(kind, '')}{num}" if kind in MAP_KINDS else None
    if zone_name and zone_name in zones:
        zid, place = zones[zone_name]
        return zid, place
    if region == "prv":
        where = CITY.get(letter, "")
        return None, f"{where} {MAP_WORDS.get(kind, 'map')}".strip()
    if region in TOWNS and kind == "ind":
        return None, f"{TOWNS[region]} interiors"
    return None, f"{REGIONS.get(region, region)} {MAP_WORDS.get(kind, MAP_KINDS.get(kind, 'map').lower())}"


def scan_scene(path):
    """Map names, camera clips and numbered shots in one scene file."""
    b = open(path, "rb").read()
    maps = {}
    for m in MAP_RE.finditer(b):
        code = m.group(0).decode()
        maps[code] = maps.get(code, 0) + 1
    clips = b.count(b"SEDBCCB\x00")
    shots = sorted({int(x) for x in re.findall(rb"(?<![a-z0-9])c(\d{2,3})[a-z]?_", b)})
    return sorted(maps, key=lambda k: -maps[k]), clips, (max(shots) if shots else None), len(b)


def script_owners(install, names):
    """Client script classes that name each scene (only class names are kept)."""
    owners = {}
    root = os.path.join(install, "client", "script")
    for d, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".lpb"):
                continue
            b = bytes(c ^ 0x73 for c in open(os.path.join(d, f), "rb").read())
            words = {w.decode("latin1").lower() for w in re.findall(rb"[A-Za-z0-9_]{4,32}", b)}
            hit = words & names
            if not hit:
                continue
            i = b.find(b"_defineClass")
            if i < 0:
                i = b.find(b"_defineBaseClass")
            m = re.search(rb"([A-Za-z][A-Za-z0-9_]{2,40})\x00", b[i + 13:i + 80]) if i >= 0 else None
            if not m:
                continue
            for h in hit:
                owners.setdefault(h, set()).add(m.group(1).decode())
    return owners


def kind_of(name):
    p = name[:3]
    if p in CLASSES:
        return f"Class quest: {CLASSES[p]}"
    if p in JOBS:
        return f"Job quest: {JOBS[p]}"
    if name.startswith("gc"):
        return OTHER["gc0"]
    if p == "rad":
        return f"Dungeon: {DUNGEONS.get(name[:6], 'dungeon')}"
    return OTHER.get(p, "Other")


def main():
    install = sys.argv[1]
    db = sys.argv[2] if len(sys.argv) > 2 else None
    cut_dir = os.path.join(install, "client", "cut")
    names = sorted(n for n in os.listdir(cut_dir) if os.path.isdir(os.path.join(cut_dir, n)))
    zones = zones_from_db(db)
    quests = json.load(open(os.path.join(OUT, "quests.json")))
    by_code = {q["code"].lower(): q for q in quests if q.get("code")}
    owners = script_owners(install, set(names))

    out = []
    for name in names:
        path = os.path.join(cut_dir, name, name)
        rec = {"id": name, "n": name, "k": kind_of(name)}
        if not os.path.isfile(path):
            # client/cut/mot is the shared motion library, not a scene
            rec.update(k="Shared motion library", lib=True)
            out.append(rec)
            continue
        maps, clips, shots, size = scan_scene(path)
        codes = []
        if name[:6] in by_code:
            codes.append(name[:6])
        m = re.fullmatch(r"gc0([13])([0lgu])(\d)\d\d", name)
        if m:
            tier, nation, n = m.groups()
            for letter in (GC_NATIONS if nation == "0" else [nation]):
                codes.append(f"{GC_NATIONS[letter]}{tier}0{n}".lower())
        used_by = []
        for cls in sorted(owners.get(name, ())):
            if cls.lower() in by_code:
                codes.append(cls.lower())
            else:
                used_by.append(cls)
        qs = []
        for c in dict.fromkeys(codes):
            q = by_code.get(c)
            if q and q["id"] not in qs:
                qs.append(q["id"])
        if qs:
            rec["q"] = qs
            first = next(q for q in quests if q["id"] == qs[0])
            rec["qn"] = first["n"]
            rec["qc"] = first["code"]
            rec["lv"] = first.get("lv")
        if used_by:
            rec["by"] = used_by
        rec["maps"] = [[code, *map_label(code, zones)] for code in maps]
        rec["clips"] = clips
        if shots:
            rec["shots"] = shots
        rec["kb"] = round(size / 1024)
        out.append(rec)

    with open(os.path.join(OUT, "cutscenes.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    linked = sum(1 for r in out if r.get("q"))
    mapped = sum(1 for r in out if r.get("maps"))
    print(f"cutscenes: {len(out)} ({linked} linked to quests, {mapped} with a map name)")


if __name__ == "__main__":
    main()
