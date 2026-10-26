#!/usr/bin/env python3
"""Read the English text sheets of the 1.23b client (data/0B/45/..).

A sheet file is a run of fields: u16 little-endian length, then 0xFF and a
string XORed with 0x73 (UTF-8, null-terminated); rows are separated by a few
flag bytes. Item rows read: name, singular, plural, flags, description.
The files carry no row ids, so rows are joined to the server's tables by
name (item names are unique enough; ties keep the first).

Writes <out>/game_text.json: {"items": {name: description}, "strings": [...]}.

    tools/game_text.py "<1.23b install>" <out dir>
"""
import json, os, sys

KEY = 0x73


def fields(data):
    """[(offset, string or None)] — None for a non-string byte."""
    out, i, n = [], 0, len(data)
    while i < n:
        size = int.from_bytes(data[i:i + 2], "little")
        if i + 2 < n and data[i + 2] == 0xFF and 0 < size and i + 2 + size <= n:
            raw = bytes(b ^ KEY for b in data[i + 3:i + 2 + size]).rstrip(b"\x00")
            try:
                out.append((i, raw.decode("utf-8")))
            except UnicodeDecodeError:
                out.append((i, None))
            i += 2 + size
        else:
            out.append((i, None))
            i += 1
    return out


def item_rows(fs):
    """Rows shaped name, singular, plural, <flags>, description."""
    strings = [(k, s) for k, (_, s) in enumerate(fs) if s is not None]
    rows = []
    for j in range(len(strings) - 3):
        (k0, a), (k1, b), (k2, c), (k3, d) = strings[j:j + 4]
        if k1 == k0 + 1 and k2 == k1 + 1 and k3 > k2 + 1 and a and b and a.lower() == b.lower() and c:
            rows.append((a, d))
    return rows


def main():
    base = os.path.join(sys.argv[1], "data", "0B", "45")
    descriptions, strings = {}, set()
    for sub in sorted(os.listdir(base)):
        folder = os.path.join(base, sub)
        if not os.path.isdir(folder):
            continue
        for f in sorted(os.listdir(folder)):
            data = open(os.path.join(folder, f), "rb").read()
            fs = fields(data)
            texts = [s for _, s in fs if s]
            if len(texts) < 2:
                continue
            strings.update(t for t in texts if 1 < len(t) < 80 and not t.startswith("["))
            for name, desc in item_rows(fs):
                if desc and desc != "[en]" and name not in descriptions:
                    descriptions[name] = desc
    os.makedirs(sys.argv[2], exist_ok=True)
    with open(os.path.join(sys.argv[2], "game_text.json"), "w") as fh:
        json.dump({"items": descriptions, "strings": sorted(strings)}, fh, ensure_ascii=False)
    print(f"{len(descriptions)} item descriptions, {len(strings)} short strings")


if __name__ == "__main__":
    main()
