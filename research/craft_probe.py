"""Read-only: how crafted / found gear and stackables look in the save (title, quality, extra stats, skills)."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours import paths, savefile  # noqa: E402

sf = savefile.SaveFile.load(Path(sys.argv[1]) if len(sys.argv) > 1 else paths.default_save_path())
inv = sf.inventory
names = savefile.load_item_names()
for cat in sf.inventory_categories():
    rows = [it for it in inv[cat] if it["ItemId"] not in savefile.EMPTY_IDS]
    if not rows:
        continue
    keys = [k for k in rows[0] if k not in ("Handle", "ItemId")]
    print(f"== {cat} ({len(rows)})  fields: {keys}")
    if "Quality" not in rows[0]:
        continue
    for it in rows:
        extra = {k: it[k] for k in keys if k not in ("getOrder",) and it[k] not in (0, [], None, "None")}
        print(f"  {it['ItemId']:16} {names.get(it['ItemId'], ''):28} {json.dumps(extra, default=str)[:260]}")
