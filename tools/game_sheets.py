#!/usr/bin/env python3
"""Read every text sheet of the 1.23b client (data/0B/45) with its row ids.

A sheet is three files in a row: an index (row offsets, not needed here),
the rows (fields: u16 length, 0xFF, string XOR 0x73), and a header of
(first id, count) u32 pairs. Walking the header's id ranges in order gives
each row its id; the row's strings are split evenly into columns.

Each sheet exists once per language. The English copy is told apart by its
"[en]" placeholders, or for name sheets by matching names the server's
spawn data already knows.

Writes <out>/sheets.json: [{"first": id, "rows": {id: [column, ...]}}] for the
English sheets (ids repeat across sheets), and
<out>/npc_names.json: {displayNameId: name}.

    tools/game_sheets.py "<1.23b install>" <server db> <out dir>
"""
import json, os, re, sqlite3, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_text

LANG_TAGS = {"[en]": "en", "[de]": "de", "[fr]": "fr", "[ja]": "ja", "[ｆｒ]": "fr"}


def header(data):
    """[(first id, count)] when the file looks like a sheet header."""
    if len(data) < 8 or len(data) % 8:
        return None
    pairs = struct.unpack("<%dI" % (len(data) // 4), data)
    ranges = list(zip(pairs[0::2], pairs[1::2]))
    prev_end = 0
    for first, count in ranges:
        if count == 0 or count > 100000 or first < prev_end:
            return None
        prev_end = first + count
    return ranges


def language(strings):
    for s in strings:
        if s in LANG_TAGS:
            return LANG_TAGS[s]
    text = " ".join(strings[:400])
    if re.search(r"[぀-ヿ一-鿿]", text):
        return "ja"
    words = re.findall(r"[a-zäöüßéèàç]+", text.lower())
    score = {"en": sum(w in ("the", "of", "and", "to", "you") for w in words),
             "de": sum(w in ("der", "die", "und", "das", "zu", "nicht") for w in words) + text.count("ä") + text.count("ü"),
             "fr": sum(w in ("le", "la", "et", "les", "des", "vous") for w in words) + text.count("é")}
    return max(score, key=score.get) if max(score.values()) else None


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def main():
    base = os.path.join(sys.argv[1], "data", "0B", "45")
    db = sqlite3.connect(f"file:{sys.argv[2]}?mode=ro", uri=True)
    known = dict(db.execute("""SELECT a.displayNameId, s.uniqueId FROM gamedata_actor_class a
                               JOIN server_spawn_locations s ON s.actorClassId = a.id
                               WHERE a.displayNameId > 0 AND s.uniqueId != ''"""))
    files = []
    for sub in sorted(os.listdir(base)):
        folder = os.path.join(base, sub)
        if os.path.isdir(folder):
            files += [os.path.join(folder, f) for f in sorted(os.listdir(folder))]

    sheets = []   # (first id, language, score, rows)
    for prev, path in zip(files, files[1:]):
        if os.path.dirname(prev) != os.path.dirname(path):
            continue
        ranges = header(open(path, "rb").read())
        if not ranges:
            continue
        strings = [s for _, s in game_text.fields(open(prev, "rb").read()) if s is not None]
        total = sum(c for _, c in ranges)
        cols, rem = divmod(len(strings), total)
        if not cols or rem:
            continue
        ids = [first + k for first, count in ranges for k in range(count)]
        rows = {i: strings[n * cols:(n + 1) * cols] for n, i in enumerate(ids)}
        lang = language(strings)
        score = sum(1 for i, uid in known.items() if i in rows and len(norm(rows[i][0])) >= 3 and norm(rows[i][0]) in norm(uid))
        sheets.append((ranges[0][0], lang, score, rows))

    # one English copy per id range. Skip Japanese; then prefer agreement
    # with known spawn names, the "[en]" tag, and the fewest non-English
    # letters (umlauts, accents) — copies don't come in a fixed order.
    chosen = {}
    for first, lang, score, rows in sheets:
        if lang == "ja":
            continue
        text = "".join(c for cols in rows.values() for c in cols)
        foreign = sum(1 for ch in text if ch in "äöüßÄÖÜéèêàâçôûîÉ")
        rank = (score, lang == "en", -foreign)
        if first not in chosen or rank > chosen[first][0]:
            chosen[first] = (rank, rows)
    # name sheets: two columns (name + "NONE", or singular + plural) in the
    # display-name id space; other sheets reuse these ids for other things
    names = {}
    for first, (_, rows) in chosen.items():
        sample = list(rows.values())[:20]
        if 1000000 <= first < 4100000 and sample and all(len(c) == 2 for c in sample):
            for i, cols in rows.items():
                name = cols[0]
                if name and name != "NONE" and not name.startswith("["):
                    names.setdefault(i, name[0].upper() + name[1:])
    out_sheets = [{"first": first, "rows": rows} for first, (_, rows) in sorted(chosen.items())]
    merged = {i: c for sh in out_sheets for i, c in sh["rows"].items()}
    os.makedirs(sys.argv[3], exist_ok=True)
    with open(os.path.join(sys.argv[3], "sheets.json"), "w") as fh:
        json.dump(out_sheets, fh, ensure_ascii=False)
    with open(os.path.join(sys.argv[3], "npc_names.json"), "w") as fh:
        json.dump(names, fh, ensure_ascii=False)
    ok = sum(1 for i, uid in known.items() if i in names and norm(names[i]) and norm(names[i]) in norm(uid))
    print(f"{len(sheets)} sheets ({len(chosen)} English id ranges), {len(merged)} rows; "
          f"{len(names)} NPC names, {ok}/{len(known)} agree with spawn names")


if __name__ == "__main__":
    main()
