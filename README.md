# XIVLegacy Reference

A player reference for FINAL FANTASY XIV version 1.0 at its last patch, 1.23b: items, recipes,
quests, monsters, NPCs, leves, achievements and zones.

It's also the checklist for the [XIVLegacy server](https://github.com/tagban/xivlegacy-server):
each quest shows whether the server has a script for it yet.

## Where the data comes from

- **The game:** names, stats, recipes, quests, spawns and zones come from the 1.23b client data the
  XIVLegacy server ships with. `tools/build.py` reads only the game-data tables of a server
  database, never characters or accounts.
- **ZAM:** drops, harvesting and leve details come from ZAM's FFXIV database (2010–2012), preserved
  by the Internet Archive. `tools/zam_fetch.py` fetches the archived pages; only factual tables
  are used (no user comments), and each page links back to its archived original.

## Building

```bash
tools/zam_fetch.py <cache dir>            # slow and polite: the Wayback Machine, one page at a time
tools/build.py <server db> [<cache dir>]  # writes docs/data/*.json
python3 -m http.server -d docs            # preview
```

The site is static (`docs/`) and served by GitHub Pages.

A fan project, not affiliated with Square Enix. FINAL FANTASY is a registered trademark of
Square Enix Holdings Co., Ltd.
