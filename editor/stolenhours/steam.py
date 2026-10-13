"""Find Steam, the game install and the save folder on any Windows machine, or on a Steam Deck under Proton.

Order for each lookup: environment override, Steam's own records (registry, Linux Steam folders, libraryfolders.vdf,
appmanifest_2993780.acf, loginusers.vdf), then a shallow scan of common folders on every drive.
"""

from __future__ import annotations

import os
import re
import string
from dataclasses import dataclass, field
from pathlib import Path

from . import deck

APP_ID = "2993780"
SHIPPING_REL = Path("Game") / "Binaries" / "Win64" / "NFL1-Win64-Shipping.exe"
SAVE_GLOB = "*gamedata.bin"
STEAMID64_BASE = 76561197960265728

ENV_STEAM = "STOLENHOURS_STEAM_DIR"
ENV_GAME = "STOLENHOURS_GAME_DIR"
ENV_SAVE = "STOLENHOURS_SAVE"

_COMMON_STEAM = (r"Program Files (x86)\Steam", r"Program Files\Steam", r"Steam", r"Games\Steam")
_COMMON_LIBS = (r"SteamLibrary", r"Steam", r"Games\SteamLibrary", r"Games\Steam",
                r"Program Files (x86)\Steam", r"Program Files\Steam")


# ---- VDF ----------------------------------------------------------------------
_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


def parse_vdf(text: str) -> dict:
    """Minimal text-VDF (KeyValues) parser: quoted keys/values and braces, // comments ignored."""
    text = re.sub(r"//[^\n]*", "", text)
    root: dict = {}
    stack = [root]
    key = None
    for m in _TOKEN.finditer(text):
        s, brace = m.group(1), m.group(2)
        if brace == "{":
            child: dict = {}
            stack[-1][key if key is not None else ""] = child
            stack.append(child)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        else:
            s = s.replace("\\\\", "\\").replace('\\"', '"')
            if key is None:
                key = s
            else:
                stack[-1][key] = s
                key = None
    return root


def _read_vdf(path: Path) -> dict:
    try:
        return parse_vdf(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def _ci(d: dict, key: str):
    """Case-insensitive dict lookup (Steam is inconsistent about key case)."""
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return None


# ---- Steam root ---------------------------------------------------------------
def _drives() -> list[Path]:
    return [Path(f"{d}:\\") for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def _registry_steam_paths() -> list[Path]:
    out = []
    try:
        import winreg
    except ImportError:
        return out
    for hive, sub, name in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
        try:
            with winreg.OpenKey(hive, sub) as k:
                out.append(Path(winreg.QueryValueEx(k, name)[0]))
        except OSError:
            pass
    return out


def _is_steam_root(p: Path) -> bool:
    return (p / "steamapps").is_dir() and ((p / "steam.exe").is_file() or (p / "userdata").is_dir())


def _valid_roots(cands: list[Path]) -> list[Path]:
    seen, out = set(), []
    for c in cands:
        try:
            r = c.resolve()
        except OSError:
            continue
        if str(r).lower() not in seen and _is_steam_root(r):
            seen.add(str(r).lower())
            out.append(r)
    return out


def find_steam_roots() -> list[Path]:
    cands: list[Path] = []
    if os.environ.get(ENV_STEAM):
        cands.append(Path(os.environ[ENV_STEAM]))
    out = _valid_roots(cands + _registry_steam_paths() + deck.linux_steam_roots())
    if out:
        return out
    # Probing drive letters can stall on disconnected network drives, so only when Steam told us nothing.
    return _valid_roots([d / c for d in _drives() for c in _COMMON_STEAM])


# ---- libraries and game install ----------------------------------------------
def library_folders(steam_root: Path) -> list[Path]:
    libs = [steam_root]
    for name in ("steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"):
        data = _ci(_read_vdf(steam_root / name), "libraryfolders") or {}
        for k, v in data.items():
            if isinstance(v, dict) and _ci(v, "path"):
                libs.append(deck.host_path(_ci(v, "path")))
            elif k.isdigit() and isinstance(v, str):
                libs.append(deck.host_path(v))
    seen, out = set(), []
    for p in libs:
        if str(p).lower() not in seen:
            seen.add(str(p).lower())
            out.append(p)
    return out


def _is_game_dir(p: Path) -> bool:
    return (p / SHIPPING_REL).is_file()


def game_dir_in_library(lib: Path) -> Path | None:
    manifest = lib / "steamapps" / f"appmanifest_{APP_ID}.acf"
    if manifest.is_file():
        state = _ci(_read_vdf(manifest), "AppState") or {}
        installdir = _ci(state, "installdir")
        if installdir and _is_game_dir(lib / "steamapps" / "common" / installdir):
            return lib / "steamapps" / "common" / installdir
    common = lib / "steamapps" / "common"
    if common.is_dir():
        for d in common.iterdir():
            if d.is_dir() and _is_game_dir(d):
                return d
    return None


def find_game_dirs() -> list[Path]:
    out: list[Path] = []

    def add(p: Path | None):
        if p and _is_game_dir(p) and all(str(p).lower() != str(o).lower() for o in out):
            out.append(p)

    if os.environ.get(ENV_GAME):
        add(Path(os.environ[ENV_GAME]))
    for root in find_steam_roots():
        for lib in library_folders(root):
            add(game_dir_in_library(lib))
    if not out:
        for d in _drives():
            for c in _COMMON_LIBS:
                add(game_dir_in_library(d / c))
    return out


# ---- saves --------------------------------------------------------------------
@dataclass
class SaveLocation:
    path: Path
    kind: str                  # "steam" or "direct-launch"
    account_id: str | None = None
    persona: str | None = None
    most_recent_user: bool = False
    mtime: float = field(default=0.0)


def _login_users(steam_root: Path) -> dict[str, tuple[str | None, bool]]:
    users = _ci(_read_vdf(steam_root / "config" / "loginusers.vdf"), "users") or {}
    out = {}
    for sid64, info in users.items():
        if sid64.isdigit() and isinstance(info, dict):
            out[str(int(sid64) - STEAMID64_BASE)] = (_ci(info, "PersonaName"),
                                                      _ci(info, "MostRecent") == "1")
    return out


def find_saves() -> list[SaveLocation]:
    """All gamedata saves, best guess first: newest-login Steam account, then newest file."""
    found: list[SaveLocation] = []
    for root in find_steam_roots():
        users = _login_users(root)
        ud = root / "userdata"
        if not ud.is_dir():
            continue
        for acct in ud.iterdir():
            remote = acct / APP_ID / "remote"
            if not remote.is_dir():
                continue
            persona, recent = users.get(acct.name, (None, False))
            for f in remote.glob(SAVE_GLOB):
                found.append(SaveLocation(f, "steam", acct.name, persona, recent, f.stat().st_mtime))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        d = Path(local) / "Game" / "Saved" / "SaveGames"
        if d.is_dir():
            for f in list(d.glob("*.bin")) + list(d.glob("*.sav")):
                found.append(SaveLocation(f, "direct-launch", mtime=f.stat().st_mtime))
    found.sort(key=lambda s: (s.kind == "steam", s.most_recent_user, s.mtime), reverse=True)
    return found


def default_save() -> Path | None:
    if os.environ.get(ENV_SAVE):
        return Path(os.environ[ENV_SAVE])
    saves = find_saves()
    return saves[0].path if saves else None
