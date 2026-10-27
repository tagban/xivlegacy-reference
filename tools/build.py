#!/usr/bin/env python3
"""Build the reference site's data from a XIVLegacy server database.

Reads only the game-data tables (gamedata_*, server_zones, the spawn and
battle-npc tables), never characters or accounts, and writes compact JSON
under docs/data/ for the static site in docs/. With a ZAM cache folder
(tools/zam_fetch.py) it also merges what ZAM's 1.0 database recorded:
drops, harvesting, monster levels and quest details.

    tools/build.py <server db> [zam cache dir]
"""
import json, os, re, sqlite3, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data")
SCRIPTS = "/Volumes/AppStorage/xivlegacy-server-rebuild/scripts/lua/quests"

# Recipe job letters, in Disciple of the Hand class order (ids 29-36).
CRAFT_JOBS = {"A": "Carpenter", "B": "Blacksmith", "C": "Armorer", "D": "Goldsmith",
              "E": "Leatherworker", "F": "Weaver", "G": "Alchemist", "H": "Culinarian"}
ITEM_KINDS = {"StandardItem": "Item", "FoodItem": "Food", "PotionItem": "Medicine", "ToolItem": "Tool",
              "ShieldItem": "Shield", "MateriaItem": "Materia", "MoneyStandard": "Currency",
              "ImportantItemStandard": "Key Item", "EnchantMedicineItem": "Enhancing Medicine",
              "CmnBadStatusItem": "Medicine", "CmnRemoveStatusItem": "Remedy", "CmnGoodStatusItem": "Medicine",
              "RaiseItem": "Revival", "AdditionalEffectEquipItem": "Gear", "SpecialEquipItem": "Gear",
              "EnchantItem": "Enhancement", "DummyItem": "Other"}
# ZAM's item slots, by the client's equipPoint (ZAM's itemlist.html?slot=).
SLOTS = {2: "Shield", 5: "Throwing Weapon", 6: "Pack", 9: "Head", 10: "Undershirt", 11: "Body",
         12: "Undergarment", 13: "Legs", 14: "Hands", 15: "Feet", 16: "Waist", 17: "Neck",
         36: "One-Handed Weapon", 37: "Two-Handed Weapon", 38: "Bow", 39: "Primary Tool",
         40: "Secondary Tool", 42: "Cowl", 43: "Wrist", 44: "Legs", 45: "Ear", 47: "Finger", 49: "Wrist"}
CLASSES = {2: "Pugilist", 3: "Gladiator", 4: "Marauder", 7: "Archer", 8: "Lancer", 22: "Thaumaturge",
           23: "Conjurer", 29: "Carpenter", 30: "Blacksmith", 31: "Armorer", 32: "Goldsmith",
           33: "Leatherworker", 34: "Weaver", 35: "Alchemist", 36: "Culinarian", 39: "Miner",
           40: "Botanist", 41: "Fisher"}
# Item bonus codes: 15001 + the stat's id (food uses 1015001 +). Labels as
# ZAM printed them; checked against ZAM's cards (Dated Cotton Coif, Meat Miq'abob).
STATS = {0: "HP", 1: "MP", 2: "TP", 3: "Strength", 4: "Vitality", 5: "Dexterity", 6: "Intelligence",
         7: "Mind", 8: "Piety", 9: "Fire Resistance", 10: "Ice Resistance", 11: "Wind Resistance",
         12: "Earth Resistance", 13: "Lightning Resistance", 14: "Water Resistance", 15: "Accuracy",
         16: "Evasion", 17: "Attack Power", 18: "Defense", 19: "Critical Hit Rate",
         20: "Critical Hit Evasion", 21: "Critical Hit Potency", 22: "Critical Hit Resilience",
         23: "Attack Magic Potency", 24: "Healing Magic Potency", 25: "Enhancement Magic Potency",
         26: "Enfeebling Magic Potency", 27: "Magic Accuracy", 28: "Magic Evasion", 29: "Craftsmanship",
         30: "Magic Craftsmanship", 31: "Control", 32: "Gathering", 33: "Output", 34: "Perception",
         39: "Parry", 40: "Block Rate", 41: "Block", 48: "Regen", 49: "Refresh", 50: "Store TP",
         51: "Enmity", 53: "Haste", 56: "Reduced Durability Loss", 57: "Spiritbond Gain",
         61: "Movement Speed", 62: "EXP Bonus", 63: "Resting HP", 64: "Resting MP",
         65: "Slashing Resistance", 66: "Piercing Resistance", 67: "Blunt Resistance"}
