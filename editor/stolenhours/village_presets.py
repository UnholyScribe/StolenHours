"""Named Base Camp (and indoor) craft layout snapshots — export / import without rebuilding by hand.

Stored under %LOCALAPPDATA%/StolenHours/village_presets/*.json (or PROJECT backups when not frozen).
Import only when the game is NOT running (safety.running_game_processes).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import paths, safety
from .savefile import SaveFile, SaveFileError
from .village import MAP_BASE, SKIP_IDS, Village, _name

PRESET_DIR = paths.USER_DATA / "village_presets"
_SAFE = re.compile(r"^[\w\- ]{1,64}$")

# Categories kept in a "village loadout" (decor + shells). Terrain land/water optional.
KEEP_CAT = {
    "HOUSE", "GUILD_HOUSE", "GUILD_SQUARE", "BRIDGE", "FENCE", "ROAD", "SLOPE",
    "OBJECT", "TABLE", "WALLDECO", "RUG", "PICK", "WEED", "TAMAGEMONO",
    "LUNCH_EATS", "LUNCH_DRINK", "PLANNED_CONSTRUCT", "VEGETABLE_FIELD",
}


def _dir() -> Path:
    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    return PRESET_DIR


def _path(name: str) -> Path:
    name = (name or "").strip()
    if not _SAFE.match(name):
        raise SaveFileError("preset name: letters, digits, space, _ or - only (max 64)")
    return _dir() / f"{name}.json"


def list_presets() -> list[dict]:
    out = []
    for p in sorted(_dir().glob("*.json")):
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "name": p.stem,
                "mapId": meta.get("mapId"),
                "objects": len(meta.get("objects") or []),
                "houses": len(meta.get("houses") or []),
                "savedAt": meta.get("savedAt"),
                "note": meta.get("note") or "",
            })
        except (OSError, json.JSONDecodeError):
            out.append({"name": p.stem, "error": "unreadable"})
    return out


def export_layout(sf: SaveFile, v: Village, name: str, map_id: str = MAP_BASE,
                  kind: str = "map", include_terrain: bool = False, note: str = "") -> dict:
    st = v.state(sf, map_id=map_id, kind=kind)
    objs = []
    for p in st.get("placed") or []:
        cat = p.get("category") or ""
        cid = p.get("craftObjId") or ""
        if cid in SKIP_IDS or cid in ("None", ""):
            continue
        if cat in ("LAND", "WATER") and not include_terrain:
            continue
        if cat and cat not in KEEP_CAT and cat not in ("LAND", "WATER"):
            # still keep unknown non-terrain
            if cat in ("LAND", "WATER"):
                continue
        objs.append({
            "craftObjId": cid,
            "location": list(p.get("location") or [0, 0, 0]),
            "rotation": list(p.get("rotation") or [0, 0, 0]),
            "category": cat,
            "name": p.get("name"),
        })
    houses = []
    for hh in st.get("houses") or []:
        houses.append({
            "id": hh.get("id"),
            "map": hh.get("map"),
            "entrance": hh.get("entrance"),
            "category": hh.get("category"),
        })
    terrain = None
    if include_terrain:
        terrain = v.terrain_grid(sf, map_id=map_id)
    payload = {
        "version": 1,
        "savedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mapId": map_id,
        "kind": kind,
        "note": note or "",
        "objects": objs,
        "houses": houses,
        "terrain": terrain,
    }
    path = _path(name)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"name": name, "path": str(path), "objects": len(objs), "houses": len(houses),
            "terrain": bool(terrain)}


def import_layout(sf: SaveFile, v: Village, name: str, free: bool = True,
                  replace: bool = True) -> dict:
    if safety.running_game_processes():
        raise SaveFileError("quit the game before importing a village loadout (save must not be live)")
    path = _path(name)
    if not path.is_file():
        raise SaveFileError(f"no preset named {name!r}")
    data = json.loads(path.read_text(encoding="utf-8"))
    map_id = data.get("mapId") or MAP_BASE
    kind = data.get("kind") or "map"
    removed = 0
    if replace:
        st = v.state(sf, map_id=map_id, kind=kind)
        for p in list(st.get("placed") or []):
            cat = p.get("category") or ""
            if cat in ("LAND", "WATER"):
                continue
            h = p.get("handle")
            if h is None:
                continue
            # House shells need exParam cleanup — skip (move/place_house on import instead)
            if cat in ("HOUSE", "GUILD_HOUSE") or p.get("houseId"):
                continue
            try:
                v.remove(sf, int(h), free=True)
                removed += 1
            except Exception:
                pass
    placed_n = 0
    notes = []
    for o in data.get("objects") or []:
        cid = o.get("craftObjId")
        if not cid or cid in SKIP_IDS:
            continue
        cat = (v.objects.get(cid) or {}).get("category") or o.get("category") or ""
        if cat in ("LAND", "WATER"):
            continue
        try:
            hid = None
            if cat in ("HOUSE", "GUILD_HOUSE"):
                for hid0, meta in (v.houses or {}).items():
                    if meta.get("craftObj") == cid or meta.get("craftObjId") == cid:
                        hid = hid0
                        break
            if hid:
                v.place_house(sf, hid, list(o.get("location") or [0, 0, 0]),
                              list(o.get("rotation") or [0, 0, 0]), free=free, map_id=map_id)
            else:
                v.place(sf, cid, map_id, list(o.get("location") or [0, 0, 0]),
                        list(o.get("rotation") or [0, 0, 0]), free=free, kind=kind)
            placed_n += 1
        except Exception as e:
            notes.append(f"{cid}: {e}")
    return {
        "name": name,
        "mapId": map_id,
        "removed": removed,
        "placed": placed_n,
        "notes": notes[:20],
        "village": v.state(sf, map_id=map_id, kind=kind),
    }


def delete_preset(name: str) -> dict:
    path = _path(name)
    if path.is_file():
        path.unlink()
    return {"deleted": name}
