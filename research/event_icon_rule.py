"""Read-only: candidate fields for choosing each event's map icon (gather kind, crowned/legendary, blue glow)."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import _Table  # noqa: E402

config, target = _Table("Quest/GDSActiveEventConfig.json"), _Table("Quest/GDSActiveEventTarget.json")
place = _Table("Quest/GDSActiveEventPlaceData.json")
purpose = _Table("Quest/GDSQuestPurposePoint.json")
titles = {k: (v["Text"][0].get("nounSingularForm_en") if v.get("Text") else None)
          for k, v in _Table("Quest/GDSQuestTitleText.json").rows.items()}

for et in (1, 2, 3, 4):
    eid = next(k for k, v in target.rows.items() if v.get("ActiveEventType") == et)
    print(f"type {et} target:", json.dumps(target.rows[eid], ensure_ascii=False)[:900])
    print(f"type {et} config:", json.dumps(config.rows[eid], ensure_ascii=False)[:900])

print("\nblue glow (114) events:")
for eid, c in config.rows.items():
    pl = place.rows.get(c["EventPointId"], {})
    pp = purpose.rows.get(pl.get("purposePointId"), {})
    if pp.get("mapIconType") == 114:
        print(" ", eid, target.rows.get(eid, {}).get("ActiveEventType"), titles.get(c["TitleId"]))

by_type = collections.defaultdict(collections.Counter)
for eid, c in config.rows.items():
    by_type[target.rows.get(eid, {}).get("ActiveEventType")][titles.get(c["TitleId"])] += 1
for et, cnt in sorted(by_type.items(), key=str):
    print(f"type {et} titles:", dict(cnt))

keys = collections.Counter(k for v in target.rows.values() for k in v)
print("\ntarget fields:", dict(keys))
