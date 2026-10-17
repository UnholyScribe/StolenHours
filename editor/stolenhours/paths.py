"""Filesystem locations. Steam, game and save folders are discovered at runtime (see steam.py)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import steam

FROZEN = getattr(sys, "frozen", False)
if os.name == "nt":
    USER_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "StolenHours"
else:
    USER_DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "StolenHours"

if FROZEN:
    # standalone exe: no project folder; the save key is read from the user's own game install (container.resolve_key)
    PACKAGE_DIR = Path(sys._MEIPASS) / "stolenhours"
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PACKAGE_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = PACKAGE_DIR.parents[1]
KEY_FILE = PROJECT_ROOT / "research" / "private" / "aes_key.hex"
PAK_KEY_FILE = PROJECT_ROOT / "research" / "private" / "pak_key.hex"
MAPPINGS_FILE = PROJECT_ROOT / "research" / "private" / "FLi-2.2.0.usmap"
EXTRACT_DIR = PROJECT_ROOT / "assets" / "game"
UI_ASSET_DIR = PACKAGE_DIR / "webgui" / "web" / "game"
BACKUP_ROOT = USER_DATA / "backups" if FROZEN else PROJECT_ROOT / "backups" / "saves"
COMMUNITY_EDITOR = PROJECT_ROOT / "tools" / "fli_save_editor"
PATTERN_FILE = COMMUNITY_EDITOR / "fli_sav_pattern.txt"
ITEM_LIST_FILE = COMMUNITY_EDITOR / "itemlist.txt"

SAVE_FILE_NAME = "002DAE74-00-gamedata.bin"
GAME_PROCESS_NAMES = ("NFL1-Win64-Shipping.exe", "NFL1.exe", "EACLauncher.exe", "GameBootstrapper.exe")
LIVE_DIR = USER_DATA / "live"
DUMPS_DIR = USER_DATA / "dumps"


class NotFound(RuntimeError):
    pass


def default_save_path() -> Path:
    p = steam.default_save()
    if p is None:
        raise NotFound("no Fantasy Life i save found. Play once and save, or set "
                       f"{steam.ENV_SAVE}=<path to gamedata.bin>, or pass --save.")
    return p


def candidate_save_paths() -> list[Path]:
    return [s.path for s in steam.find_saves()]


def game_dir() -> Path:
    dirs = steam.find_game_dirs()
    if not dirs:
        raise NotFound(f"Fantasy Life i install not found. Set {steam.ENV_GAME}=<game folder>.")
    return dirs[0]