DAMAGE_TYPES = {1: "Slashing", 2: "Piercing", 3: "Blunt", 4: "Projectile"}


def bonuses(eq):
    out = []
    for i in range(1, 11):
        t, v = eq.get(f"paramBonusType{i}"), eq.get(f"paramBonusValue{i}")
        if t is None or t < 0 or not v:
            continue
        food = t >= 1000000
        code = t - 1000000 if food else t
        # food's 1015063 isn't on ZAM's cards: unverified, left out
        if food and code == 15063:
            continue
        if 15001 <= code <= 15105 and (code - 15001) in STATS:
            out.append([STATS[code - 15001], v])
    return out


QUEST_KINDS = {"man": "Main Scenario", "etc": "Side Quest", "wld": "Guild / Class",
               "pgl": "Grand Company", "trl": "Tutorial", "dft": "Default Talk"}


def pretty(name):
    """'wharf_rat' -> 'Wharf Rat'; drops a quest prefix like 'man0l1_'."""
    name = re.sub(r"^[a-z]{3}\d[a-z]\d_", "", name or "")
    return " ".join(w[:1].upper() + w[1:] for w in re.split(r"[_\s]+", name) if w)


def icon_code(icon):
    """The client's icon number as ZAM named its icon files:
    60001 -> 1C5F0001 (0x1C59 + icon / 10000, then icon % 10000)."""
    if not icon or icon >= 600000:
        return None
    return "%04X%04X" % (0x1C59 + icon // 10000, icon % 10000)


def item_kind(r, weapons, armor):
    raw = (r["category"] or "").split("/")[-1]
    cid = r["catalogID"]
    if raw == "StandardItem" and cid in weapons:
        return "Weapon" if cid < 6000000 else "Tool" if cid < 8000000 else "Gear"
    if raw == "StandardItem" and cid in armor:
        return "Armor"
    return ITEM_KINDS.get(raw, raw)


def rows(db, sql):
    cur = db.execute(sql)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur]


