"""Portability check for a built Stolen Hours folder: no keys, mappings, personal ids or project paths inside,
and the bundled pieces (web UI, map viewer, parser data, mod) are present.

usage: py -3.12 research/portable_check.py <build folder>
"""
import sys
from pathlib import Path

root = Path(sys.argv[1])
NEEDLES = [b"235938730", b"Karda", b"E:\\Fantasy Life i", b"E:/Fantasy Life i", b"research\\private",
           b"research/private"]
private = Path(__file__).resolve().parent / "private"
for key in ("aes_key.hex", "pak_key.hex"):
    p = private / key
    if p.exists():
        NEEDLES.append(p.read_text().strip().encode())
bad = []
for f in root.rglob("*"):
    if not f.is_file():
        continue
    if f.suffix in (".hex", ".usmap"):
        bad.append(f"forbidden file {f}")
        continue
    if f.stat().st_size > 64 << 20:
        continue
    data = f.read_bytes()
    for n in NEEDLES:
        if n in data or n.lower() in data.lower():
            bad.append(f"{f.relative_to(root)} contains {n[:12]!r}...")
need = ["_internal/stolenhours/webgui/web/game/mapview/maps/Map_200000.jpg",
        "_internal/stolenhours/webgui/web/game/mapview/maps/Map_100100.jpg",
        "_internal/stolenhours/webgui/web/game/mapview/mapview.json",
        "_internal/stolenhours/webgui/web/game/collection/collection.json",
        "_internal/stolenhours/webgui/web/game/nav_collection.png",
        "_internal/stolenhours/webgui/web/game/forge/forge.json",
        "_internal/stolenhours/webgui/web/game/items/details.json",
        "_internal/stolenhours/webgui/web/game/nav_forge.png",
        "_internal/hook/ue4ss_mod/StolenHours/Scripts/main.lua",
        "_internal/hook/ue4ss_mod/StolenHours/Scripts/stolenhours_dump.lua",
        "_internal/tools/fli_save_editor/fli_sav_pattern.txt"]
missing = [n for n in need if not (root / n).exists()]
size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
print(f"{sum(1 for _ in root.rglob('*'))} entries, {size / 1e6:.0f} MB")
print("leaks:", bad or "none")
print("missing:", missing or "none")
sys.exit(1 if bad or missing else 0)
