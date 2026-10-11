"""Filesystem locations. Every path here was checked on Unholy's machine on 2026-10-11 unless marked."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = PROJECT_ROOT / "research" / "private" / "aes_key.hex"
BACKUP_ROOT = PROJECT_ROOT / "backups" / "saves"
COMMUNITY_EDITOR = PROJECT_ROOT / "tools" / "fli_save_editor"
PATTERN_FILE = COMMUNITY_EDITOR / "fli_sav_pattern.txt"
ITEM_LIST_FILE = COMMUNITY_EDITOR / "itemlist.txt"

SAVE_FILE_NAME = "002DAE74-00-gamedata.bin"
STEAM_SAVE_DIR = Path(r"C:\Null\Grave\userdata\235938730\2993780\remote")

# Used when NFL1-Win64-Shipping.exe is started directly instead of through Steam.
# Source: Steam community thread; UNVERIFIED on this machine (folder absent until the game is run that way).
DIRECT_LAUNCH_SAVE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Game" / "Saved" / "SaveGames"

GAME_PROCESS_NAMES = ("NFL1-Win64-Shipping.exe", "NFL1.exe", "EACLauncher.exe", "GameBootstrapper.exe")

LIVE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "StolenHours" / "live"


def default_save_path() -> Path:
    return STEAM_SAVE_DIR / SAVE_FILE_NAME


def candidate_save_paths() -> list[Path]:
    found = [STEAM_SAVE_DIR / SAVE_FILE_NAME]
    if DIRECT_LAUNCH_SAVE_DIR.is_dir():
        found.extend(sorted(DIRECT_LAUNCH_SAVE_DIR.glob("*.bin")) + sorted(DIRECT_LAUNCH_SAVE_DIR.glob("*.sav")))
    return [p for p in found if p.is_file()]
