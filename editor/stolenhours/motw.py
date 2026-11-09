"""Mark of the Web (Zone.Identifier) — Windows blocks DLLs from GitHub zip downloads.

Strangers who extract StolenHours-*-win64 often crash until they Unblock-File / Run.cmd.
The frozen exe clears Zone.Identifier on its own folder at every launch so double-clicking
StolenHours.exe is enough — no PowerShell, no helper script required.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _zone_stream(path: Path) -> Path:
    return Path(str(path) + ":Zone.Identifier")


def has_motw(path: Path) -> bool:
    if os.name != "nt" or not path.exists():
        return False
    try:
        with open(_zone_stream(path), "rb"):
            return True
    except OSError:
        return False


def clear_motw(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        os.remove(_zone_stream(path))
        return True
    except OSError:
        return False


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(sys.executable).resolve().parent


def scan(root: Path | None = None, limit: int = 80) -> list[Path]:
    root = root or app_root()
    if os.name != "nt" or not root.is_dir():
        return []
    hits: list[Path] = []
    for p in [root / "StolenHours.exe", *sorted(root.glob("*.exe")), *sorted(root.glob("*.dll"))]:
        if p.is_file() and has_motw(p):
            hits.append(p)
            if len(hits) >= limit:
                return hits
    internal = root / "_internal"
    if internal.is_dir():
        for p in internal.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".dll", ".pyd", ".exe"):
                continue
            if has_motw(p):
                hits.append(p)
                if len(hits) >= limit:
                    break
    return hits


def unblock_tree(root: Path | None = None) -> int:
    root = root or app_root()
    if os.name != "nt" or not root.is_dir():
        return 0
    n = 0
    for p in root.rglob("*"):
        if p.is_file() and clear_motw(p):
            n += 1
    if clear_motw(root):
        n += 1
    return n


def ensure_unblocked(root: Path | None = None) -> int:
    """Always clear MOTW when present. No dialogs — EXE must Just Work after unzip."""
    root = root or app_root()
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return 0
    if not scan(root, limit=1):
        return 0
    n = unblock_tree(root)
    if n:
        try:
            marker = Path(os.environ.get("LOCALAPPDATA", ".")) / "StolenHours" / "motw_cleared.txt"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"cleared {n} Zone.Identifier stream(s) under {root}\n", encoding="utf-8")
        except OSError:
            pass
    return n
