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
QUEST_KINDS = {"man": "Main Scenario", "etc": "Side Quest", "wld": "Guild / Class",
               "pgl": "Grand Company", "trl": "Tutorial", "dft": "Default Talk"}


def pretty(name):
    """'wharf_rat' -> 'Wharf Rat'; drops a quest prefix like 'man0l1_'."""
    name = re.sub(r"^[a-z]{3}\d[a-z]\d_", "", name or "")
    return " ".join(w[:1].upper() + w[1:] for w in re.split(r"[_\s]+", name) if w)


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


def main():
    db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    zam_dir = sys.argv[2] if len(sys.argv) > 2 else None
    os.makedirs(OUT, exist_ok=True)

    zones = {r["id"]: r["placeName"] for r in rows(db, "SELECT id, placeName FROM server_zones") if r["placeName"] not in (None, "", "--")}
    write("zones", [{"id": k, "n": v} for k, v in sorted(zones.items())])

    # --- items ---------------------------------------------------------------
    weapons = {r["catalogID"]: r for r in rows(db, "SELECT * FROM gamedata_items_weapon")}
    armor = {r["catalogID"]: r for r in rows(db, "SELECT * FROM gamedata_items_armor")}
    items = []
    names = {}
    for r in rows(db, "SELECT * FROM gamedata_items WHERE catalogID > 0 AND name NOT LIKE '[%'"):
        cid = r["catalogID"]
        names[cid] = r["name"]
        it = {"id": cid, "n": r["name"], "c": item_kind(r, weapons, armor),
              "lv": r["level"], "il": r["itemLevel"], "el": r["equipLevel"], "st": r["stackSize"],
              "sp": r["sellPrice"], "bp": r["buyPrice"], "r": r["rarity"],
              "rare": r["isRare"], "ex": r["isExclusive"]}
        if r["repairSkill"]:
            it["rep"] = [r["repairSkill"], r["repairLevel"]]
        w = weapons.get(cid)
        if w and w["damagePower"]:
            it["w"] = {"dmg": w["damagePower"], "dly": w["damageInterval"], "atk": w["attack"],
                       "matk": w["magicAttack"], "par": w["parry"]}
        a = armor.get(cid)
        if a and (a["defense"] or a["magicDefense"] or a["evasion"]):
            it["a"] = {"def": a["defense"], "mdef": a["magicDefense"], "eva": a["evasion"]}
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
    npcs = {}
    for r in rows(db, "SELECT * FROM server_spawn_locations"):
        key = (r["actorClassId"], r["zoneId"], r["privateAreaName"] or "")
        if key in npcs or not r["uniqueId"]:
            continue
        npcs[key] = {"id": r["actorClassId"], "n": r["customDisplayName"] or pretty(r["uniqueId"]),
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
        mobs.append({"id": r["groupId"], "cls": r["actorClassId"], "n": pretty(r["pname"]), "z": r["zoneId"],
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
        quests.append({"id": q["id"], "n": q["questName"], "code": q["className"],
                       "k": QUEST_KINDS.get(code[:3], "Other"), "lv": q["minLevel"],
                       "pre": q["prerequisite"] or None, "s": 1 if text else 0,
                       "giver": {"id": giver, "n": g["n"] if g else None, "z": g["z"] if g else None} if giver else None})

    # --- leves ---------------------------------------------------------------
    leves = []
    for r in rows(db, "SELECT * FROM gamedata_guildleves WHERE name != ''"):
        leves.append({"id": r["id"], "n": r["name"], "lv": r["level"], "z": r["zoneId"],
                      "d": r["difficulty"], "t": r["leveType"], "cls": r["classType"],
                      "exp": r["rewardExp"], "gil": r["rewardGil"], "lim": r["timeLimit"],
                      "items": [r[f"item{i}"] for i in range(1, 5) if r[f"item{i}"]],
                      "mobs": [r[f"mob{i}"] for i in range(1, 5) if r[f"mob{i}"]]})

    achievements = [{"id": r["achievementId"], "n": r["name"], "pts": r["rewardPoints"]}
                    for r in rows(db, "SELECT * FROM gamedata_achievements") if r["name"]]

    if zam_dir:
        merge_zam(zam_dir, items, mobs, quests)

    write("items", items)
    write("recipes", recipes)
    write("npcs", npc_list)
    write("monsters", mobs)
    write("quests", quests)
    write("leves", leves)
    write("achievements", achievements)
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump({"counts": {"items": len(items), "recipes": len(recipes), "npcs": len(npc_list),
                              "monsters": len(mobs), "quests": len(quests), "leves": len(leves),
                              "achievements": len(achievements)},
                   "zam": bool(zam_dir)}, f)


def merge_zam(zam_dir, items, mobs, quests):
    """Merge parsed ZAM facts (tools/zam_parse.py output) when present."""
    path = os.path.join(zam_dir, "parsed.json")
    if not os.path.exists(path):
        print("no parsed ZAM data yet")
        return
    zam = json.load(open(path))

    def rows(page, tab):
        return page.get("tabs", {}).get(tab, {}).get("rows", [])

    by_id = {it["id"]: it for it in items}
    merged = 0
    for cid, page in zam.get("item", {}).items():
        it = by_id.get(int(cid))
        if not it:
            continue
        facts = {}
        drops = [[r[0][0], r[1][0], r[2][0], r[0][1]] for r in rows(page, "Dropped_By") if len(r) >= 3]
        harvest = [[r[1][0], r[2][0], r[3][0]] for r in rows(page, "Harvested_From") if len(r) >= 4]
        if drops:
            facts["drops"] = drops
        if harvest:
            facts["harvest"] = harvest
        if facts:
            it["zam"] = facts
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
        rewards = [[r[0][1], r[0][0], r[4][0] if len(r) > 4 else "1"] for r in rows(page, "Rewards") if r and r[0][1]]
        if rewards:
            z["rewards"] = rewards
        if z:
            q["zam"] = z
    print(f"zam: {merged} items with drops/harvesting, {len(zam.get('quest', {}))} quest pages")


if __name__ == "__main__":
    main()
