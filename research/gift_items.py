"""Looks up gift-code reward items in the extracted game tables: id, table, rarity fields and English description.

Run:  py -3.12 research/gift_items.py "Redux Stone" "Monstroganoff" ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ITEM = Path(__file__).resolve().parents[1] / "assets" / "game" / "Game" / "Content" / "GameData" / "Item"


def data_map(name: str) -> list:
    props = json.loads((ITEM / name).read_text(encoding="utf-8"))[0]["Properties"]
    return props.get("m_dataMap") or next(iter(props.values()))


def main(wanted: list[str]) -> None:
    nouns = {}
    for e in data_map("GDSItemText_Noun.json"):
        info = (e["Value"].get("textInfo") or [{}])[0]
        nouns.setdefault((info.get("nounSingularForm_en") or "").lower(), []).append(e["Key"])
    descs = {e["Key"]: ((e["Value"].get("textInfo") or [{}])[0].get("text_en") or "") for e in data_map("GDSItemText.json")}
    rows = []
    for f in sorted(ITEM.glob("GDSItem*Data.json")):
        try:
            for e in data_map(f.name):
                if isinstance(e["Value"], dict) and "nameId" in e["Value"]:
                    rows.append((f.stem[7:-4], e["Key"], e["Value"]))
        except (KeyError, IndexError, StopIteration):
            pass
    out = {}
    for w in wanted:
        keys = set(nouns.get(w.lower(), []))
        hits = []
        for table, item_id, v in rows:
            if (v.get("nameId") in keys and table not in ("Recipe", "Treasure")
                    and not item_id.lower().startswith("test")):
                hits.append({"id": item_id, "table": table, "rarity": v.get("rarity", v.get("Rarity")),
                             "desc": descs.get(f"desc_itm_{item_id}", "").replace("\r\n", " ")})
        out[w] = hits
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
