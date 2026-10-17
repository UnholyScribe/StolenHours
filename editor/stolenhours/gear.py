"""What the main character is wearing, for the 3D preview.

Sources, best first:
  live:      the field character's ViewEquipModelInfoSet[EquipSetCurrentIndex] through the live mod (model names,
             appearance overrides already applied). The game's RPG_MainChara menu actor reports the same sets.
  last live: the last live reading, cached in USER_DATA, used while it is newer than the save file.
  save:      the current life's view-over-gear item ids (SaveFile.worn_items); the preview maps them to models.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import live, paths

PLAYER = "BP_CtrlCharacterBase_C"
SLOTS = ("weapon", "shield", "Head", "tops", "bottoms", "arm", "foot", "mantle", "glasses", "sub")
CACHE = paths.USER_DATA / "last_gear.json"
FRESH_S = 5


def read_live(bridge: live.LiveBridge) -> dict[str, str] | None:
    if not bridge.mod_alive():
        return None
    r = bridge.get(PLAYER, "EquipSetCurrentIndex")
    if not r.ok or not r.text.strip().isdigit():
        return None
    i = int(r.text)
    models = {}
    for slot in SLOTS:
        r = bridge.get(PLAYER, f"ViewEquipModelInfoSet[{i}].{slot}")
        if not r.ok:
            return None
        if r.text and r.text != "None":
            models[slot] = r.text.lower()
    return models


class MainGear:
    def __init__(self, bridge: live.LiveBridge, cache: Path = CACHE):
        self.bridge, self.cache = bridge, cache
        self._last: dict | None = None
        self._lock = threading.Lock()

    def get(self, sf=None) -> dict:
        with self._lock:
            return self._get(sf)

    def _get(self, sf) -> dict:
        now = time.time()
        if self._last and now - self._last["at"] < FRESH_S:
            return self._last
        try:
            models = read_live(self.bridge)
        except live.LiveError:
            models = None
        if models is not None:
            self._last = {"source": "live", "at": now, "models": models}
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            self.cache.write_text(json.dumps(self._last), encoding="utf-8")
            return self._last
        try:
            cached = json.loads(self.cache.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            cached = None
        save_time = sf.path.stat().st_mtime if sf is not None and sf.path.exists() else 0
        if cached and cached.get("at", 0) > save_time:
            return {**cached, "source": "last live"}
        if sf is not None:
            return {"source": "save", "at": save_time, "items": sf.worn_items()}
        return {"source": "none", "at": 0}