def write(name, data):
    with open(os.path.join(OUT, f"{name}.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    print(f"{name}: {len(data)}")


def quest_scripts():
    """{code: (path, text)} for every quest script in the server tree."""
    found = {}
    for sub in os.listdir(SCRIPTS) if os.path.isdir(SCRIPTS) else []:
        folder = os.path.join(SCRIPTS, sub)
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.endswith(".lua"):
                    found[f[:-4].lower()] = open(os.path.join(folder, f), errors="ignore").read()
    return found


def quest_giver(text):
    """The class id the script's SEQ_ACCEPT arm offers the quest at."""
    arm = re.search(r"sequence\s*==\s*SEQ_ACCEPT\)\s*then(.*?)(?:elseif|end)", text, re.S)
    if not arm:
        return None
    m = re.search(r"SetENpc\(\s*(\w+)\s*,\s*QFLAG_TALK", arm.group(1))
    if not m:
        return None
    const = re.search(rf"^\s*{m.group(1)}\s*=\s*(\d+)", text, re.M)
    return int(const.group(1)) if const else None


def quest_steps(text):
    """The script's step list: SEQ_nnn = n; -- what the player does."""
    steps = []
    for m in re.finditer(r"^\s*SEQ_(\d+)\s*=\s*(\d+)\s*;?\s*--\s*(.+)$", text, re.M):
        note = re.sub(r"\s*Info:.*$", "", m.group(3)).strip()
        steps.append([int(m.group(2)), note])
    return steps


def quest_actors(text):
    """Class ids the script names: ENPC_/BNPC_ constants and NPC tables."""
    ids = set()
    for m in re.finditer(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d{7})\s*;", text, re.M):
        name, val = m.group(1), int(m.group(2))
        if not name.startswith(("MRKR", "SEQ", "FLAG", "CNTR", "COUNTER")) and (1000000 <= val < 1100000 or 2000000 <= val < 3000000):
            ids.add(val)
    return sorted(ids)


def main():
    db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    zam_dir = sys.argv[2] if len(sys.argv) > 2 else None
    os.makedirs(OUT, exist_ok=True)

    zones = {r["id"]: r["placeName"] for r in rows(db, "SELECT id, placeName FROM server_zones") if r["placeName"] not in (None, "", "--")}
    write("zones", [{"id": k, "n": v} for k, v in sorted(zones.items())])

    # --- items ---------------------------------------------------------------
    weapons = {r["catalogID"]: r for r in rows(db, "SELECT * FROM gamedata_items_weapon")}
    equipment = {r["catalogID"]: r for r in rows(db, "SELECT * FROM gamedata_items_equipment")}
    armor = {r["catalogID"]: r for r in rows(db, "SELECT * FROM gamedata_items_armor")}
    items = []
    names = {}
    for r in rows(db, "SELECT * FROM gamedata_items WHERE catalogID > 0 AND name NOT LIKE '[%'"):
        cid = r["catalogID"]
        names[cid] = r["name"]
        it = {"id": cid, "n": r["name"], "c": item_kind(r, weapons, armor),
              "lv": r["level"], "il": r["itemLevel"], "el": r["equipLevel"], "st": r["stackSize"],
              "sp": r["sellPrice"], "bp": r["buyPrice"], "r": r["rarity"],
              "rare": r["isRare"], "ex": r["isExclusive"], "ic": icon_code(r["icon"])}
        eq = equipment.get(cid)
        if eq:
            if eq["equipPoint"] in SLOTS:
                it["sl"] = SLOTS[eq["equipPoint"]]
            b = bonuses(eq)
            if b:
                it["b"] = b
        if r["mainSkill"] in CLASSES:
            it["req"] = CLASSES[r["mainSkill"]]
        if r["durability"]:
            it["dur"] = r["durability"]
        if r["repairSkill"] in CLASSES:
            it["rep"] = [CLASSES[r["repairSkill"]], r["repairItem"], r["repairItemNum"], r["repairLevel"]]
        w = weapons.get(cid)
        if w and w["damagePower"]:
            it["w"] = {"dmg": w["damagePower"], "dly": w["damageInterval"], "atk": w["attack"],
                       "matk": w["magicAttack"], "par": w["parry"], "hits": w["frequency"],
                       "type": DAMAGE_TYPES.get(w["damageAttributeType1"])}
        a = armor.get(cid)
        if a and (a["defense"] or a["magicDefense"] or a["evasion"]):
            it["a"] = {"def": a["defense"], "mdef": a["magicDefense"], "eva": a["evasion"], "res": a["criticalDefense"]}
        items.append({k: v for k, v in it.items() if v not in (None, 0, "", 0.0)} | {"id": cid, "n": r["name"]})

    # --- recipes -------------------------------------------------------------
    recipes = []
    for r in rows(db, "SELECT * FROM gamedata_recipes"):
        if not r["craftedItem"]:
            continue
        mats = [r[f"material{i}"] for i in range(8) if r[f"material{i}"]]
        crystals = [[r[f"crystal{i}ID"], r[f"crystal{i}Quantity"]] for i in range(2) if r[f"crystal{i}ID"]]
        recipes.append({"id": r["id"], "i": r["craftedItem"], "q": r["craftedQuantity"],
                        "j": CRAFT_JOBS.get(r["job"], r["job"]), "lv": r["level"],
                        "m": mats, "cr": crystals})

    # --- npcs ----------------------------------------------------------------
    # names from the client's own name sheets (tools/game_sheets.py) via the
    # actor class's displayNameId; the spawn row's uniqueId when missing
    game_names = {}
    names_path = os.path.join(zam_dir, "npc_names.json") if zam_dir else None
    if names_path and os.path.exists(names_path):
        sheet = json.load(open(names_path))
        for cls, dn in db.execute("SELECT id, displayNameId FROM gamedata_actor_class WHERE displayNameId > 0"):
            if str(dn) in sheet:
                game_names[cls] = sheet[str(dn)]
    npcs = {}
    for r in rows(db, "SELECT * FROM server_spawn_locations"):
        key = (r["actorClassId"], r["zoneId"], r["privateAreaName"] or "")
        if key in npcs or not r["uniqueId"]:
            continue
        npcs[key] = {"id": r["actorClassId"], "n": game_names.get(r["actorClassId"]) or r["customDisplayName"] or pretty(r["uniqueId"]),
                     "z": r["zoneId"], "pa": r["privateAreaName"] or None,
                     "p": [round(r["positionX"], 1), round(r["positionY"], 1), round(r["positionZ"], 1)]}
    npc_list = sorted(npcs.values(), key=lambda n: (n["n"], n["z"]))
    npc_name = {}
    for n in npc_list:
        if not n["pa"]:
            npc_name.setdefault(n["id"], n)
    for n in npc_list:
        npc_name.setdefault(n["id"], n)

    # --- monsters ------------------------------------------------------------
    genus = {r["genusId"]: r["name"] for r in rows(db, "SELECT genusId, name FROM server_battlenpc_genus")}
    spawn_counts = defaultdict(int)
    for r in rows(db, "SELECT groupId FROM server_battlenpc_spawn_locations"):
        spawn_counts[r["groupId"]] += 1
    mobs = []
    for r in rows(db, """SELECT g.*, p.name AS pname, p.genusId, p.aggroType, p.actorClassId
                         FROM server_battlenpc_groups g JOIN server_battlenpc_pools p ON p.poolId = g.poolId"""):
        if not spawn_counts[r["groupId"]]:
            continue
        mobs.append({"id": r["groupId"], "cls": r["actorClassId"], "n": game_names.get(r["actorClassId"]) or pretty(r["pname"]), "z": r["zoneId"],
                     "lv": [r["minLevel"], r["maxLevel"]], "g": genus.get(r["genusId"]),
                     "ag": 1 if r["aggroType"] else 0, "sp": spawn_counts[r["groupId"]],
                     "re": r["respawnTime"], "pa": r["privateAreaName"] or None})

    # --- quests --------------------------------------------------------------
    scripts = quest_scripts()
    qmeta = rows(db, "SELECT * FROM gamedata_quests")
    qname = {q["id"]: q["questName"] for q in qmeta}
    quests = []
    for q in qmeta:
        code = (q["className"] or "").lower()
        text = scripts.get(code)
        giver = quest_giver(text) if text else None
        g = npc_name.get(giver) if giver else None
        extra = {}
        if text:
            steps = quest_steps(text)
            if steps:
                extra["steps"] = steps
            actors = quest_actors(text)
            if actors:
                extra["act"] = actors
        quests.append(extra | {"id": q["id"], "n": q["questName"], "code": q["className"],
                       "k": QUEST_KINDS.get(code[:3], "Other"), "lv": q["minLevel"],
                       "pre": q["prerequisite"] or None, "s": 1 if text else 0,
                       "giver": {"id": giver, "n": g["n"] if g else None, "z": g["z"] if g else None} if giver else None})

    # --- leves ---------------------------------------------------------------
    leves = []
    for r in rows(db, "SELECT * FROM gamedata_guildleves WHERE id > 0"):
        leves.append({"id": r["id"], "n": r["name"] or None, "lv": r["level"], "z": r["zoneId"],
                      "d": r["difficulty"], "t": r["leveType"], "cls": r["classType"],
                      "exp": r["rewardExp"], "gil": r["rewardGil"], "lim": r["timeLimit"],
                      "items": [r[f"item{i}"] for i in range(1, 5) if r[f"item{i}"]],
                      "mobs": [r[f"mob{i}"] for i in range(1, 5) if r[f"mob{i}"]]})

    # --- harvesting ----------------------------------------------------------
    node_items = {r["id"]: r for r in rows(db, "SELECT * FROM gamedata_gather_node_items")}
    placed = defaultdict(list)
    for r in rows(db, "SELECT * FROM server_gather_node_spawns"):
        placed[r["harvestNodeId"]].append(r["zoneId"])
    harvest = []
    for r in rows(db, "SELECT * FROM gamedata_gather_nodes"):
        yields = []
        for i in range(1, 12):
            ref = r.get(f"item{i}")
            if ref not in (None, "", 0) and int(ref) in node_items:
                ni = node_items[int(ref)]
                yields.append([ni["itemCatalogId"], ni["maxYield"]])
        harvest.append({"id": r["id"], "n": f"Node {r['id']}", "gr": r["grade"], "at": r["attempts"],
                        "y": yields, "placed": sorted(set(placed.get(r["id"], [])))})

    achievements = [{"id": r["achievementId"], "n": r["name"], "pts": r["rewardPoints"]}
                    for r in rows(db, "SELECT * FROM gamedata_achievements") if r["name"]]

    if zam_dir:
        merge_zam(zam_dir, items, mobs, quests, leves)
        parsed = os.path.join(zam_dir, "parsed.json")
        if os.path.exists(parsed):
            monster_names = {}
            if names_path and os.path.exists(names_path):
                monster_names = {int(k): v for k, v in json.load(open(names_path)).items()}
            merge_zam_monsters(json.load(open(parsed)), mobs, zam_zone_ids(db), monster_names)
        text = os.path.join(zam_dir, "game_text.json")
        if os.path.exists(text):
            desc = json.load(open(text))["items"]
            for it in items:
                if it["n"] in desc:
                    it["d"] = desc[it["n"]]
    # community sightings (data/sightings.json): monsters seen in era videos
    sight_path = os.path.join(ROOT, "data", "sightings.json")
    sighted_leves = {}
    if os.path.exists(sight_path):
        by_cls = {}
        for m in mobs:
            by_cls.setdefault(m["cls"], []).append(m)
        for sg in json.load(open(sight_path)):
            seen = {"zone": sg["zone"], "video": sg["video"], "t": sg["t"], "note": sg.get("note"), "era": sg.get("era")}
            if sg.get("nm"):
                seen["nm"] = 1
            hits = [m for i in sg["ids"] for m in by_cls.get(i, [])]
            if not hits:
                m = {"id": sg["ids"][0], "cls": sg["ids"][0], "n": sg["name"], "z": sg["zone"], "lv": [0, 0],
                     "sp": 0, "zam": 0}
                mobs.append(m)
                by_cls[m["cls"]] = [m]
                hits = [m]
            for m in hits[:1]:
                m["zz"] = sorted(set(m.get("zz", [])) | {sg["zone"]})
                m.setdefault("seen", []).append(seen)
            if sg.get("leve"):
                sighted_leves[sg["leve"]] = sg["zone"]
        print(f"sightings: {sum(1 for _ in json.load(open(sight_path)))}")

    # a leve is shown once something names it; targets by the game's names
    leves = [lv for lv in leves if lv.get("n")]
    for lv in leves:
        if lv["id"] in sighted_leves and not lv.get("z"):
            lv["z"] = sighted_leves[lv["id"]]
    sheet_names = {}
    if names_path and os.path.exists(names_path):
        sheet_names = json.load(open(names_path))
    for lv in leves:
        targets = [sheet_names.get(str(m)) for m in dict.fromkeys(lv.get("mobs", []))]
        if any(targets):
            lv["tg"] = [[m, t] for m, t in zip(dict.fromkeys(lv["mobs"]), targets) if t]

    write("items", items)
    write("recipes", recipes)
    write("npcs", npc_list)
    write("monsters", mobs)
    write("quests", quests)
    write("leves", leves)
    write("achievements", achievements)
    write("harvest", harvest)
    notes_path = os.path.join(ROOT, "data", "zone_notes.json")
    with open(os.path.join(OUT, "zone_notes.json"), "w") as f:
        json.dump(json.load(open(notes_path)) if os.path.exists(notes_path) else {}, f, ensure_ascii=False)
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump({"counts": {"items": len(items), "recipes": len(recipes), "npcs": len(npc_list),
                              "monsters": len(mobs), "quests": len(quests), "leves": len(leves), "harvest": len(harvest),
                              "achievements": len(achievements)},
                   "zam": bool(zam_dir)}, f)


# ZAM's zone ids -> our zones: a region covers every field zone with its
# internal prefix; cities and dungeons are single places. ZAM filed Limsa
# Lominsa as "Locke's Lie" (2) and Gridania as "Stateroom" (8). The market
# wards (13, 15, 17, 18) can't be tied to one city and stay unlinked.
ZAM_ZONES = {1: ("prefix", "sea0Field"), 2: ("names", "sea0Town01", "sea0Town01a"),
             5: ("prefix", "wil0Field"), 6: ("prefix", "fst0Field"),
             7: ("names", "wil0Town01", "wil0Town01a"), 8: ("names", "fst0Town01", "fst0Town01a"),
             9: ("prefix", "roc0Field"), 10: ("prefix", "lak0Field01"),
             11: ("names", "wil0Dungeon04"), 12: ("names", "wil0Dungeon02"),
             14: ("names", "fst0Dungeon02"), 16: ("names", "sea0Dungeon03"),
             # the wards, by each ZAM zone page's "Connected Zones"
             13: ("names", "fst0Market01"), 15: ("names", "sea0Market01"),
             17: ("names", "wil0Market01"), 18: ("names", "fst0Market01")}
ZAM_ZONE_NAMES = {1: "La Noscea", 2: "Limsa Lominsa", 5: "Thanalan", 6: "The Black Shroud", 7: "Ul'dah",
                  8: "Gridania", 9: "Coerthas", 10: "Mor Dhona", 11: "Copperbell Mines", 12: "Nanawa Mines",
                  13: "Gridania Market Wards", 14: "The Tam-Tara Deepcroft", 15: "Limsa Lominsa Market Wards",
                  16: "Cassiopeia Hollow", 17: "Ul'dah Market Wards", 18: "Gridania Market Wards"}
MONSTER_ROLES = ("Monster", "Notorious Monster", "Leve Monster")


def zam_zone_ids(db):
    names = list(db.execute("SELECT id, zoneName FROM server_zones WHERE zoneName != ''"))
    out = {}
    for zid, rule in ZAM_ZONES.items():
        if rule[0] == "prefix":
            out[zid] = [i for i, n in names if n.startswith(rule[1])]
        else:
            out[zid] = [i for i, n in names if n in rule[1:]]
    return out


def merge_zam_monsters(zam, mobs, zone_map, game_names):
    """ZAM's monster pages: drops and zones for the monsters we spawn, and
    the monsters our server doesn't spawn yet (keyed by class id)."""
    by_cls = {}
    for m in mobs:
        by_cls.setdefault(m["cls"], []).append(m)
    added = 0
    for cls, page in zam.get("mob", {}).items():
        info = page.get("info", {})
        role = (info.get("Role") or [""])[0]
        cls = int(cls)
        if role not in MONSTER_ROLES and not (role == "" and cls >= 2000000):
            continue
        zones = (info.get("Related Zones") or ["", None, []])[2]
        zids = sorted({i for _, z in zones for i in zone_map.get(z, [])})
        znames = [ZAM_ZONE_NAMES.get(z, n) for n, z in zones]
        drops = [r[0][1] for r in page.get("tabs", {}).get("Drops", {}).get("rows", []) if r and r[0][1]]
        rank = (info.get("Rank") or ["-"])[0]
        lv = [int(x) for x in re.findall(r"\d+", rank)][:2]
        facts = {"zz": zids, "zn": znames, "dr": drops,
                 "race": re.sub(r"\s*\[ wiki \]", "", (info.get("Race") or [""])[0]) or None,
                 "el": (info.get("Element") or [None])[0]}
        if cls in by_cls:
            for m in by_cls[cls]:
                m.update({k: v for k, v in facts.items() if v})
        else:
            name = game_names.get(cls) or page.get("name")
            if not name or name.startswith("Not Found"):
                continue
            mobs.append({"id": cls, "cls": cls, "n": name[0].upper() + name[1:], "z": zids[0] if zids else None,
                         "lv": [lv[0], lv[-1]] if lv else [0, 0], "g": facts["race"],
                         "ag": 1 if (info.get("Aggressive") or [""])[0] == "Yes" else 0,
                         "sp": 0, "zam": 1} | {k: v for k, v in facts.items() if v})
            added += 1
            by_cls[cls] = [mobs[-1]]
    # zone pages: every monster ZAM listed there, even without its own page
    for zid, page in zam.get("zone", {}).items():
        zid = int(zid)
        for r in page.get("tabs", {}).get("Related_NPCs___Mobs", {}).get("rows", []):
            if len(r) < 5 or not r[0][1]:
                continue
            cls, role = r[0][1], r[4][0]
            if role not in MONSTER_ROLES and not (role == "" and cls >= 2000000):
                continue
            ours = zone_map.get(zid, [])
            if cls in by_cls:
                for m in by_cls[cls]:
                    m["zz"] = sorted(set(m.get("zz", [])) | set(ours))
                    if ZAM_ZONE_NAMES.get(zid) and ZAM_ZONE_NAMES[zid] not in m.get("zn", []):
                        m["zn"] = m.get("zn", []) + [ZAM_ZONE_NAMES[zid]]
            else:
                lv = [int(x) for x in re.findall(r"\d+", r[2][0])][:2]
                name = game_names.get(cls) or r[0][0]
                mobs.append({"id": cls, "cls": cls, "n": name[0].upper() + name[1:], "z": ours[0] if ours else None,
                             "zz": ours, "zn": [ZAM_ZONE_NAMES.get(zid, r[1][0])], "lv": [lv[0], lv[-1]] if lv else [0, 0],
                             "g": re.sub(r"\s*\[ wiki \]", "", r[5][0]) if len(r) > 5 else None,
                             "ag": 1 if r[3][0] == "Yes" else 0, "sp": 0, "zam": 1})
                by_cls[cls] = [mobs[-1]]
                added += 1
    print(f"zam: monsters enriched, {added} added that the server doesn't spawn")


def merge_zam(zam_dir, items, mobs, quests, leves):
    """Merge parsed ZAM facts (tools/zam_parse.py output) when present."""
    path = os.path.join(zam_dir, "parsed.json")
    if not os.path.exists(path):
        print("no parsed ZAM data yet")
        return
    zam = json.load(open(path))

    def rows(page, tab):
        return page.get("tabs", {}).get(tab, {}).get("rows", [])

    by_id = {it["id"]: it for it in items}
    detail_dir = os.path.join(OUT, "item")
    os.makedirs(detail_dir, exist_ok=True)
    merged = 0
    for cid, page in zam.get("item", {}).items():
        it = by_id.get(int(cid))
        if not it:
            continue
        facts = {}
        tt = page.get("tt") or {}
        if tt:
            facts["tt"] = tt
            if tt.get("icon"):
                it["ic"] = tt["icon"]
            slot = next((m.split("Slot:", 1)[1].strip() for m in tt.get("misc", []) if "Slot:" in m), None)
            if slot and not it.get("sl"):
                it["sl"] = slot
        drops = [[r[0][0], r[1][0], r[2][0], r[0][1]] for r in rows(page, "Dropped_By") if len(r) >= 3]
        harvest = [[r[1][0], r[2][0], r[3][0]] for r in rows(page, "Harvested_From") if len(r) >= 4]
        sold = [[r[0][0], r[1][0], r[-1][0], r[0][1]] for r in rows(page, "Sold_By") if len(r) >= 3]
        if drops:
            facts["drops"] = drops
        if harvest:
            facts["harvest"] = harvest
        if sold:
            facts["sold"] = sold
        if facts:
            with open(os.path.join(detail_dir, f"{cid}.json"), "w") as f:
                json.dump(facts, f, separators=(",", ":"), ensure_ascii=False)
            it["zam"] = 1
            merged += 1

    by_quest = {q["id"]: q for q in quests}
    for qid, page in zam.get("quest", {}).items():
        q = by_quest.get(int(qid))
        if not q:
            continue
        info = page.get("info", {})
        z = {}
        for key, out in (("Category", "cat"), ("Zone", "zone"), ("Rank", "rank")):
            if key in info and info[key][0]:
                z[out] = info[key][0]
        if "Start NPC" in info:
            z["npc"] = info["Start NPC"]
        if page.get("journal"):
            z["journal"] = page["journal"]
        rel = [[r[0][0], r[0][1], r[1][0], r[4][0] if len(r) > 4 else "", r[-1][0]] for r in rows(page, "Related_NPCs___Mobs") if r]
        if rel:
            z["rel"] = rel
        zones_rel = [[r[0][0], r[1][0], r[2][0]] for r in rows(page, "Related_Zones") if len(r) >= 3]
        if zones_rel:
            z["zones"] = zones_rel
        rewards = [[r[0][1], r[0][0], r[4][0] if len(r) > 4 else "1"] for r in rows(page, "Rewards") if r and r[0][1]]
        if rewards:
            z["rewards"] = rewards
        if z:
            q["zam"] = z
    # Leves: the client's leve sheets give names and descriptions by the
    # game's own ids (ZAM's battle-leve ids run one high: its 1003 "Kobold as
    # Ice" is the game's 1002, which targets kobolds). ZAM adds rank and
    # discipline, matched by name.
    by_leve = {lv["id"]: lv for lv in leves}
    game_leves_path = os.path.join(zam_dir, "leves.json")
    if os.path.exists(game_leves_path):
        for lid, text in json.load(open(game_leves_path)).items():
            lv = by_leve.get(int(lid))
            if lv is None:
                lv = {"id": int(lid), "items": [], "mobs": []}
                leves.append(lv)
                by_leve[lv["id"]] = lv
            lv["n"] = text["n"]
            for key in ("d", "client", "obj"):
                if text.get(key) and text[key] not in ("****", " "):
                    lv[key] = text[key]
    by_name = {}
    for lid, (name, rank, cls) in zam.get("levelist", {}).items():
        by_name.setdefault(name, (rank, cls))
    for lv in leves:
        if lv.get("n") in by_name:
            rank, cls = by_name[lv["n"]]
            lv["cat"] = cls
            if rank.isdigit():
                lv["lv"] = int(rank)
    print(f"zam: {merged} items with ZAM details, {len(zam.get('quest', {}))} quest pages")


if __name__ == "__main__":
    main()
