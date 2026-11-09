"""Install or update the StolenHours UE4SS mod that ships inside the editor, on whatever PC the editor runs on.

When the portable build includes tools/ue4ss/dist (dwmapi.dll + ue4ss/), Install Live Setup can put
UE4SS + the StolenHours mod into the user's game folder in one click (game must be closed).
A mod is switched on by a `<name> : 1` line in Mods/mods.txt.
Existing mod files are backed up with SHA-256 first.
"""
from __future__ import annotations

import datetime as _dt
import re
import shutil
from pathlib import Path

from . import paths, safety

MOD_NAME = "StolenHours"
BUNDLED = paths.PROJECT_ROOT / "hook" / "ue4ss_mod" / MOD_NAME
# Dev tree: tools/ue4ss/dist. Frozen exe: same path under _MEIPASS.
UE4SS_DIST = paths.PROJECT_ROOT / "tools" / "ue4ss" / "dist"
MOD_BACKUPS = (paths.USER_DATA / "mod_backups") if paths.FROZEN else paths.PROJECT_ROOT / "backups" / "mod"
_VERSION = re.compile(r'local VERSION = "([^"]+)"')
_ENTRY = re.compile(rf"^\s*{MOD_NAME}\s*:\s*(\d)\s*$", re.M)
_KEYBINDS_NOTE = "; Built-in keybinds"
SHIPPING_REL = "Game\\Binaries\\Win64\\NFL1-Win64-Shipping.exe"


def _version(main_lua: Path) -> str | None:
    try:
        m = _VERSION.search(main_lua.read_text(encoding="utf-8", errors="replace"))
    except FileNotFoundError:
        return None
    return m.group(1) if m else "unknown"


def mods_dir(game: Path) -> Path | None:
    win64 = game / "Game" / "Binaries" / "Win64"
    for base in (win64 / "ue4ss", win64):
        if (base / "UE4SS.dll").exists() and (base / "Mods").is_dir():
            return base / "Mods"
    return None


def _bundled_files() -> list[Path]:
    return sorted(p for p in BUNDLED.rglob("*") if p.is_file())


def ue4ss_bundled() -> bool:
    return (UE4SS_DIST / "dwmapi.dll").is_file() and (UE4SS_DIST / "ue4ss" / "UE4SS.dll").is_file()


def status(game: Path | None = None) -> dict:
    out = {"bundled": _version(BUNDLED / "Scripts" / "main.lua"), "game": None, "ue4ss": False,
           "installed": None, "enabled": False, "current": False, "ue4ss_bundled": ue4ss_bundled(),
           "can_live_setup": False}
    try:
        game = game or paths.game_dir()
    except paths.NotFound:
        return out
    out["game"] = str(game)
    mods = mods_dir(game)
    if mods is None:
        out["can_live_setup"] = out["ue4ss_bundled"]
        return out
    out["ue4ss"] = True
    out["installed"] = _version(mods / MOD_NAME / "Scripts" / "main.lua")
    try:
        m = _ENTRY.search((mods / "mods.txt").read_text(encoding="utf-8", errors="replace"))
        out["enabled"] = bool(m and m.group(1) == "1")
    except FileNotFoundError:
        pass
    target = mods / MOD_NAME
    out["current"] = out["enabled"] and all(
        (target / f.relative_to(BUNDLED)).exists()
        and safety.sha256_file(target / f.relative_to(BUNDLED)) == safety.sha256_file(f) for f in _bundled_files())
    # Offer setup when UE4SS is missing (and we ship it) or the mod is missing/outdated.
    out["can_live_setup"] = (not out["current"]) and (out["ue4ss"] or out["ue4ss_bundled"])
    return out


def _skip_eac(game: Path) -> None:
    """Point GameBootstrapper at the shipping exe so Steam launches without EAC (needed for UE4SS)."""
    ini = game / "GameBootstrapper.ini"
    if not ini.is_file():
        return
    text = ini.read_text(encoding="utf-8", errors="replace")
    if "ApplicationPath=EACLauncher.exe" not in text:
        return
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup = MOD_BACKUPS / f"{stamp}_GameBootstrapper.ini"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ini, backup)
    ini.write_text(text.replace("ApplicationPath=EACLauncher.exe", f"ApplicationPath={SHIPPING_REL}"),
                   encoding="utf-8", newline="")


