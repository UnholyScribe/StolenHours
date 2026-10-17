"""Details of the map marker sources on one map: func-point icons and names, pick point types, enemy groups, minimap.

usage: py -3.12 research/map_sources_detail.py [map_id]
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import GAME_DATA, _Table  # noqa: E402

m = sys.argv[1] if len(sys.argv) > 1 else "Map_200000"
noun = _Table("Map/GDSMapText_Noun.json").rows
print("noun row sample:", json.dumps(next(iter(noun.items())), ensure_ascii=False)[:300])


def name(tid):
    r = noun.get(tid)
    if not r:
        return tid
    t = r.get("Text") or []
    return (t[0].get("nounSingularForm_en") if t else None) or tid


fp = _Table(f"Map/{m}/{m}_GDSMapFuncPoint.json").rows
print("\n== func points with icons")
for k, r in fp.items():
    if r["mapIconType"]:
        print(r["mapIconType"], k, r["FuncPointType"], name(r["GameIconInfo"].get("textId")), r["AreaID"])
jp = _Table(f"Map/{m}/{m}_GDSMapJumpFuncPointPlacement.json").rows
print("\n== jump points with icons")
for k, r in jp.items():
    if r["mapIconType"]:
        gi = r["gameIconInfoArray"][0] if r["gameIconInfoArray"] else {}
        print(r["mapIconType"], k, name(gi.get("textId")), r["Position"])
pp = _Table(f"Map/{m}/{m}_GDSMapPickPoint.json").rows
print("\n== pick points: Type counts", collections.Counter(r["Type"] for r in pp.values()))
print("   sample", json.dumps(next(iter(pp.values())), ensure_ascii=False)[:1500])
en = _Table(f"Map/{m}/{m}_GDSMapEnemyPlacementConfig.json").rows
print("\n== enemy groups", len(en), "subMap counts", collections.Counter(r["subMapId"] for r in en.values()).most_common(5))
mm = _Table(f"Map/{m}/{m}_GDSMapMinimap.json").rows
for k, r in mm.items():
    print("minimap", k, r["texPath"].split("'")[1].split(".")[0], r["minX"], r["maxX"], r["minY"], r["maxY"], r["mapTextureSizeX"])
wm = [r for r in _Table("Map/GDSWorldMapData.json").rows.values()]
print("\n== world maps")
for r in wm:
    print(r["ID"], r["mapId"], r["MapRegion"], name(r["nameId"]))
