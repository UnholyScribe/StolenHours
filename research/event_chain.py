"""Dumps the config -> place -> purpose point chain for active events matching a prefix.

usage: py -3.12 research/event_chain.py qsf_active_event_026
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import _Table  # noqa: E402
from stolenhours.mapview import world_to_map  # noqa: E402

config, target = _Table("Quest/GDSActiveEventConfig.json"), _Table("Quest/GDSActiveEventTarget.json")
place, purpose = _Table("Quest/GDSActiveEventPlaceData.json"), _Table("Quest/GDSQuestPurposePoint.json")
for eid, c in config.rows.items():
    if not eid.startswith(sys.argv[1]):
        continue
    print("==", eid, json.dumps({k: v for k, v in c.items() if not isinstance(v, (dict, list))}))
    pl = place.rows.get(c["EventPointId"], {})
    print("  place", c["EventPointId"], json.dumps(pl)[:600])
    pp = purpose.rows.get(pl.get("purposePointId"))
    if pp:
        pos = pp["tgtPosition"]
        print("  point", pl.get("purposePointId"), pos, world_to_map(pos["X"], pos["Y"]), "icon", pp["mapIconType"])
    print("  target", json.dumps(target.rows.get(eid, {}))[:600])
