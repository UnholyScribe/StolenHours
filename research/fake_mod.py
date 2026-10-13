"""Test double for the StolenHours UE4SS mod: answers EVENTS / PLAYER / PING through a mailbox in <root>/StolenHours/live.

Never point it at the real %LOCALAPPDATA%; run the editor with LOCALAPPDATA=<root> instead.
usage: py -3.12 research/fake_mod.py <root> [--old]   (--old answers like mod 0.3.0: unknown command)
"""
import json
import math
import sys
import time
from pathlib import Path

root = Path(sys.argv[1]) / "StolenHours" / "live"
old = "--old" in sys.argv
root.mkdir(parents=True, exist_ok=True)
meta = json.loads((Path(__file__).resolve().parents[1] / "editor/stolenhours/webgui/web/game/mapview/mapview.json")
                  .read_text(encoding="utf-8"))
picked, seen = [], set()
for eid, e in meta["events"].items():
    if e["icon"] not in seen and "multi" not in eid:
        seen.add(e["icon"])
        picked.append(eid)
events = ",".join(f"{eid}:{1 + i % 3}" for i, eid in enumerate(picked[:10])) + ",roguelike_dummy_001:1"
t0 = time.time()
while True:
    (root / "heartbeat.txt").write_text(str(int(time.time())))
    cmd = root / "cmd.txt"
    if cmd.exists():
        try:
            cid, verb, *_ = cmd.read_text(encoding="utf-8").rstrip("\r\n").split("\t")
        except (OSError, ValueError):
            time.sleep(0.05)
            continue
        cmd.unlink()
        if verb == "PING":
            ok, text = True, "pong fake"
        elif old and verb in ("EVENTS", "PLAYER"):
            ok, text = False, f"unknown command {verb}"
        elif verb == "EVENTS":
            ok, text = True, f"{len(picked[:10]) + 1}|{events}"
        elif verb == "PLAYER":
            a = (time.time() - t0) / 10
            x, y = 20000 * math.cos(a), 20000 * math.sin(a)
            ok, text = True, f"{x:.1f},{y:.1f},500.0,{math.degrees(a) + 90:.1f},Map_200000"
        else:
            ok, text = False, f"unknown command {verb}"
        tmp = root / "ack.tmp"
        tmp.write_text(f"{cid}\t{'OK' if ok else 'ERR'}\t{text}", encoding="utf-8")
        tmp.replace(root / "ack.txt")
    time.sleep(0.05)
