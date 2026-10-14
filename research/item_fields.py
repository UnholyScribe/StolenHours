"""Read-only: which fields of the GDSItem*Data tables look like prices, and sample values. usage: item_fields.py [regex]"""
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.collection import GAME_DATA, _rows  # noqa: E402

pat = re.compile(sys.argv[1] if len(sys.argv) > 1 else r"price|sell|buy|gold|money|cost|value", re.I)
for f in sorted((GAME_DATA / "Item").glob("GDSItem*Data.json")):
    try:
        rows = _rows(f"Item/{f.name}")
    except (KeyError, IndexError, ValueError):
        continue
    sample = next((v for v in rows.values() if isinstance(v, dict)), None)
    if not sample:
        continue
    keys = [k for k in sample if pat.search(k)]
    if keys:
        ex = list(rows.items())[:3]
        print(f"{f.name} ({len(rows)}): " + "; ".join(f"{k}={[v.get(k) for _, v in ex]}" for k in keys))
