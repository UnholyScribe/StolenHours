"""Read-only: GDSMapIconData rows for given mapIconTypes (default: event icons, glows, player-ish rows),
with the texture each icon id resolves to through GDSMenuIconTexture."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours.mapevents import _Table  # noqa: E402

icons = _Table("Menu/GDSMapIconData.json")
tex = _Table("Menu/GDSMenuIconTexture.json")
want = {int(a) for a in sys.argv[1:]} or {0, 1, 2, 3, 113, 114, 115, 124, 129, 130, 131, 219}
first = next(iter(icons.rows.items()))
print("row sample:", json.dumps(first, ensure_ascii=False)[:800])
print("tex sample:", json.dumps(next(iter(tex.rows.items())), ensure_ascii=False)[:500])
for k, v in icons.rows.items():
    t = v.get("mapIconType", k)
    if (isinstance(t, int) and t in want) or (sys.argv[1:] == [] and "layer" in json.dumps(v).lower() and False):
        tid = v.get("mapIconId")
        print(t, json.dumps(v, ensure_ascii=False)[:500], "->", json.dumps(tex.rows.get(tid), ensure_ascii=False)[:250])
