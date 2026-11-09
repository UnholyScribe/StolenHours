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


def _saves_under_userdata(ud: Path, users: dict[str, tuple[str | None, bool]] | None = None) -> list[SaveLocation]:
    found: list[SaveLocation] = []
    if not ud.is_dir():
        return found
    users = users or {}
    try:
        accounts = list(ud.iterdir())
    except OSError:
        return found
    for acct in accounts:
        if not acct.is_dir() or not acct.name.isdigit():
            continue
        remote = acct / APP_ID / "remote"
        if not remote.is_dir():
            continue
        persona, recent = users.get(acct.name, (None, False))
        try:
            files = list(remote.glob(SAVE_GLOB))
        except OSError:
            continue
        for f in files:
            try:
                mtime = f.stat().st_mtime
            except OSError:
                mtime = 0.0
            found.append(SaveLocation(f, "steam", acct.name, persona, recent, mtime))
    return found


def _deep_steam_userdata() -> list[Path]:
    """When registry Steam is missing/wrong, still find userdata/*/2993780/remote on common layouts."""
    out: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        try:
            r = p.resolve()
        except OSError:
            return
        key = str(r).lower()
        if key not in seen and r.is_dir():
            seen.add(key)
            out.append(r)

    for root in find_steam_roots():
        add(root / "userdata")
    for d in _drives():
        for c in _COMMON_STEAM:
            add(d / c / "userdata")
        # Portable / renamed Steam folders people actually use
        for name in ("Steam", "steam", "SteamLibrary"):
            add(d / name / "userdata")
            add(d / "Games" / name / "userdata")
            add(d / "Program Files (x86)" / name / "userdata")
            add(d / "Program Files" / name / "userdata")
    return out


def find_saves() -> list[SaveLocation]:
    """All gamedata saves, best guess first: newest-login Steam account, then newest file."""
    found: list[SaveLocation] = []
    seen: set[str] = set()

    def add_all(items: list[SaveLocation]) -> None:
        for s in items:
            key = str(s.path).lower()
            if key not in seen:
                seen.add(key)
                found.append(s)

    for root in find_steam_roots():
        add_all(_saves_under_userdata(root / "userdata", _login_users(root)))
    if not found:
        # Registry miss / exotic Steam path — still find the save without env vars or a command.
        for ud in _deep_steam_userdata():
            add_all(_saves_under_userdata(ud))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        d = Path(local) / "Game" / "Saved" / "SaveGames"
        if d.is_dir():
            try:
                bins = list(d.glob("*.bin")) + list(d.glob("*.sav"))
            except OSError:
                bins = []
            for f in bins:
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    mtime = 0.0
                add_all([SaveLocation(f, "direct-launch", mtime=mtime)])
    found.sort(key=lambda s: (s.kind == "steam", s.most_recent_user, s.mtime), reverse=True)
    return found


def default_save() -> Path | None:
    if os.environ.get(ENV_SAVE):
        return Path(os.environ[ENV_SAVE])
    saves = find_saves()
    return saves[0].path if saves else None
