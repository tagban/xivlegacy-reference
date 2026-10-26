#!/usr/bin/env python3
"""Fetch ZAM's FFXIV 1.0 database pages from the Wayback Machine.

The live ffxiv.zam.com database is gone; the Internet Archive kept captures
from 2010-2013. For each page kind this lists every captured id, takes the
newest capture, and saves the raw page under the cache folder (not in the
repo). Polite: one request at a time, a pause between requests, backoff on
errors. Rerunning skips pages already saved.

    tools/zam_fetch.py <cache dir> [kind ...]     kinds: item mob quest levelist
"""
import json, os, re, sys, time, urllib.parse, urllib.request

KINDS = {"item": "ffxivitem", "mob": "ffxivmob", "quest": "ffxivquest", "levelist": None}
# Leves only ever had list pages (levelist.html?class=..&page=..): those are
# keyed by their query string instead of an id.
CDX = "https://web.archive.org/cdx/search/cdx"
UA = "xivlegacy-reference/0.1 (FFXIV 1.0 preservation; github.com/tagban)"
PAUSE = 1.2


def get(url, tries=6):
    delay = 5
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # 429, 5xx, timeouts: back off and retry
            print(f"  retry in {delay}s: {e}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 300)
    return None


def captures(kind, param):
    """{id: (timestamp, original url)} with the newest capture per id."""
    q = urllib.parse.urlencode({
        "url": f"ffxiv.zam.com/en/{kind}.html?*", "from": "2010", "to": "2013",
        "fl": "timestamp,original", "filter": "statuscode:200", "output": "json",
    })
    raw = get(f"{CDX}?{q}")
    best = {}
    for ts, orig in json.loads(raw or b"[]")[1:]:
        if param is None:
            query = re.sub(r"&?setcookie=\d+", "", orig.split("?", 1)[1] if "?" in orig else "")
            key = re.sub(r"[^\w=&-]", "_", query)[:120] or "index"
        else:
            m = re.search(param + r"=(\d+)", orig)
            if not m:
                continue
            key = m.group(1)
        if key not in best or ts > best[key][0]:
            best[key] = (ts, orig)
    return best


def main():
    cache = sys.argv[1]
    kinds = sys.argv[2:] or list(KINDS)
    for kind in kinds:
        folder = os.path.join(cache, kind)
        os.makedirs(folder, exist_ok=True)
        index = os.path.join(folder, "_captures.json")
        if os.path.exists(index):
            best = json.load(open(index))
        else:
            best = captures(kind, KINDS[kind])
            json.dump(best, open(index, "w"))
        todo = [i for i in sorted(best) if not os.path.exists(os.path.join(folder, f"{i}.html"))]
        print(f"{kind}: {len(best)} captured, {len(todo)} to fetch", flush=True)
        for n, i in enumerate(todo, 1):
            ts, orig = best[i]
            body = get(f"https://web.archive.org/web/{ts}id_/{orig}")
            if body:
                with open(os.path.join(folder, f"{i}.html"), "wb") as f:
                    f.write(body)
            if n % 100 == 0:
                print(f"  {kind} {n}/{len(todo)}", flush=True)
            time.sleep(PAUSE)


if __name__ == "__main__":
    main()
