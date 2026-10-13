"""Lists live events near the player with their offset in game-screen pixels (1920 wide) at a zoom step.

usage: py -3.12 research/live_compare.py PORT TOKEN [step]
"""
import json
import sys
import urllib.request
from pathlib import Path

port, token = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 1
mv = json.loads((Path(__file__).resolve().parents[1] / "editor/stolenhours/webgui/web/game/mapview/mapview.json")
                .read_text(encoding="utf-8"))
req = urllib.request.Request(f"http://127.0.0.1:{port}/api/mapview_live", data=b"{}", method="POST",
                             headers={"X-Token": token, "Content-Type": "application/json"})
live = json.load(urllib.request.urlopen(req))["data"]
p = live["player"]
zoom = list(mv["zoom"].values())[step] * mv["textureSize"]
print("player", p, "zoom keys", mv["zoom"])
rows = []
for e in live["events"]:
    ev = mv["events"].get(e["id"])
    if not ev:
        print("not on map:", e)
        continue
    # u runs down the screen, v runs across
    dx, dy = (ev["v"] - p["v"]) * zoom, (ev["u"] - p["u"]) * zoom
    rows.append((abs(dx) + abs(dy), e["id"], ev["title"], ev["icon"], ev["glow"], round(dx), round(dy)))
for r in sorted(rows):
    print(*r[1:], sep="\t")
