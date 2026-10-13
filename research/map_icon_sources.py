"""Which game tables put icons on the map: every row field named like *mapIconType* (non-zero), per table.

usage: py -3.12 research/map_icon_sources.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import GAME_DATA, _Table  # noqa: E402

KEY = re.compile(r"mapicon(type|id)$|^iconType$", re.I)
names = {}
try:
    for k, v in _Table("Map/GDSMapText_Noun.json").rows.items():
        names[k] = v
except Exception:
    pass


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if KEY.search(k) and isinstance(v, (int, str)) and v not in (0, "None", ""):
                yield f"{path}.{k}", v
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for x in o:
            yield from walk(x, path + "[]")


per = collections.defaultdict(collections.Counter)
for f in sorted(GAME_DATA.rglob("*.json")):
    rel = f.relative_to(GAME_DATA).as_posix()
    if rel.startswith("Menu/GDSMapIconData") or rel.startswith("Menu/GDSMenuIconTexture"):
        continue
    try:
        rows = _Table(rel).rows
    except Exception:
        continue
    for row in rows.values():
        for key, val in walk(row):
            per[re.sub(r"Map_\d{6}", "Map_X", rel) + "  " + key][val] += 1
for k, c in sorted(per.items()):
    print(f"{sum(c.values()):6}  {k}  {dict(c.most_common(12))}")
