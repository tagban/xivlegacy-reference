#!/usr/bin/env python3
"""Export the client's icons (data/1C/59 .. 1C/61) to docs/icons/<id>.png.

The file id is the icon's name (data/1C/61/01/81.DAT -> 1C610181.png, the
same name ZAM used). Exports only the icons the site's data uses (docs/data/items.json), so
run it after tools/build.py.

    tools/game_icons.py "<1.23b install>"
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gtex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "icons")
FOLDERS = ["59", "5A", "5B", "5C", "5D", "5E", "5F", "60", "61", "62"]


def main():
    data = os.path.join(sys.argv[1], "data", "1C")
    os.makedirs(OUT, exist_ok=True)
    used = {i.get("ic") for i in json.load(open(os.path.join(ROOT, "docs", "data", "items.json")))}
    index = []
    for folder in FOLDERS:
        base = os.path.join(data, folder)
        if not os.path.isdir(base):
            continue
        for a in sorted(os.listdir(base)):
            for f in sorted(os.listdir(os.path.join(base, a))):
                if not f.upper().endswith(".DAT"):
                    continue
                code = f"1C{folder}{a}{f[:2]}".upper()
                if code not in used:
                    continue
                got = gtex.read(os.path.join(base, a, f))
                if not got:
                    continue
                w, h, rgba = got
                if w > 256 or h > 256:
                    continue
                target = os.path.join(OUT, f"{code}.png")
                if not os.path.exists(target):
                    with open(target, "wb") as fh:
                        fh.write(gtex.png(w, h, rgba))
                index.append(code)
        print(f"1C/{folder}: {sum(1 for i in index if i[2:4] == folder)}", flush=True)
    print(f"{len(index)} icons")


if __name__ == "__main__":
    main()
