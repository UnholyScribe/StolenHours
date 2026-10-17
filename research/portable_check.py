"""Scan a StolenHours.exe portable folder for personal-path / key leaks.

Usage: py -3.12 research/portable_check.py "<portable build dir>"
"""
from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
# Strings that must never appear in a shipped build.
NEEDLES = [
    b"research\\private",
    b"research/private",
    b"Fantasy Life i - Stolen Hours",
    b"discord_bot\\.env",
]
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
        bad.append(f"{f.relative_to(root)} is a key/mapping file")
        continue
    try:
        data = f.read_bytes()
    except OSError:
        continue
    for n in NEEDLES:
        if not n:
            continue
        if n in data or n.lower() in data.lower():
            bad.append(f"{f.relative_to(root)} contains {n[:24]!r}...")

need = [
    "_internal/stolenhours/webgui/web/game/mapview/maps/Map_200000.jpg",
    "_internal/stolenhours/webgui/web/game/mapview/maps/Map_100100.jpg",
    "_internal/stolenhours/webgui/web/game/mapview/mapview.json",
]
missing = [p for p in need if not (root / p).exists()]

print(f"scan: {root}")
if bad:
    print("LEAKS:")
    for line in bad:
        print(" ", line)
else:
    print("no leaks")
if missing:
    print("MISSING:")
    for p in missing:
        print(" ", p)
else:
    print("nothing missing (map art present)")
sys.exit(1 if bad or missing else 0)
