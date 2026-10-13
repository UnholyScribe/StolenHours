"""Steam Deck / Linux host support.

Under Proton (Wine) the editor is a Windows program in its own prefix: the Linux filesystem is drive Z:, Steam's
records hold Linux paths, and the game runs in another prefix, so tasklist can't see it. Native Linux works the
same way without the Z: mapping.
"""

from __future__ import annotations

import functools
import os
import re
from pathlib import Path

ROOT = "Z:\\"  # where Wine shows the Linux root; tests point it at a temp folder
STEAM_DIRS = (".local/share/Steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam")
STEAM_LINKS = (".steam/steam", ".steam/root")  # symlinks to one of the above; only used if neither exists


@functools.cache
def under_wine() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return hasattr(ctypes.WinDLL("ntdll"), "wine_get_version")
    except (OSError, AttributeError):
        return False


def on_linux_host() -> bool:
    return os.name == "posix" or under_wine()


def host_path(p: str) -> Path:
    """A path from Steam's Linux records (libraryfolders.vdf etc.) as this process can open it."""
    if os.name == "nt" and p.startswith("/"):
        return Path(ROOT) / p.lstrip("/")
    return Path(p)


def homes() -> list[Path]:
    if os.name == "posix":
        return [Path.home()]
    if not under_wine():
        return []
    out = []
    home = os.environ.get("HOME", "")
    if home.startswith("/"):
        out.append(host_path(home))
    try:
        out += sorted(p for p in (Path(ROOT) / "home").iterdir() if p.is_dir())
    except OSError:
        pass
    seen = set()
    return [p for p in out if not (str(p).lower() in seen or seen.add(str(p).lower()))]


def linux_steam_roots() -> list[Path]:
    out = []
    for home in homes():
        found = [home / d for d in STEAM_DIRS if (home / d / "steamapps").is_dir()]
        out += found or [home / d for d in STEAM_LINKS if (home / d / "steamapps").is_dir()][:1]
    return out


def proc_root() -> Path:
    return Path("/proc") if os.name == "posix" else Path(ROOT) / "proc"


def running_on_host(names) -> list[str]:
    """Which of `names` (Windows exe names) are running anywhere on the Linux host, any Wine prefix."""
    wanted = {n.lower(): n for n in names}
    short = {n.lower()[:15]: n for n in names}  # /proc/<pid>/comm keeps 15 characters
    found = set()
    proc = proc_root()
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return []
    for pid in pids:
        try:
            parts = (proc / pid / "cmdline").read_bytes().split(b"\0")[:4]
        except OSError:
            continue
        for part in parts:
            base = re.split(r"[\\/]", part.decode("utf-8", "replace"))[-1].lower()
            if base in wanted:
                found.add(wanted[base])
        try:
            comm = (proc / pid / "comm").read_text("utf-8", "replace").strip().lower()
        except OSError:
            continue
        if comm in short:
            found.add(short[comm])
    return sorted(found)
