"""Read-only: find which exported table holds a text key, and print a few matching entries."""
import json
import sys
from pathlib import Path

G = Path(__file__).resolve().parents[1] / "assets/game/Game/Content/GameData"
key, prefix = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
for f in G.rglob("*.json"):
    s = f.read_text(encoding="utf-8", errors="ignore")
    if f'"{key}"' not in s or "text_en" not in s:
        continue
    m = {(x["Key"]["Name"] if isinstance(x["Key"], dict) else x["Key"]): x["Value"]
         for x in json.loads(s)[0]["Properties"]["m_dataMap"]}
    if key not in m:
        continue
    hits = [(k, (m[k].get("textInfo") or [{}])[0].get("text_en")) for k in m if k.startswith(prefix)]
    print(f.relative_to(G), len(hits))
    for h in hits[:15]:
        print("  ", h)
