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
    # a leve is shown once something names it (the client data doesn't)
    leves = [lv for lv in leves if lv["n"]]

    write("items", items)
    write("recipes", recipes)
    write("npcs", npc_list)
    write("monsters", mobs)
    write("quests", quests)
    write("leves", leves)
    write("achievements", achievements)
    write("harvest", harvest)
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump({"counts": {"items": len(items), "recipes": len(recipes), "npcs": len(npc_list),
                              "monsters": len(mobs), "quests": len(quests), "leves": len(leves), "harvest": len(harvest),
                              "achievements": len(achievements)},
                   "zam": bool(zam_dir)}, f)


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
            if slot:
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
    by_leve = {lv["id"]: lv for lv in leves}
    for lid, (name, rank, cls) in zam.get("levelist", {}).items():
        lv = by_leve.get(int(lid))
        if lv is None:
            lv = {"id": int(lid), "items": [], "mobs": []}
            leves.append(lv)
            by_leve[lv["id"]] = lv
        lv["n"] = name
        lv["cat"] = cls
        if rank.isdigit():
            lv["lv"] = int(rank)
    print(f"zam: {merged} items with ZAM details, {len(zam.get('quest', {}))} quest pages")


if __name__ == "__main__":
    main()
