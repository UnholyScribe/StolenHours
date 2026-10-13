"""Read-only look at the crafting result tables: title names, quality groups, preset gear, item craft data."""
import collections
import json
import sys
from pathlib import Path

G = Path(__file__).resolve().parents[1] / "assets" / "game" / "Game" / "Content" / "GameData"


def rows(rel):
    d = json.loads((G / rel).read_text(encoding="utf-8"))
    return d[0]["Properties"]["m_dataMap"]


def key(k):
    return k["Name"] if isinstance(k, dict) else k


noun = {}
for r in rows("Item/GDSItemText_Noun.json"):
    v = r["Value"]
    noun[key(r["Key"])] = v
titles = [key(r["Key"]) for r in rows("Item/GDSItemTitleData.json")]
print("title text samples:")
for k in list(noun):
    if k.startswith("name_item_title_"):
        print(" ", k, json.dumps(noun[k], ensure_ascii=False)[:200])
sample = next(iter(noun.items()))
print("noun row shape:", json.dumps(sample, ensure_ascii=False)[:300])

qg = rows("Item/GDSItemQualityGroup.json")
sizes = collections.Counter(len(r["Value"]["itemGroup"]) for r in qg)
prefixes = collections.Counter(r["Value"]["ItemId"][:3] for r in qg)
print("quality groups:", len(qg), "sizes", dict(sizes), "prefixes", dict(prefixes))

pre = rows("Item/GDSEquipSkillPresetSetting.json")
print("presets:", len(pre), "titles", collections.Counter(r["Value"]["Title"] for r in pre),
      "qualities", collections.Counter(r["Value"]["Quality"] for r in pre))

craft = json.loads((G / "Item/GDSItemCraftData.json").read_text(encoding="utf-8"))
m = craft[0]["Properties"]["m_dataMap"]
print("craft rows:", len(m))
for r in m[:2]:
    print(json.dumps(r, ensure_ascii=False)[:1500])
