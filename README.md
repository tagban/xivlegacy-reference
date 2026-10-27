# XIVLegacy Reference

A player reference for FINAL FANTASY XIV version 1.0 at its last patch, 1.23b: items, recipes,
quests, monsters, NPCs, leves, achievements and zones.

**Community:** questions, testing and news on the [XIVLegacy Discord](https://discord.gg/D9k3khqvy8).

It's also the checklist for the [XIVLegacy server](https://github.com/tagban/xivlegacy-server):
each quest shows whether the server has a script for it yet.

## Related

- [XIVLegacy Server](https://github.com/tagban/xivlegacy-server) and its [documentation](https://github.com/tagban/xivlegacy-server-docs)
- [XIVLegacy client documentation](https://github.com/tagban/xivlegacy-client-docs): protocol, opcodes and client behavior
- [XIVLegacy Launcher](https://github.com/tagban/xivlegacy-launcher)

## Where the data comes from

- **The game:** names, stats, recipes, quests, spawns and zones come from the 1.23b client data the
  XIVLegacy server ships with. `tools/build.py` reads only the game-data tables of a server
  database, never characters or accounts.
- **The client's own files:** icons (`tools/game_icons.py`, GTEX textures → PNG) and item
  descriptions (`tools/game_text.py`, the XOR-0x73 text sheets in `data/0B/45`), and NPC and
  monster names (`tools/game_sheets.py`: each sheet's header of id ranges gives its rows their
  ids), read straight from a 1.23b install.
- **ZAM:** drops, harvesting and leve details come from ZAM's FFXIV database (2010–2012), preserved
  by the Internet Archive. `tools/zam_fetch.py` fetches the archived pages; only factual tables
  are used (no user comments), and each page links back to its archived original.

## Building

```bash
tools/game_icons.py "<1.23b install>"     # icons -> docs/icons
tools/game_text.py "<1.23b install>" <cache dir>
tools/game_sheets.py "<1.23b install>" <server db> <cache dir>
tools/zam_fetch.py <cache dir>            # slow and polite: the Wayback Machine, one page at a time
tools/build.py <server db> [<cache dir>]  # writes docs/data/*.json
python3 -m http.server -d docs            # preview
```

The site is static (`docs/`) and served by GitHub Pages.

A fan project, not affiliated with Square Enix. FINAL FANTASY is a registered trademark of
Square Enix Holdings Co., Ltd.
