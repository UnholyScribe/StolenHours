"""Filesystem locations. Steam, game and save folders are discovered at runtime (see steam.py)."""

from __future__ import annotations

import os
from pathlib import Path

from . import steam

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = PROJECT_ROOT / "research" / "private" / "aes_key.hex"
BACKUP_ROOT = PROJECT_ROOT / "backups" / "saves"
COMMUNITY_EDITOR = PROJECT_ROOT / "tools" / "fli_save_editor"
PATTERN_FILE = COMMUNITY_EDITOR / "fli_sav_pattern.txt"
ITEM_LIST_FILE = COMMUNITY_EDITOR / "itemlist.txt"

SAVE_FILE_NAME = "002DAE74-00-gamedata.bin"
GAME_PROCESS_NAMES = ("NFL1-Win64-Shipping.exe", "NFL1.exe", "EACLauncher.exe", "GameBootstrapper.exe")
LIVE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "StolenHours" / "live"


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
