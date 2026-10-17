"""Row count and first row of the map tables that may place markers (Map_200000 plus the shared ones).

usage: py -3.12 research/map_tables_peek.py [map_id]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import GAME_DATA, _Table  # noqa: E402

m = sys.argv[1] if len(sys.argv) > 1 else "Map_200000"
names = [p.relative_to(GAME_DATA).as_posix() for p in sorted((GAME_DATA / "Map" / m).rglob("*.json"))]
names += ["Map/GDSFastTravel.json", "Map/GDSTamagemonoShrineData.json", "Map/GDSAreaDef.json", "Map/GDSAreaPoint.json",
          "Map/GDSCamp.json", "Map/GDSQuestRequesterSetting.json", "Map/GDSMapAbsolutePoint.json",
          "Menu/GDSMapMenuPlacementConfig.json", "Menu/GDSMapMenuIconVisibleSetting.json",
          "Menu/GDSDungeonEntranceIconSetting.json", "Map/GDSPlantLeafeData.json", "Map/GDSAnywhereGateSetting.json",
          f"NPC/Map/{m}/{m}_GDSNPCSetting.json", f"Shop/Map/{m}/{m}_GDSMapShopConfig.json"]
for n in names:
    if "/map200000_area" in n and not n.endswith("area002_GDSMapPickPoint.json") \
            and not n.endswith("area002_GDSMapEnemyPlacementConfig.json"):
        continue
    try:
        rows = _Table(n).rows
    except Exception as e:
        print(f"== {n}: {type(e).__name__} {e}")
        continue
    first = next(iter(rows.values()), {})
    print(f"== {n} ({len(rows)} rows)\n   {json.dumps(first, ensure_ascii=False)[:700]}")