def install_ue4ss(game: Path | None = None, skip_eac: bool = True) -> dict:
    """Copy bundled UE4SS into the game Win64 folder. Game must be closed."""
    safety.require_game_closed()
    if not ue4ss_bundled():
        raise safety.SafetyError(
            "This build does not include UE4SS. Use a full Stolen Hours release zip, "
            "or install UE4SS into the game folder yourself, then press Install mod.")
    game = game or paths.game_dir()
    win64 = game / "Game" / "Binaries" / "Win64"
    if not (win64 / "NFL1-Win64-Shipping.exe").is_file():
        raise safety.SafetyError(f"game shipping exe not found under {win64}")
    if skip_eac:
        _skip_eac(game)
    shutil.copy2(UE4SS_DIST / "dwmapi.dll", win64 / "dwmapi.dll")
    dest_ue4ss = win64 / "ue4ss"
    if dest_ue4ss.exists():
        shutil.rmtree(dest_ue4ss)
    shutil.copytree(UE4SS_DIST / "ue4ss", dest_ue4ss)
    settings = dest_ue4ss / "UE4SS-settings.ini"
    if settings.is_file():
        text = settings.read_text(encoding="utf-8", errors="replace")
        settings.write_text(text.replace("EnableHotReloadSystem = 0", "EnableHotReloadSystem = 1"),
                            encoding="utf-8")
    paths.LIVE_DIR.mkdir(parents=True, exist_ok=True)
    return status(game)


def install_live(game: Path | None = None, skip_eac: bool = True) -> dict:
    """One-click Live Map / Time Hook setup: UE4SS (if bundled) + StolenHours mod."""
    safety.require_game_closed()
    game = game or paths.game_dir()
    st = status(game)
    if not st["ue4ss"]:
        st = install_ue4ss(game, skip_eac=skip_eac)
    mod = install(game)
    return {**mod, "ue4ss": True, "live_setup": True,
            "note": "Start Fantasy Life i from Steam, load a save, then open Live Map. "
                    "Multiplayer is off while EAC is skipped."}


def _enable(mods_txt: Path) -> None:
    text = mods_txt.read_text(encoding="utf-8", errors="replace") if mods_txt.exists() else ""
    if _ENTRY.search(text):
        text = _ENTRY.sub(f"{MOD_NAME} : 1", text)
    elif _KEYBINDS_NOTE in text:  # UE4SS wants Keybinds last
        text = text.replace(_KEYBINDS_NOTE, f"{MOD_NAME} : 1\n{_KEYBINDS_NOTE}", 1)
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + f"{MOD_NAME} : 1\n"
    mods_txt.write_text(text, encoding="utf-8")


def install(game: Path | None = None) -> dict:
    safety.require_game_closed()
    game = game or paths.game_dir()
    mods = mods_dir(game)
    if mods is None:
        raise safety.SafetyError("UE4SS is not installed in this game folder. Install UE4SS first, then try again.")
    files = _bundled_files()
    if not files:
        raise safety.SafetyError("this build has no mod files inside")
    target = mods / MOD_NAME
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup = None
    old = [p for p in (target.rglob("*") if target.exists() else []) if p.is_file()]
    if (mods / "mods.txt").exists():
        old.append(mods / "mods.txt")
    if old:
        backup = MOD_BACKUPS / f"{stamp}_{MOD_NAME}-{_version(target / 'Scripts' / 'main.lua') or 'none'}"
        lines = []
        for p in old:
            rel = p.relative_to(mods)
            dest = backup / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            digest = safety.sha256_file(dest)
            if digest != safety.sha256_file(p):
                raise safety.SafetyError(f"backup of {rel} does not match; nothing was installed")
            lines.append(f"{digest}  {rel}")
        (backup / "SHA256.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    for f in files:
        dest = target / f.relative_to(BUNDLED)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        if safety.sha256_file(dest) != safety.sha256_file(f):
            raise safety.SafetyError(f"{dest.name} did not copy correctly")
    _enable(mods / "mods.txt")
    st = status(game)
    if not st["current"]:
        raise safety.SafetyError("the mod was copied but does not check out; see the mod folder")
    return {**st, "backup": str(backup) if backup else None}
