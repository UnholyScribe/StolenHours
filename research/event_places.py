"""Read-only: where each map event sits and which icon data points at it.

Prints per-type counts of events whose place resolves to a world position (func point or purpose point),
which events carry OverrideMapIconType, and the purpose-point mapIconType spread.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import GAME_DATA, _Table  # noqa: E402

config, target = _Table("Quest/GDSActiveEventConfig.json"), _Table("Quest/GDSActiveEventTarget.json")
place = _Table("Quest/GDSActiveEventPlaceData.json")
func = _Table("Map/Map_200000/Map_200000_GDSMapFuncPoint.json")
purpose = _Table("Quest/GDSQuestPurposePoint.json")

print("place sample:", json.dumps(next(iter(place.rows.items())), ensure_ascii=False)[:600])
print("func sample:", json.dumps(next(iter(func.rows.items())), ensure_ascii=False)[:600])
pk = next((k for k, v in place.rows.items() if v.get("purposePointId")), None)
if pk:
    print("purpose sample:", json.dumps(purpose.rows.get(place.rows[pk]["purposePointId"]), ensure_ascii=False)[:600])

stats = collections.Counter()
overrides = []
icon_types = collections.Counter()
for eid, c in config.rows.items():
    t = target.rows.get(eid, {})
    pl = place.rows.get(c["EventPointId"], {})
    fp = func.rows.get(pl.get("funcPointId"))
    pp = purpose.rows.get(pl.get("purposePointId"))
    et = t.get("ActiveEventType", 0)
    stats[(et, "func" if fp else "nofunc", "purpose" if pp else "nopurpose", pl.get("mapId"))] += 1
    if pp:
        icon_types[(et, pp.get("mapIconType"))] += 1
    if t.get("OverrideMapIconType"):
        overrides.append((eid, et, t["OverrideMapIconType"]))
for k, n in sorted(stats.items(), key=str):
    print(k, n)
print("purpose mapIconType by event type:", dict(icon_types))
print("overrides:", overrides)
