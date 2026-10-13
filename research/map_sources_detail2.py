"""Names and kinds for map markers: noun text layout, fast travel, pick point groups per Type, enemy group sample.

usage: py -3.12 research/map_sources_detail2.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import GAME_DATA, _Table  # noqa: E402

noun = _Table("Map/GDSMapText_Noun.json").rows
row = noun.get("name_HugeMap_01")
print("noun keys", list(row.keys()))
print(json.dumps(row, ensure_ascii=False)[:1500])
print()
for k in ("name_WorldMap_000100", "name_WorldMap_100100", "name_HugeMap_02", "name_Map_200000_013"):
    r = noun.get(k, {})
    print(k, [v for kk, v in r.items() if isinstance(v, str) and re.search(r"[A-Za-z]{3}", v) and kk != "ID"][:6])
print("\n== fast travel on Map_200000")
for r in _Table("Map/GDSFastTravel.json").rows.values():
    if r["TargetMapID"] == "Map_200000":
        print(r["ID"]["Name"], r["Title"], r["iconID"], r["Position"])
fp = _Table("Map/Map_200000/Map_200000_GDSMapFuncPoint.json").rows
print("tower_01 pos", fp["FP_map_200000_tower_01"]["Position"])
pp = _Table("Map/Map_200000/Map_200000_GDSMapPickPoint.json").rows
by = collections.defaultdict(collections.Counter)
for r in pp.values():
    by[r["Type"]][re.sub(r"_?\d+$", "", r["GroupID"])] += 1
for t, c in sorted(by.items()):
    print("pick Type", t, c.most_common(6))
en = _Table("Map/Map_200000/Map_200000_GDSMapEnemyPlacementConfig.json").rows
g = [r for r in en.values() if r["subMapId"] == "None"]
print("\n== enemy group sample", json.dumps(g[100], ensure_ascii=False)[:1800])
print("group name prefixes", collections.Counter(re.sub(r"_?\d+$", "", r["GroupID"]["Name"]) for r in g).most_common(12))
