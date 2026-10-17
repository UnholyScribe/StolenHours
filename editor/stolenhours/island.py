"""Island building: debris (obstacles), terrain shave flags, and the three craftable maps.

Maps (from GDSWorldMapData + obstacle tables):
- Personal island / Base Camp = `Map_000100` (craft area 50x50x150 in `m_CraftAreaStatus`)
- Past / The Depths = `Map_000101` overworld; craft floors `Map_000202` / `000212` / `000222`
- Big island / Ginormosia = `Map_200000` (`m_HugeMapStatusP` area ranks; build voxels in GDSHugeMapData)

Debris (verified against Unholy's save after clearing the starter house in game):
- `m_FlagStatus.GlobalSyncByteFlag[idx]` = 255 when cleared (`GDSGlobalSyncByteFlag` id -> idx)
- Matching `craftObjStatusPArray` entry (`refCraftObjId` from `GDSMapObstaclePlacement`) is zeroed
- Its handle is dropped from the craft area's `craftObjStHdlArray`
- `playCountData.obstacleReleaseNum` may rise (was still 0 after myhouse; counter UNVERIFIED)

Terraform (verified structure; in-game raise/lower semantics UNVERIFIED):
- `craftObjStatusPArray` land_obj / water_obj cells; `objStatusBitFlag` bit 1 = Shave
- 314 Shave cells on Unholy's save after early terraforming

UNVERIFIED until load-tested: clearing by flag+craft wipe matches a full in-game reclaim; Shave bit =
raise vs lower vs flatten.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import paths, uiassets
from .savefile import SaveFile, SaveFileError

GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"
DATA_FILE = paths.UI_ASSET_DIR / "island" / "island.json"
DATA_PATTERN = (
    r"^Game/Content/GameData/(System/GDSGlobalSyncByteFlag|Map/GDSMapText_Noun|"
    r"Map/Map_000100/Map_000100_GDSMapObstaclePlacement|"
    r"Map/Map_000202/Map_000202_GDSMapObstaclePlacement|"
    r"Map/Map_000212/Map_000212_GDSMapObstaclePlacement|"
    r"Map/Map_000222/Map_000222_GDSMapObstaclePlacement|"
    r"Item/GDSItemText_Noun)\.uasset$"
)
CLEARED = 255
SHAVE = 1
EMPTY_CRAFT = {
    "Handle": {"handle": 0}, "exParamHandle": {"handle": 0}, "craftObjId": "None", "viewPatternId": "None",
    "Location": [0.0, 0.0, 0.0], "Rotation": [0.0, 0.0, 0.0], "gridIdx": -1, "mapId": 0, "objStatusBitFlag": 0,
}
# User-facing groups for the three islands + Depths craft floors
MAP_GROUPS = [
    {"id": "base", "name": "Base Camp", "map": "Map_000100", "kind": "personal"},
    {"id": "depths_b1", "name": "Depths – B1", "map": "Map_000202", "kind": "past"},
    {"id": "depths_b2", "name": "Depths – B2", "map": "Map_000212", "kind": "past"},
    {"id": "depths_b3", "name": "Depths – B3", "map": "Map_000222", "kind": "past"},
]
TYPE_LABEL = {
    "EObstacleType::Reclaim": "Debris",
    "EObstacleType::DebrisRemoval": "Debris",
    "EObstacleType::Removal": "Clearable",
}


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "System" / "GDSGlobalSyncByteFlag.json").exists() \
            or not (GAME_DATA / "Map" / "Map_000100" / "Map_000100_GDSMapObstaclePlacement.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)


def _rows(rel: str) -> dict:
    props = json.loads((GAME_DATA / rel).read_text(encoding="utf-8"))[0]["Properties"]
    return {(r["Key"]["Name"] if isinstance(r["Key"], dict) else r["Key"]): r["Value"] for r in props["m_dataMap"]}


def _nouns(rel: str) -> dict[str, str]:
    out = {}
    for k, v in _rows(rel).items():
        info = (v.get("textInfo") or [{}])[0]
        out[k] = (info.get("nounSingularForm_en") or info.get("text_en") or "").strip()
    return out


def _label(oid: str, otype: str) -> str:
    kind = TYPE_LABEL.get(otype, otype.split("::")[-1] if "::" in otype else otype or "Obstacle")
    m = re.search(r"(reclaim|removal|lift|repair|guild|myhouse)_?(\w*)$", oid, re.I)
    if not m:
        return kind
    tag, rest = m.group(1).lower(), m.group(2)
    nice = {"reclaim": "Debris", "removal": "Clearable", "lift": "Lift", "repair": "Repair",
            "guild": "Guild hall site", "myhouse": "Your house site"}
    base = nice.get(tag, kind)
    if rest and tag == "removal":
        return f"{base} ({rest.replace('_', ' ')})"
    if rest and tag == "reclaim" and rest.isdigit():
        return f"{base} #{int(rest) + 1}"
    return base


def build(out: Path | None = None, log=print) -> dict:
    out = out or DATA_FILE.parent
    if not (GAME_DATA / "System" / "GDSGlobalSyncByteFlag.json").exists():
        log("island: no exported data; run extract first")
        return {"missing": ["island data"]}
    sync = _rows("System/GDSGlobalSyncByteFlag.json")
    items = _nouns("Item/GDSItemText_Noun.json")
    obstacles = []
    for group in MAP_GROUPS:
        mid = group["map"]
        place_path = f"Map/{mid}/{mid}_GDSMapObstaclePlacement.json"
        try:
            places = _rows(place_path)
        except FileNotFoundError:
            places = {}
        for oid, flag in sync.items():
            if f"obstacle_{mid}_" not in oid and not (mid == "Map_000100" and oid.startswith("obstacle_Map_000100_")):
                continue
            if not oid.startswith("obstacle_"):
                continue
            p = places.get(oid) or {}
            reward = p.get("rewardItemInfo") or {}
            cond = p.get("releaseCond") or {}
            obstacles.append({
                "id": oid, "idx": flag["idx"], "map": mid, "group": group["id"],
                "name": _label(oid, p.get("Type") or ""), "type": (p.get("Type") or "").split("::")[-1] or "Obstacle",
                "craft": p.get("refCraftObjId") or None,
                "friends": int((cond.get("friendNum") or 0)),
                "reward": reward.get("ID") if reward.get("ID") not in (None, "None") else None,
                "rewardNum": int(reward.get("Num") or 0),
                "rewardName": items.get(reward.get("ID") or "") or None,
                "hidden": bool(p.get("mapIconHidden")),
            })
    # any sync obstacle not covered (test flags skipped)
    known = {o["id"] for o in obstacles}
    for oid, flag in sync.items():
        if not oid.startswith("obstacle_") or oid in known:
            continue
        m = re.match(r"obstacle_(Map_\w+)_", oid)
        mid = m.group(1) if m else "unknown"
        group = next((g["id"] for g in MAP_GROUPS if g["map"] == mid), "other")
        obstacles.append({
            "id": oid, "idx": flag["idx"], "map": mid, "group": group,
            "name": _label(oid, ""), "type": "Obstacle", "craft": None, "friends": 0,
            "reward": None, "rewardNum": 0, "rewardName": None, "hidden": False,
        })
    obstacles.sort(key=lambda o: (o["group"], o["idx"]))
    data = {
        "maps": MAP_GROUPS + [
            {"id": "ginormosia", "name": "Ginormosia", "map": "Map_200000", "kind": "huge"},
            {"id": "depths", "name": "The Depths", "map": "Map_000101", "kind": "past"},
        ],
        "obstacles": obstacles,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "island.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"island: {len(obstacles)} obstacles across {len(MAP_GROUPS)} craft maps -> {out}")
    return {"obstacles": len(obstacles)}


class Island:
    def __init__(self, data: dict):
        self.maps = data["maps"]
        self.obstacles: dict[str, dict] = {o["id"]: o for o in data["obstacles"]}

    @classmethod
    def load(cls, path: Path | None = None) -> "Island":
        p = path or DATA_FILE
        if not p.exists():
            raise FileNotFoundError(p)
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def state(self, sf: SaveFile) -> dict:
        flags = sf.sd["m_FlagStatus"]["GlobalSyncByteFlag"]
        crafts = {o["craftObjId"]: o for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
                  if o.get("craftObjId") not in (None, "None", "")}
        rows = []
        for o in self.obstacles.values():
            val = flags[o["idx"]] if o["idx"] < len(flags) else 0
            craft_here = bool(o.get("craft") and o["craft"] in crafts)
            # Cleared house: flag 255 and craft object gone. Uncleared: flag 0 and craft still there.
            cleared = val == CLEARED
            rows.append({**o, "flag": val, "cleared": cleared, "craftPresent": craft_here,
                         "rewardName": o.get("rewardName")})
        by_group: dict[str, list] = {}
        for r in rows:
            by_group.setdefault(r["group"], []).append(r)
        terra = self.terrain_summary(sf)
        huge = []
        for a in sf.sd["m_HugeMapStatusP"]["areaStatus"]:
            key = a["key"] if isinstance(a, dict) and "key" in a else None
            val = a["value"] if isinstance(a, dict) and "value" in a else a
            if key is None and isinstance(a, dict):
                # Map serialization sometimes stores as list of {key,value}
                continue
            if not isinstance(val, dict):
                continue
            huge.append({"id": key, "rank": val.get("nowAreaRank", 0), "release": val.get("releaseAreaRank", 0),
                         "points": val.get("AreaPoint", 0)})
        if not huge:
            # alternate: already a list of area dicts keyed externally
            areas = sf.sd["m_HugeMapStatusP"]["areaStatus"]
            if isinstance(areas, list):
                for i, val in enumerate(areas):
                    if isinstance(val, dict) and "nowAreaRank" in val:
                        huge.append({"id": f"area{i+1:03d}", "rank": val.get("nowAreaRank", 0),
                                     "release": val.get("releaseAreaRank", 0), "points": val.get("AreaPoint", 0)})
            elif isinstance(areas, dict):
                for key, val in areas.items():
                    if isinstance(val, dict):
                        huge.append({"id": key, "rank": val.get("nowAreaRank", 0),
                                     "release": val.get("releaseAreaRank", 0), "points": val.get("AreaPoint", 0)})
        houses = []
        for h in sf.sd["m_CraftStatus"]["CraftExParamP"].get("exParamHouse") or []:
            hid = (h.get("houseDataId") or {})
            name = hid.get("Name") if isinstance(hid, dict) else hid
            if name in (None, "None", ""):
                continue
            houses.append({
                "id": name,
                "map": h.get("placedMapId"),
                "entrance": h.get("entranceMapId"),
                "category": int(h.get("houseCategory") or 0),
                "planned": bool(h.get("isPlannedConstruct")),
                "rooms": len(h.get("indoorAreaStHdlArray") or []),
            })
        return {
            "maps": self.maps,
            "groups": by_group,
            "obstacles": rows,
            "cleared": sum(1 for r in rows if r["cleared"]),
            "remaining": sum(1 for r in rows if not r["cleared"]),
            "obstacleReleaseNum": sf.sd["m_PlayData"]["playCountData"]["obstacleReleaseNum"],
            "terrain": terra,
            "huge": huge,
            "houses": houses,
        }

    def terrain_summary(self, sf: SaveFile) -> dict:
        arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
        land = water = shaved_land = shaved_water = other_shave = 0
        for o in arr:
            cid = o.get("craftObjId")
            bit = int(o.get("objStatusBitFlag") or 0)
            if cid == "land_obj":
                land += 1
                if bit & SHAVE:
                    shaved_land += 1
            elif cid == "water_obj":
                water += 1
                if bit & SHAVE:
                    shaved_water += 1
            elif bit & SHAVE:
                other_shave += 1
        return {"land": land, "water": water, "shavedLand": shaved_land, "shavedWater": shaved_water,
                "otherShave": other_shave, "shaved": shaved_land + shaved_water + other_shave}

    def clear_obstacles(self, sf: SaveFile, ids: list[str]) -> int:
        """Mark debris cleared the same way the game did for the house site."""
        if not ids:
            return 0
        flags = sf.sd["m_FlagStatus"]["GlobalSyncByteFlag"]
        arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
        n = 0
        for oid in ids:
            o = self.obstacles.get(oid)
            if not o:
                raise SaveFileError(f"unknown obstacle {oid}")
            if o["idx"] >= len(flags):
                raise SaveFileError(f"obstacle flag index out of range: {oid}")
            already = flags[o["idx"]] == CLEARED
            flags[o["idx"]] = CLEARED
            craft_id = o.get("craft")
            if craft_id:
                for i, slot in enumerate(arr):
                    if slot.get("craftObjId") != craft_id:
                        continue
                    h = (slot.get("Handle") or {}).get("handle") or 0
                    arr[i] = {k: (list(v) if isinstance(v, list) else
                                  (dict(v) if isinstance(v, dict) else v)) for k, v in EMPTY_CRAFT.items()}
                    self._drop_handle(sf, h)
            if not already:
                n += 1
        if n:
            sf.sd["m_PlayData"]["playCountData"]["obstacleReleaseNum"] = int(
                sf.sd["m_PlayData"]["playCountData"]["obstacleReleaseNum"]) + n
            sf.dirty = True
        return n

    def _drop_handle(self, sf: SaveFile, handle: int) -> None:
        if not handle:
            return
        areas = sf.sd["m_CraftAreaStatus"]
        for key in ("mapCraftAreaStatusPList", "outdoorCraftAreaStatusPList", "indoorCraftAreaStatusPList",
                    "wallCraftAreaStatusPList", "ceilingCraftAreaStatusPList"):
            for area in areas.get(key) or []:
                for field in ("craftObjStHdlArray", "putCraftObjStHdlArray"):
                    lst = area.get(field)
                    if not lst:
                        continue
                    area[field] = [h for h in lst if (h.get("handle") if isinstance(h, dict) else h) != handle]

    def reset_shave(self, sf: SaveFile) -> int:
        """Clear every Shave bit on craft objects (undo offline terraforming edits). UNVERIFIED in game."""
        arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
        n = 0
        for o in arr:
            bit = int(o.get("objStatusBitFlag") or 0)
            if bit & SHAVE:
                o["objStatusBitFlag"] = bit & ~SHAVE
                n += 1
        if n:
            sf.dirty = True
        return n
