#!/usr/bin/env python3
"""Copy the item icons ZAM showed into docs/icons/, so the site needs no
outside host. Takes the icon codes from docs/data/items.json (tools/build.py
computes them from the client's icon numbers); skips icons already copied.
ZAM's image host first, then the Wayback Machine; retries gateway errors.

    tools/zam_icons.py
"""
import json, os, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "icons")
UA = "xivlegacy-reference/0.1 (FFXIV 1.0 preservation; github.com/tagban)"
SOURCES = ["https://zam.zamimg.com/ffxiv/icons/{}.png",
           "https://web.archive.org/web/2012id_/http://zam.zamimg.com/ffxiv/icons/{}.png"]


def fetch(url, tries=3):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                return body if body[:8] == b"\x89PNG\r\n\x1a\n" else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(3 * (n + 1))
        except Exception:
            time.sleep(3 * (n + 1))
    return None


def main():
    items = json.load(open(os.path.join(ROOT, "docs", "data", "items.json")))
    codes = sorted({it.get("ic") for it in items} - {None})
    os.makedirs(OUT, exist_ok=True)
    todo = [c for c in codes if not os.path.exists(os.path.join(OUT, f"{c}.png"))]
    print(f"{len(codes)} icons, {len(todo)} to copy", flush=True)
    missing = []
    for n, code in enumerate(todo, 1):
        body = None
        for src in SOURCES:
            body = fetch(src.format(code))
            if body:
                break
            time.sleep(1)
        if body:
            with open(os.path.join(OUT, f"{code}.png"), "wb") as f:
                f.write(body)
        else:
            missing.append(code)
        if n % 200 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(0.3)
    print(f"done; {len(missing)} not found: {missing[:20]}")


if __name__ == "__main__":
    main()
