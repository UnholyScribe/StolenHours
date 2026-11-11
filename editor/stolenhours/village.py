"""Village / house craft editor: catalog, place/move/remove furniture & houses.

Save layout (verified on Unholy's save; see FINDINGS):
- `m_CraftStatus.craftObjStatusPArray` — placed craft objects (65535 slots)
- `m_CraftAreaStatus.*CraftAreaStatusPList` — per-area grids + handle lists
- `CraftExParamP.exParamHouse` — house shells linked via `exParamHandle`
- Inventory pocket `invCraft` — bag stock for Legal placement mode

Numeric `craftObjStatusP.mapId` is NOT the string map id. Loom CONFIRMED
`zlib.crc32(mapId.encode("utf-32-le")) & 0xFFFFFFFF` (2026-11-10). Editor encodes any map
string; learn-from-save remains as assert/fallback.

gridIdx (Base Camp / map Category 0): `ix * Width + iy + iz * Width * Depth`
with Location = origin + (ix,iy,iz) * voxel. Outdoor origin comes from land_obj grid 0
(or derived from any object). Indoor Category 2 uses `ix + iy * Width + …` (axis swap).

Handle packing: `(serial << 16) | index` where index is the craftObjStatusPArray slot
(same pattern as inventory item handles). Serial = max existing high-word + 1.
"""
from __future__ import annotations

import copy
import json
import math
import zlib
from pathlib import Path

from . import paths, uiassets
from .savefile import EMPTY_IDS, SaveFile, SaveFileError

GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"
DATA_FILE = paths.UI_ASSET_DIR / "village" / "craft.json"
DATA_PATTERN = (
    r"^Game/Content/GameData/(Craft/GDS(CraftObj(Data|VisualData|ShapeData)|HouseData|RoomData|"
    r"Indoor(Design|Parts|Structure)Data|MapCraftArea|NPCRoomData)|"
    r"Item/GDSItem(CraftData|Text_Noun))\.uasset$"
)

EMPTY_CRAFT = {
    "Handle": {"handle": 0}, "exParamHandle": {"handle": 0}, "craftObjId": "None", "viewPatternId": "None",
    "Location": [0.0, 0.0, 0.0], "Rotation": [0.0, 0.0, 0.0], "gridIdx": -1, "mapId": 0, "objStatusBitFlag": 0,
}
AREA_LISTS = (
    "mapCraftAreaStatusPList", "outdoorCraftAreaStatusPList", "indoorCraftAreaStatusPList",
    "wallCraftAreaStatusPList", "ceilingCraftAreaStatusPList",
)
# Categories that are placeable furniture / buildings in the editor (not terrain / limits)
PLACE_CATS = {
    "OBJECT", "TABLE", "WALLDECO", "RUG", "HOUSE", "BRIDGE", "FENCE", "ROAD", "SLOPE",
    "TAMAGEMONO", "LUNCH_EATS", "LUNCH_DRINK", "GUILD_SQUARE", "GUILD_HOUSE", "PICK",
    "VEGETABLE_FIELD", "PLANNED_CONSTRUCT",
}
SKIP_IDS = {"land_obj", "water_obj", "None", ""}
MAP_BASE = "Map_000100"
MAP_MYHOUSE = "Map_MyHouse"
def encode_map_id(map_id: str) -> int:
    """Loom CONFIRMED: craftObjStatusP.mapId = CRC32(UTF-32LE map string)."""
    return zlib.crc32(str(map_id).encode("utf-32-le")) & 0xFFFFFFFF


# Known pairs (also encode_map_id); kept for tests / pack mapidLookup.
MAP_ID_NUMERIC = {
    "Map_000100": encode_map_id("Map_000100"),
    "Map_MyHouse": encode_map_id("Map_MyHouse"),
    "NPCEmptyRoom_00": encode_map_id("NPCEmptyRoom_00"),
    "NPCEmptyRoom_01": encode_map_id("NPCEmptyRoom_01"),
}
# Loom M2: pack is sole mesh resolution source for Village/island viewer (read-only).
PACK_FILE = paths.UI_ASSET_DIR / "village" / "basecamp_pack.json"
_VOXEL_XY = 50
_VOXEL_Z = 150
ISLAND_VOXEL = {"xy": _VOXEL_XY, "z": _VOXEL_Z, "land_z": (-150, 0, 150), "water_z": (-150,)}
# objStatusBitFlag — Shave CONFIRMED; Put / Planned POSSIBLE (Loom M2).
STATUS_BITFLAGS = {
    "shave": {"bit": 0, "mask": 1, "confidence": "CONFIRMED"},
    "put": {"bit": 1, "mask": 2, "confidence": "POSSIBLE"},
    "planned_construct": {"bit": 2, "mask": 4, "confidence": "POSSIBLE"},
}


def load_pack(path: Path | None = None) -> dict:
    p = path or PACK_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _build_mesh_index(pack: dict | None = None) -> dict[str, dict]:
    """craftObjId → mesh/glb keys from Loom pack only (M2 read-only resolve)."""
    pack = pack if pack is not None else load_pack()
    out: dict[str, dict] = {}
    furn = pack.get("furniture") or {}
    with_glb = furn.get("with_glb") or {}
    if isinstance(with_glb, dict):
        for rows in with_glb.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                cid = row.get("craftObjId")
                if not cid:
                    continue
                out[cid] = {
                    "craftObjId": cid,
                    "source": "furniture",
                    "name": row.get("name"),
                    "bp": row.get("bp"),
                    "meshes": list(row.get("meshes") or []),
                    "glbs": list(row.get("glbs_on_disk") or []),
                }
    # Terrain LAND variants (ids only in pack; visuals named *_visual).
    tv = pack.get("terrain_obj_variants") or {}
    ids = tv.get("ids") if isinstance(tv, dict) else None
    if isinstance(ids, list):
        for cid in ids:
            out.setdefault(cid, {
                "craftObjId": cid,
                "source": "terrain",
                "name": cid,
                "bp": None,
                "meshes": [],
                "glbs": [],
                "visual": f"{cid}_visual" if not str(cid).endswith("_visual") else cid,
            })
    return out


def resolve_pack_mesh(craft_obj_id: str, pack: dict | None = None) -> dict | None:
    """Read-only mesh resolve for Village/island viewer. Pack is sole source."""
    cid = str(craft_obj_id or "")
    if not cid or cid in EMPTY_IDS:
        return None
    idx = _build_mesh_index(pack)
    hit = idx.get(cid)
    if hit:
        return dict(hit)
    return None


def _mesh_tex_stem(mesh_path: str | None) -> str | None:
    """'/Game/.../mdl_cft010001_00' → 'tex_cft010001_00'."""
    if not mesh_path:
        return None
    name = Path(str(mesh_path).split(".")[0]).name
    if name.startswith("mdl_"):
        return "tex_" + name[4:]
    if name.startswith("tex_"):
        return name
    return None


def _village_asset(name: str) -> Path:
    return paths.UI_ASSET_DIR / "village" / name


def load_house_design_preview() -> dict:
    p = _village_asset("house_design_preview.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_house_paint_preview() -> dict:
    p = _village_asset("house_paint_item_preview.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _craft3d_glb(rel_or_name: str) -> str | None:
    """Graphics/.../mdl_x.glb or mdl_x → craft3d-relative m/mdl_x.glb if present."""
    name = Path(str(rel_or_name).replace("\\", "/")).name
    if not name.endswith(".glb"):
        name = f"{name}.glb"
    if not name.startswith("mdl_"):
        return None
    root = paths.UI_ASSET_DIR / "craft3d" / "m" / name
    if root.exists():
        return f"m/{name}"
    return None


def design_preview(design_id: str | None) -> dict:
    """Loom CONFIRMED IndoorDesigen → cft* glb list + craft3d paths (00 tex fallback)."""
    did = str(design_id or "") or "ide_thatch_00"
    raw = load_house_design_preview()
    row = next((d for d in (raw.get("designs") or []) if d.get("design_id") == did), None)
    glbs_ue = list((row or {}).get("glbs") or [])
    meshes = list((row or {}).get("meshes") or [])
    craft = []
    for g in glbs_ue:
        rel = _craft3d_glb(g)
        if rel:
            craft.append(rel)
    # Prefer *_00 wall/floor shells for room drop-in when present.
    wall_shell = next((c for c in craft if "/mdl_cft01" in f"/{c}" and c.endswith("_00.glb")), None)
    floor_shell = next((c for c in craft if "/mdl_cft02" in f"/{c}" and c.endswith("_00.glb")), None)
    if wall_shell is None:
        wall_shell = next((c for c in craft if "mdl_cft01" in c), None)
    if floor_shell is None:
        floor_shell = next((c for c in craft if "mdl_cft02" in c), None)
    return {
        "designId": did,
        "partsN": (row or {}).get("parts_n"),
        "meshes": meshes,
        "glbsUe": glbs_ue,
        "glbsCraft3d": craft,
        "wallShell": wall_shell,
        "floorShell": floor_shell,
        "texFallback00": True,
        "parent": "basemat_obj_opq_00",
        "confidence": raw.get("confidence") or "CONFIRMED",
    }


def theme_for_design(design_id: str | None, pack: dict | None = None) -> dict:
    """walls_floors Type 117/118 → craft3d Diff/Nml/Rse + IndoorDesigen shell glbs (Loom)."""
    pack = pack if pack is not None else load_pack()
    did = str(design_id or "")
    if not did or did in EMPTY_IDS:
        did = "ide_thatch_00"
    rows = ((pack.get("walls_floors") or {}).get("rows") or [])
    wall = next((r for r in rows if r.get("designId") == did and int(r.get("Type") or 0) == 117), None)
    floor = next((r for r in rows if r.get("designId") == did and int(r.get("Type") or 0) == 118), None)
    if wall is None:
        wall = next((r for r in rows if r.get("designId") == did), None)
    if floor is None:
        floor = next((r for r in rows if r.get("designId") == did and r is not wall), None)
    preview = design_preview(did)

    def _slot(row: dict | None, kind: str) -> dict:
        meshes = list((row or {}).get("meshes") or [])
        stem = _mesh_tex_stem(meshes[0] if meshes else None)
        # Variant NN≠00 binds Tex/Mat from cft*/00 (Loom CONFIRMED).
        if stem and not stem.endswith("_00"):
            parts = stem.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                stem = f"{parts[0]}_00"
        out = {
            "designId": did,
            "kind": kind,
            "itemId": (row or {}).get("itemId"),
            "name": (row or {}).get("name"),
            "indoorFolder": (row or {}).get("indoor_folder"),
            "meshes": meshes,
            "stem": stem,
            "dif": f"t/{stem}_dif.webp" if stem else None,
            "nml": f"t/{stem}_nml.webp" if stem else None,
            "rse": f"t/{stem}_rse.webp" if stem else None,
            "shell": preview.get("wallShell" if kind == "wall" else "floorShell"),
        }
        if kind == "floor":
            # Loom CONFIRMED mat_cft020001_00 Vertex_Color 0.25
            out["vertexColor"] = [0.25, 0.25, 0.25, 1.0]
            out["normalPower"] = 0.5
        else:
            out["vertexColor"] = [1.0, 1.0, 1.0, 1.0]
            out["normalPower"] = 1.0
        return out

    return {
        "designId": did,
        "wall": _slot(wall, "wall"),
        "floor": _slot(floor, "floor"),
        "parent": "basemat_obj_opq_00",
        "preview": preview,
        "texFallback00": True,
    }


def indoor_design_id(area: dict) -> str | None:
    """Prefer area defaultIndoorDesignId, else first childIndoorPartrsInfoArray designId."""
    raw = area.get("defaultIndoorDesignId")
    name = _name(raw) if not isinstance(raw, str) else (None if raw in EMPTY_IDS else raw)
    if name:
        return name
    for child in area.get("childIndoorPartrsInfoArray") or []:
        n = _name(child.get("designId"))
        if n:
            return n
    return None


def extract(force: bool = False) -> None:
    need = [
        GAME_DATA / "Craft" / "GDSCraftObjData.json",
        GAME_DATA / "Craft" / "GDSCraftObjVisualData.json",
        GAME_DATA / "Item" / "GDSItemCraftData.json",
    ]
    if force or not all(p.exists() for p in need):
        uiassets._run_extractor("json", DATA_PATTERN)


def _rows(rel: str) -> dict:
    props = json.loads((GAME_DATA / rel).read_text(encoding="utf-8"))[0]["Properties"]
    return {(r["Key"]["Name"] if isinstance(r["Key"], dict) else r["Key"]): r["Value"] for r in props["m_dataMap"]}


def _name(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, dict):
        n = v.get("Name")
        return None if n in EMPTY_IDS else n
    return None if v in EMPTY_IDS else str(v)


def _nouns() -> dict[str, str]:
    """English display names. Keys are both `name_ico…` and bare `ico…` / `icf…`."""
    out = {}
    for k, v in _rows("Item/GDSItemText_Noun.json").items():
        info = (v.get("textInfo") or [{}])[0]
        en = (info.get("nounSingularForm_en") or info.get("text_en") or "").strip()
        if not en:
            continue
        out[k] = en
        if k.startswith("name_"):
            out[k[5:]] = en
    return out


# Known shells the noun table doesn't label (guild test BP, islander kits).
_NAME_ALIAS = {
    "house_guild_thatch": "Thatched Guild Office",
    "obj_cft_guild_house_test_2": "Thatched Guild Office",
    "house_icf01021030": "Thatched House (Islander)",
    "obj_icf01021030": "Thatched House (Islander)",
}


def _display_name(nouns: dict[str, str], item_id: str | None, craft_obj_id: str) -> str:
    if craft_obj_id in _NAME_ALIAS:
        return _NAME_ALIAS[craft_obj_id]
    if item_id:
        n = nouns.get(item_id) or nouns.get(f"name_{item_id}")
        if n:
            return n
    # craft id obj_ico… → ico…
    bare = craft_obj_id[4:] if craft_obj_id.startswith("obj_") else craft_obj_id
    if bare in _NAME_ALIAS:
        return _NAME_ALIAS[bare]
    # strip variant suffixes like _01 for bridges when looking up base noun
    n = nouns.get(bare) or nouns.get(f"name_{bare}")
    if n:
        return n
    base = bare.rsplit("_", 1)[0] if "_" in bare else bare
    return nouns.get(base) or nouns.get(f"name_{base}") or craft_obj_id


def _cat(raw) -> str:
    s = str(raw or "")
    return s.split("::")[-1] if "::" in s else s


def _bp_path(visual: dict) -> str | None:
    bp = visual.get("bpPath") or {}
    path = bp.get("AssetPathName") if isinstance(bp, dict) else None
    if not path or path in EMPTY_IDS:
        return None
    return path.split(".")[0]


def build(out: Path | None = None, log=print) -> dict:
    out = out or DATA_FILE.parent
    if not (GAME_DATA / "Craft" / "GDSCraftObjData.json").exists():
        log("village: no exported Craft data; run extract first")
        return {"missing": ["craft data"]}
    nouns = _nouns()
    objs = _rows("Craft/GDSCraftObjData.json")
    visuals = _rows("Craft/GDSCraftObjVisualData.json")
    houses = {}
    try:
        houses = _rows("Craft/GDSHouseData.json")
    except FileNotFoundError:
        pass
    item_to_obj: dict[str, str] = {}
    obj_to_item: dict[str, str] = {}
    try:
        for iid, row in _rows("Item/GDSItemCraftData.json").items():
            oid = _name(row.get("craftObjId"))
            if not oid:
                continue
            item_to_obj[iid] = oid
            obj_to_item.setdefault(oid, iid)
    except FileNotFoundError:
        pass

    catalog = []
    for oid, row in objs.items():
        cat = _cat(row.get("Category"))
        if cat not in PLACE_CATS and not oid.startswith(("obj_ico", "obj_icf")):
            continue
        if oid in SKIP_IDS or oid.startswith("obstacle_"):
            continue
        vid = row.get("craftObjVisualId")
        vis = visuals.get(vid) or {}
        size = vis.get("Size") or {}
        house_id = _name((row.get("HouseData") or {}).get("houseDataId"))
        item_id = obj_to_item.get(oid)
        # item id often matches without obj_ prefix
        if not item_id and oid.startswith("obj_"):
            cand = oid[4:]
            if cand in item_to_obj:
                item_id = cand
            elif nouns.get(cand) or nouns.get(f"name_{cand}"):
                item_id = cand
        name = _display_name(nouns, item_id, oid)
        catalog.append({
            "id": oid,
            "itemId": item_id,
            "name": name,
            "category": cat,
            "action": _cat(row.get("ActionType")),
            "w": int(size.get("Width") or 1),
            "d": int(size.get("Depth") or 1),
            "h": int(size.get("Height") or 1),
            "shape": vis.get("shapeDataId"),
            "visual": vid,
            "bp": _bp_path(vis),
            "houseId": house_id,
        })
    catalog.sort(key=lambda c: (c["category"], c["name"].lower(), c["id"]))

    house_rows = []
    for hid, row in houses.items():
        # house_icf01020030 → icf01020030 for noun lookup
        itemish = hid.replace("house_", "", 1) if hid.startswith("house_") else hid
        house_rows.append({
            "id": hid,
            "name": _display_name(nouns, itemish, hid),
            "structure": _name(row.get("structureId")),
            "design": _name(row.get("defaultDesignId")),
            "category": int(row.get("houseCategory") or 0),
            "forceMap": row.get("forceMapId") if row.get("forceMapId") not in EMPTY_IDS else None,
            "craftObj": next((c["id"] for c in catalog if c.get("houseId") == hid), None),
        })
    house_rows.sort(key=lambda h: (h["name"].lower(), h["id"]))

    # Loom Base Camp pack (walls/floors Type 117/118 + landmarks) when banked into UI assets.
    pack_path = out / "basecamp_pack.json"
    pack = {}
    if pack_path.exists():
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pack = {}
    walls_floors = list((pack.get("walls_floors") or {}).get("rows") or [])
    paint = load_house_paint_preview()
    paint_by_item = {}
    for bucket in ("walls_type117", "floors_type118"):
        for row in paint.get(bucket) or []:
            iid = row.get("itemId")
            if iid:
                paint_by_item[iid] = row
    for row in walls_floors:
        hit = paint_by_item.get(row.get("itemId")) or {}
        if hit.get("preview_glbs"):
            row["previewGlbs"] = list(hit["preview_glbs"])
            row["previewMeshes"] = list(hit.get("preview_meshes") or [])
            row["previewCraft3d"] = [p for g in row["previewGlbs"] if (p := _craft3d_glb(g))]
    data = {
        "objects": catalog,
        "houses": house_rows,
        "maps": [
            {"id": MAP_BASE, "name": "Base Camp", "kind": "map"},
            {"id": MAP_MYHOUSE, "name": "My House", "kind": "indoor"},
        ],
        "wallsFloors": walls_floors,
        "houseDesignPreview": {
            "confidence": (load_house_design_preview() or {}).get("confidence"),
            "designN": len((load_house_design_preview() or {}).get("designs") or []),
            "texFallback00": True,
        },
        "landmarks": pack.get("landmarks") or {},
        "terrainOps": pack.get("terrain") or {
            "voxel_z": 150, "base_z": -150, "shave_mask": 1,
            "ops": ["hgrm_landPileUp", "hgrm_landDig", "ShaveLand"],
        },
        # Loom pack slices (meshes/coverage) — Village UI reads what it needs.
        "outdoor": pack.get("outdoor") or {},
        "outdoorCoverage": pack.get("outdoor_coverage") or {},
        "buildings": pack.get("buildings") or {},
        "landCells": pack.get("land_cells") or [],
        "furnitureCoverage": pack.get("furniture_coverage") or {},
        "furniturePack": pack.get("furniture") or {},
        "indoorParts": pack.get("indoor_parts_meshes") or {},
        "plannedConstruct": pack.get("planned_construct") or [],
        "terrainObjVariants": pack.get("terrain_obj_variants") or {},
        "fenceHedgeVpc": pack.get("fence_hedge_vpc") or {},
        "waterVpc": pack.get("water_vpc") or {},
        "bridgeVpc": pack.get("bridge_vpc") or {},
        "mapidLookup": pack.get("mapid_lookup") or dict(MAP_ID_NUMERIC),
        "islandVoxel": dict(ISLAND_VOXEL),
        "statusBitflags": dict(STATUS_BITFLAGS),
        "meshIndex": _build_mesh_index(pack),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "craft.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"village: {len(catalog)} craft objects, {len(house_rows)} houses -> {out}")
    return {"objects": len(catalog), "houses": len(house_rows)}


def _handle_val(h) -> int:
    if isinstance(h, dict):
        return int(h.get("handle") or h.get("Handle") or 0)
    return int(h or 0)


def _area_handles(area: dict) -> list[int]:
    out = []
    for field in ("craftObjStHdlArray", "putCraftObjStHdlArray"):
        for h in area.get(field) or []:
            v = _handle_val(h)
            if v:
                out.append(v)
    return out


class Village:
    def __init__(self, data: dict):
        self.objects = {o["id"]: o for o in data["objects"]}
        self.houses = {h["id"]: h for h in data.get("houses") or []}
        self.maps = data.get("maps") or []

    @classmethod
    def load(cls, path: Path | None = None) -> "Village":
        p = path or DATA_FILE
        if not p.exists():
            raise FileNotFoundError(p)
        return cls(json.loads(p.read_text(encoding="utf-8")))

    # ---- geometry helpers ----------------------------------------------------
    @staticmethod
    def _axis_order(category: int) -> str:
        # Both outdoor and indoor use ix-major: grid = ix * Width + iy
        # (MyHouse Tropical Bed grid 25 + Wooden Bucket grid 10 verified 2026-10-15).
        # Earlier "indoor iy-major" note was wrong.
        return "xy"

    @classmethod
    def _unpack_grid(cls, grid: int, area: dict) -> tuple[int, int, int]:
        w = int(area["Width"])
        d = int(area["Depth"])
        layer = w * d
        iz = int(grid) // layer if layer else 0
        rem = int(grid) % layer if layer else 0
        # grid = ix * Width + iy
        ix, iy = (rem // w, rem % w) if w else (0, 0)
        return ix, iy, iz

    @classmethod
    def _pack_grid(cls, ix: int, iy: int, iz: int, area: dict) -> int:
        w = int(area["Width"])
        rem = ix * w + iy
        return rem + iz * w * int(area["Depth"])

    @classmethod
    def area_origin(cls, area: dict, sf: SaveFile | None = None) -> tuple[float, float, float]:
        """World origin of grid (0,0,0) in cm."""
        loc = area.get("Location") or [0.0, 0.0, 0.0]
        oz = float(loc[2]) if len(loc) > 2 else 0.0
        # Prefer land_obj / any object at grid 0 on this area
        if sf is not None:
            hdls = set(_area_handles(area))
            arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
            for o in arr:
                if (o.get("Handle") or {}).get("handle") not in hdls:
                    continue
                if int(o.get("gridIdx") or -1) == 0:
                    L = o["Location"]
                    return float(L[0]), float(L[1]), float(L[2])
            # derive from any object
            for o in arr:
                if (o.get("Handle") or {}).get("handle") not in hdls:
                    continue
                if o.get("craftObjId") in SKIP_IDS or o.get("craftObjId") in EMPTY_IDS:
                    continue
                g = int(o.get("gridIdx") or -1)
                if g < 0:
                    continue
                ix, iy, iz = cls._unpack_grid(g, area)
                vw = float(area.get("voxelWidth") or 50)
                vd = float(area.get("voxelDepth") or 50)
                vh = float(area.get("voxelHeight") or 100)
                L = o["Location"]
                return float(L[0]) - ix * vw, float(L[1]) - iy * vd, float(L[2]) - iz * vh
        # Indoor default: room centered on area Location (UNVERIFIED empty-room place)
        vw = float(area.get("voxelWidth") or 50)
        vd = float(area.get("voxelDepth") or 50)
        w, d = int(area["Width"]), int(area["Depth"])
        return float(loc[0]) - (w * vw) / 2 + vw / 2, float(loc[1]) - (d * vd) / 2 + vd / 2, oz

    @classmethod
    def grid_to_loc(cls, ix: int, iy: int, iz: int, area: dict, origin: tuple[float, float, float]) -> list[float]:
        vw = float(area.get("voxelWidth") or 50)
        vd = float(area.get("voxelDepth") or 50)
        vh = float(area.get("voxelHeight") or 100)
        ox, oy, oz = origin
        return [ox + ix * vw, oy + iy * vd, oz + iz * vh]

    @classmethod
    def loc_to_grid(cls, loc: list[float], area: dict, origin: tuple[float, float, float]) -> tuple[int, int, int, int]:
        vw = float(area.get("voxelWidth") or 50)
        vd = float(area.get("voxelDepth") or 50)
        vh = float(area.get("voxelHeight") or 100)
        ox, oy, oz = origin
        ix = int(round((float(loc[0]) - ox) / vw))
        iy = int(round((float(loc[1]) - oy) / vd))
        iz = int(round((float(loc[2]) - oz) / vh))
        return ix, iy, iz, cls._pack_grid(ix, iy, iz, area)

    # ---- area / mapId lookup -------------------------------------------------
    def _iter_areas(self, sf: SaveFile):
        cas = sf.sd["m_CraftAreaStatus"]
        for list_name in AREA_LISTS:
            for area in cas.get(list_name) or []:
                mid = area.get("mapId")
                if mid in EMPTY_IDS:
                    continue
                yield list_name, area

    def find_area(self, sf: SaveFile, map_id: str, kind: str | None = None) -> tuple[str, dict]:
        """Return (list_name, area). kind: map|indoor|wall|ceiling|outdoor or None."""
        prefer = {
            "map": ("mapCraftAreaStatusPList",),
            "outdoor": ("outdoorCraftAreaStatusPList",),
            "indoor": ("indoorCraftAreaStatusPList",),
            "wall": ("wallCraftAreaStatusPList",),
            "ceiling": ("ceilingCraftAreaStatusPList",),
        }
        lists = prefer.get(kind) if kind else AREA_LISTS
        for list_name, area in self._iter_areas(sf):
            if lists and list_name not in lists:
                continue
            if area.get("mapId") == map_id:
                return list_name, area
        raise SaveFileError(f"no craft area for map {map_id}" + (f" ({kind})" if kind else ""))

    def numeric_map_id(self, sf: SaveFile, area: dict) -> int:
        sid = area.get("mapId")
        if not sid or sid in EMPTY_IDS:
            raise SaveFileError("area has no mapId string to encode")
        encoded = encode_map_id(sid)
        # Assert against objects on this area when present (learn-from-save check).
        hdls = set(_area_handles(area))
        arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
        counts: dict[int, int] = {}
        for o in arr:
            if (o.get("Handle") or {}).get("handle") not in hdls:
                continue
            if o.get("craftObjId") in EMPTY_IDS:
                continue
            mid = int(o.get("mapId") or 0)
            if mid:
                counts[mid] = counts.get(mid, 0) + 1
        if counts and encoded not in counts:
            return max(counts.items(), key=lambda kv: kv[1])[0]
        return encoded

    def _obj_by_handle(self, sf: SaveFile, handle: int) -> dict | None:
        for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]:
            if (o.get("Handle") or {}).get("handle") == handle:
                return o
        return None

    def _index_by_handle(self, sf: SaveFile, handle: int) -> int:
        for i, o in enumerate(sf.sd["m_CraftStatus"]["craftObjStatusPArray"]):
            if (o.get("Handle") or {}).get("handle") == handle:
                return i
        raise SaveFileError(f"craft handle {handle} not found")

    # ---- inventory (Legal mode) ---------------------------------------------
    def inv_stock(self, sf: SaveFile) -> dict[str, dict]:
        """itemId -> {index, stock, name} for invCraft."""
        inv = sf.inventory.get("invCraft") or []
        out = {}
        for i, it in enumerate(inv):
            iid = it.get("ItemId")
            if iid in EMPTY_IDS:
                continue
            stock = int(it.get("stockNum") or 1)
            out[iid] = {"index": i, "stock": stock, "itemId": iid}
        return out

    def _consume_item(self, sf: SaveFile, item_id: str) -> None:
        inv = sf.inventory["invCraft"]
        for i, it in enumerate(inv):
            if it.get("ItemId") != item_id:
                continue
            if "stockNum" in it:
                n = int(it["stockNum"])
                if n <= 1:
                    # clear slot — keep trailing-empty convention by zeroing like empty
                    inv[i] = copy.deepcopy(it)
                    inv[i]["ItemId"] = "None"
                    if "stockNum" in inv[i]:
                        inv[i]["stockNum"] = 0
                else:
                    it["stockNum"] = n - 1
            else:
                inv[i]["ItemId"] = "None"
            sf.dirty = True
            return
        raise SaveFileError(f"{item_id} is not in your craft bag (Legal mode)")

    def _restore_item(self, sf: SaveFile, item_id: str) -> None:
        inv = sf.inventory["invCraft"]
        for it in inv:
            if it.get("ItemId") == item_id and "stockNum" in it:
                it["stockNum"] = int(it["stockNum"]) + 1
                sf.dirty = True
                return
        # add one via savefile helper when pocket already has a template
        try:
            sf.add_item("invCraft", item_id, stock=1)
        except SaveFileError:
            # no template / full — leave UNVERIFIED gap rather than corrupt
            raise SaveFileError(f"could not return {item_id} to invCraft")

    # ---- handle allocation --------------------------------------------------
    def _alloc_handle(self, sf: SaveFile, index: int) -> int:
        used = set()
        serials = []
        for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]:
            h = (o.get("Handle") or {}).get("handle") or 0
            if not h:
                continue
            used.add(h)
            serials.append((h & 0xFFFFFFFF) >> 16)
        serial = (max(serials) + 1) if serials else 1
        # keep low 16 = index; bump serial until unique
        for _ in range(0x10000):
            h = ((serial & 0xFFFF) << 16) | (index & 0xFFFF)
            # interpret as signed int32 like the save
            if h >= 0x80000000:
                h_signed = h - 0x100000000
            else:
                h_signed = h
            if h_signed not in used and h not in used:
                return h_signed
            serial = (serial + 1) & 0xFFFF
        raise SaveFileError("could not allocate craft handle")

    def _find_empty_slot(self, sf: SaveFile) -> int:
        arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
        for i, o in enumerate(arr):
            if o.get("craftObjId") in EMPTY_IDS and not ((o.get("Handle") or {}).get("handle") or 0):
                return i
        # also reuse zeroed debris slots (Handle 0, None id)
        for i, o in enumerate(arr):
            if o.get("craftObjId") in EMPTY_IDS:
                return i
        raise SaveFileError("craft object array is full")

    def _drop_handle(self, sf: SaveFile, handle: int) -> None:
        if not handle:
            return
        areas = sf.sd["m_CraftAreaStatus"]
        for key in AREA_LISTS:
            for area in areas.get(key) or []:
                for field in ("craftObjStHdlArray", "putCraftObjStHdlArray"):
                    lst = area.get(field)
                    if not lst:
                        continue
                    area[field] = [h for h in lst if _handle_val(h) != handle]

    # ---- public state -------------------------------------------------------
    def state(self, sf: SaveFile, map_id: str = MAP_BASE, kind: str | None = None) -> dict:
        if kind is None:
            kind = "indoor" if map_id == MAP_MYHOUSE or str(map_id).startswith("NPC") else "map"
        try:
            list_name, area = self.find_area(sf, map_id, kind if kind != "auto" else None)
        except SaveFileError:
            # fallback: any area with that mapId
            list_name, area = self.find_area(sf, map_id, None)
        origin = self.area_origin(area, sf)
        try:
            num_map = self.numeric_map_id(sf, area)
        except SaveFileError:
            num_map = 0
        hdls = _area_handles(area)
        placed = []
        for h in hdls:
            o = self._obj_by_handle(sf, h)
            if not o or o.get("craftObjId") in EMPTY_IDS or o.get("craftObjId") in SKIP_IDS:
                continue
            if str(o.get("craftObjId", "")).startswith("obstacle_"):
                continue
            if str(o.get("craftObjId", "")).startswith("obj_limit_"):
                continue
            meta = self.objects.get(o["craftObjId"]) or {}
            placed.append({
                "handle": h,
                "craftObjId": o["craftObjId"],
                "name": meta.get("name") or o["craftObjId"],
                "itemId": meta.get("itemId"),
                "category": meta.get("category") or "",
                "w": meta.get("w") or 1,
                "d": meta.get("d") or 1,
                "h": meta.get("h") or 1,
                "location": list(o["Location"]),
                "rotation": list(o["Rotation"]),
                "gridIdx": int(o.get("gridIdx") or 0),
                "mapIdNum": int(o.get("mapId") or 0),
                "exParam": (o.get("exParamHandle") or {}).get("handle") or 0,
                "houseId": meta.get("houseId"),
            })

        houses = []
        for row in sf.sd["m_CraftStatus"]["CraftExParamP"].get("exParamHouse") or []:
            hid = _name(row.get("houseDataId"))
            if not hid:
                continue
            houses.append({
                "id": hid,
                "handle": _handle_val(row.get("Handle")),
                "map": row.get("placedMapId"),
                "entrance": row.get("entranceMapId"),
                "category": int(row.get("houseCategory") or 0),
                "planned": bool(row.get("isPlannedConstruct")),
                "rooms": len(row.get("indoorAreaStHdlArray") or []),
            })

        stock = self.inv_stock(sf)
        design_id = indoor_design_id(area) if kind == "indoor" else None
        theme = theme_for_design(design_id) if kind == "indoor" else None
        return {
            "mapId": map_id,
            "areaList": list_name,
            "area": {
                "mapId": area.get("mapId"),
                "category": int(area.get("Category") or 0),
                "width": int(area["Width"]),
                "depth": int(area["Depth"]),
                "height": int(area["Height"]),
                "voxel": [float(area.get("voxelWidth") or 50), float(area.get("voxelDepth") or 50),
                          float(area.get("voxelHeight") or 100)],
                "origin": list(origin),
                "numericMapId": num_map,
                "location": list(area.get("Location") or [0, 0, 0]),
                "designId": design_id,
            },
            "theme": theme,
            "placed": placed,
            "houses": houses,
            "inventory": {k: v["stock"] for k, v in stock.items()},
            "catalogSize": len(self.objects),
        }

    def catalog(self, q: str = "", category: str = "", limit: int = 200) -> list[dict]:
        q = (q or "").strip().lower()
        rows = []
        for o in self.objects.values():
            if category and o["category"] != category:
                continue
            if q and q not in o["name"].lower() and q not in o["id"].lower() and q not in (o.get("itemId") or ""):
                continue
            rows.append(o)
            if len(rows) >= limit:
                break
        return rows

    # ---- mutations ----------------------------------------------------------
    def place(self, sf: SaveFile, craft_obj_id: str, map_id: str, location: list[float],
              rotation: list[float] | None = None, free: bool = False, kind: str | None = None) -> dict:
        meta = self.objects.get(craft_obj_id)
        if not meta:
            raise SaveFileError(f"unknown craft object {craft_obj_id}")
        if kind is None:
            kind = "indoor" if map_id == MAP_MYHOUSE or str(map_id).startswith("NPC") else "map"
        list_name, area = self.find_area(sf, map_id, kind if kind != "auto" else None)
        num_map = self.numeric_map_id(sf, area)
        origin = self.area_origin(area, sf)
        ix, iy, iz, grid = self.loc_to_grid(location, area, origin)
        # clamp to area
        if not (0 <= ix < int(area["Width"]) and 0 <= iy < int(area["Depth"]) and 0 <= iz < int(area["Height"])):
            raise SaveFileError(f"location outside craft area ({ix},{iy},{iz})")
        loc = self.grid_to_loc(ix, iy, iz, area, origin)
        rot = list(rotation or [0.0, 0.0, 0.0])

        item_id = meta.get("itemId")
        if not free:
            if not item_id:
                raise SaveFileError(f"{craft_obj_id} has no inventory item; use Free mode")
            self._consume_item(sf, item_id)

        idx = self._find_empty_slot(sf)
        handle = self._alloc_handle(sf, idx)
        slot = {
            "Handle": {"handle": handle},
            "exParamHandle": {"handle": 0},
            "craftObjId": craft_obj_id,
            "viewPatternId": "Default",
            "Location": loc,
            "Rotation": rot,
            "gridIdx": grid,
            "mapId": num_map,
            "objStatusBitFlag": 0,
        }
        sf.sd["m_CraftStatus"]["craftObjStatusPArray"][idx] = slot
        area.setdefault("craftObjStHdlArray", []).append({"handle": handle})
        sf.dirty = True
        return {"handle": handle, "index": idx, "location": loc, "gridIdx": grid, "mapIdNum": num_map}

    def move(self, sf: SaveFile, handle: int, location: list[float] | None = None,
             rotation: list[float] | None = None, map_id: str | None = None,
             kind: str | None = None) -> dict:
        idx = self._index_by_handle(sf, handle)
        o = sf.sd["m_CraftStatus"]["craftObjStatusPArray"][idx]
        # find owning area
        owner = None
        for list_name, area in self._iter_areas(sf):
            if handle in _area_handles(area):
                owner = (list_name, area)
                break
        if owner is None:
            raise SaveFileError(f"handle {handle} not in any craft area")
        list_name, area = owner
        if map_id and area.get("mapId") != map_id:
            # moving across areas not supported in v1
            raise SaveFileError("moving between maps is not supported yet")
        origin = self.area_origin(area, sf)
        if location is not None:
            ix, iy, iz, grid = self.loc_to_grid(location, area, origin)
            if not (0 <= ix < int(area["Width"]) and 0 <= iy < int(area["Depth"]) and 0 <= iz < int(area["Height"])):
                raise SaveFileError(f"location outside craft area ({ix},{iy},{iz})")
            o["Location"] = self.grid_to_loc(ix, iy, iz, area, origin)
            o["gridIdx"] = grid
        if rotation is not None:
            o["Rotation"] = [float(rotation[0]), float(rotation[1]), float(rotation[2])]
        sf.dirty = True
        return {"handle": handle, "location": list(o["Location"]), "rotation": list(o["Rotation"]),
                "gridIdx": int(o["gridIdx"])}

    def remove(self, sf: SaveFile, handle: int, free: bool = False) -> dict:
        idx = self._index_by_handle(sf, handle)
        o = sf.sd["m_CraftStatus"]["craftObjStatusPArray"][idx]
        cid = o.get("craftObjId")
        meta = self.objects.get(cid) or {}
        # houses need exParam cleanup — refuse plain remove; use remove_house
        if (o.get("exParamHandle") or {}).get("handle"):
            raise SaveFileError("that object is a house shell; use house remove")
        item_id = meta.get("itemId")
        if not free and item_id:
            self._restore_item(sf, item_id)
        self._drop_handle(sf, handle)
        sf.sd["m_CraftStatus"]["craftObjStatusPArray"][idx] = {
            k: (list(v) if isinstance(v, list) else (dict(v) if isinstance(v, dict) else v))
            for k, v in EMPTY_CRAFT.items()
        }
        sf.dirty = True
        return {"removed": cid, "handle": handle, "returned": (not free and bool(item_id))}

    def rotate90(self, sf: SaveFile, handle: int) -> dict:
        idx = self._index_by_handle(sf, handle)
        o = sf.sd["m_CraftStatus"]["craftObjStatusPArray"][idx]
        yaw = float(o["Rotation"][1]) + 90.0
        if yaw >= 360.0:
            yaw -= 360.0
        o["Rotation"][1] = yaw
        sf.dirty = True
        return {"handle": handle, "rotation": list(o["Rotation"])}

    # ---- Base Camp terrain (land_obj / water_obj height field) ---------------
    # Loom CONFIRMED (BASECAMP_SYSTEM / save probe): even (ix,iy) only; iz steps
    # Location.Z by voxelHeight 150 (Hagram PileUp/Dig). Origin Z ≈ −150 → ground
    # top Y=0. Shave = objStatusBitFlag bit0 (bevel / Scraped_*); not a height channel.

    def terrain_grid(self, sf: SaveFile, map_id: str = MAP_BASE) -> dict:
        """Packed height field for the buildable craft sector."""
        list_name, area = self.find_area(sf, map_id, "map")
        origin = self.area_origin(area, sf)
        vw = float(area.get("voxelWidth") or 50)
        vd = float(area.get("voxelDepth") or 50)
        vh = float(area.get("voxelHeight") or 150)
        hdls = set(_area_handles(area))
        arr = sf.sd["m_CraftStatus"]["craftObjStatusPArray"]
        # (ix, iy) → list of (iz, surface, shave, handle)
        stacks: dict[tuple[int, int], list] = {}
        for o in arr:
            h = (o.get("Handle") or {}).get("handle")
            if h not in hdls:
                continue
            cid = o.get("craftObjId")
            if cid not in ("land_obj", "water_obj"):
                continue
            g = int(o.get("gridIdx") or -1)
            if g < 0:
                continue
            ix, iy, iz = self._unpack_grid(g, area)
            if ix < 0 or iy < 0 or ix % 2 or iy % 2:
                continue
            bit = int(o.get("objStatusBitFlag") or 0)
            stacks.setdefault((ix, iy), []).append({
                "iz": iz, "surface": "water" if cid == "water_obj" else "land",
                "shave": bool(bit & 1), "handle": h,
            })
        if not stacks:
            return {
                "origin": list(origin), "voxel": [vw, vd, vh], "step": 2,
                "width": 0, "depth": 0, "maxTier": int(area.get("Height") or 6),
                "cells": [],
            }
        ixs = sorted({k[0] for k in stacks})
        iys = sorted({k[1] for k in stacks})
        ix0, iy0 = ixs[0], iys[0]
        mw = (ixs[-1] - ix0) // 2 + 1
        md = (iys[-1] - iy0) // 2 + 1
        cells = []
        for my in range(md):
            for mx in range(mw):
                ix, iy = ix0 + mx * 2, iy0 + my * 2
                layers = stacks.get((ix, iy)) or []
                if not layers:
                    cells.append({"mx": mx, "my": my, "ix": ix, "iy": iy,
                                  "h": 0, "surface": "empty", "shave": False, "handle": 0})
                    continue
                top = max(layers, key=lambda L: L["iz"])
                cells.append({
                    "mx": mx, "my": my, "ix": ix, "iy": iy,
                    "h": int(top["iz"]), "surface": top["surface"],
                    "shave": top["shave"], "handle": top["handle"],
                })
        return {
            "mapId": map_id,
            "origin": [float(origin[0]), float(origin[1]), float(origin[2])],
            "voxel": [vw, vd, vh],
            "step": 2,
            "ix0": ix0, "iy0": iy0,
            "width": mw, "depth": md,
            "maxTier": int(area.get("Height") or 6),
            "tierUnit": vh / 100.0,  # meters per iz step (top of tier h at Y = h * tierUnit)
            "cellSize": (vw * 2) / 100.0,  # meters (even-cell footprint)
            "cells": cells,
        }

    def _terrain_layers_at(self, sf: SaveFile, area: dict, ix: int, iy: int) -> list[dict]:
        hdls = set(_area_handles(area))
        out = []
        for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]:
            h = (o.get("Handle") or {}).get("handle")
            if h not in hdls:
                continue
            cid = o.get("craftObjId")
            if cid not in ("land_obj", "water_obj"):
                continue
            g = int(o.get("gridIdx") or -1)
            if g < 0:
                continue
            gx, gy, gz = self._unpack_grid(g, area)
            if gx == ix and gy == iy:
                out.append({"obj": o, "iz": gz, "handle": h, "cid": cid})
        return out

    def _put_terrain_cell(self, sf: SaveFile, area: dict, origin: tuple, num_map: int,
                          ix: int, iy: int, iz: int, cid: str = "land_obj") -> int:
        """Insert land_obj/water_obj at (ix,iy,iz); returns handle. Free (no inventory)."""
        idx = self._find_empty_slot(sf)
        handle = self._alloc_handle(sf, idx)
        loc = self.grid_to_loc(ix, iy, iz, area, origin)
        grid = self._pack_grid(ix, iy, iz, area)
        sf.sd["m_CraftStatus"]["craftObjStatusPArray"][idx] = {
            "Handle": {"handle": handle},
            "exParamHandle": {"handle": 0},
            "craftObjId": cid,
            "viewPatternId": "Default",
            "Location": loc,
            "Rotation": [0.0, 0.0, 0.0],
            "gridIdx": grid,
            "mapId": num_map,
            "objStatusBitFlag": 0,
        }
        area.setdefault("craftObjStHdlArray", []).append({"handle": handle})
        return handle

    def terrain_raise(self, sf: SaveFile, ix: int, iy: int, map_id: str = MAP_BASE) -> dict:
        """Hagram PileUp: stack land_obj one iz (+150 Z). Loom STRONGLY SUPPORTED."""
        list_name, area = self.find_area(sf, map_id, "map")
        origin = self.area_origin(area, sf)
        num_map = self.numeric_map_id(sf, area)
        max_h = int(area.get("Height") or 6) - 1
        layers = self._terrain_layers_at(sf, area, ix, iy)
        top = max((L["iz"] for L in layers), default=-1)
        if top >= max_h:
            raise SaveFileError(f"already at max tier {max_h}")
        new_iz = top + 1
        # Don't duplicate an existing layer
        if any(L["iz"] == new_iz for L in layers):
            raise SaveFileError(f"tier {new_iz} already occupied at ({ix},{iy})")
        handle = self._put_terrain_cell(sf, area, origin, num_map, ix, iy, new_iz, "land_obj")
        sf.dirty = True
        return {"ix": ix, "iy": iy, "iz": new_iz, "handle": handle, "h": new_iz}

    def terrain_lower(self, sf: SaveFile, ix: int, iy: int, map_id: str = MAP_BASE) -> dict:
        """Hagram Excavate/Dig: peel top elevated land_obj (−1 iz). Loom CONFIRMED 2026-11-10.

        Live: Excavate gray on flat Ground; peels elevated only — does NOT become water_obj.
        Water cells come from Hagram Water category (STRONGLY SUPPORTED) — HOLD until live proof.
        """
        list_name, area = self.find_area(sf, map_id, "map")
        layers = self._terrain_layers_at(sf, area, ix, iy)
        if not layers:
            raise SaveFileError(f"no terrain at ({ix},{iy})")
        top = max(layers, key=lambda L: L["iz"])
        if top["iz"] > 0:
            self.remove(sf, top["handle"], free=True)
            return {"ix": ix, "iy": iy, "removedIz": top["iz"], "h": top["iz"] - 1}
        raise SaveFileError(
            "Excavate is peel-only on elevated land (flat Ground is gray in-game); "
            "water uses Hagram Water — not Dig-at-floor")

    def terrain_shave(self, sf: SaveFile, ix: int, iy: int, map_id: str = MAP_BASE,
                      on: bool | None = None) -> dict:
        """Toggle Shave bit0 on the top cell (bevel / Scraped_*). Loom CONFIRMED."""
        list_name, area = self.find_area(sf, map_id, "map")
        layers = self._terrain_layers_at(sf, area, ix, iy)
        if not layers:
            raise SaveFileError(f"no terrain at ({ix},{iy})")
        top = max(layers, key=lambda L: L["iz"])
        bit = int(top["obj"].get("objStatusBitFlag") or 0)
        want = (not bool(bit & 1)) if on is None else bool(on)
        top["obj"]["objStatusBitFlag"] = (bit | 1) if want else (bit & ~1)
        sf.dirty = True
        return {"ix": ix, "iy": iy, "iz": top["iz"], "shave": want, "h": top["iz"]}

    def terrain_level(self, sf: SaveFile, ix: int, iy: int, map_id: str = MAP_BASE) -> dict:
        """Nudge one cell toward the median of its 4-neighbors (Level / Smooth). UNVERIFIED."""
        list_name, area = self.find_area(sf, map_id, "map")
        layers = self._terrain_layers_at(sf, area, ix, iy)
        cur = max((L["iz"] for L in layers), default=0)
        nbrs = []
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nl = self._terrain_layers_at(sf, area, ix + dx, iy + dy)
            if nl:
                nbrs.append(max(L["iz"] for L in nl))
        if not nbrs:
            return {"ix": ix, "iy": iy, "h": cur, "changed": False}
        target = sorted(nbrs)[len(nbrs) // 2]
        if target == cur:
            return {"ix": ix, "iy": iy, "h": cur, "changed": False}
        if target > cur:
            r = self.terrain_raise(sf, ix, iy, map_id=map_id)
            return {**r, "leveled": True, "target": target}
        r = self.terrain_lower(sf, ix, iy, map_id=map_id)
        return {**r, "leveled": True, "target": target}

    # ---- houses -------------------------------------------------------------
    def _house_ex_by_handle(self, sf: SaveFile, ex_handle: int) -> dict | None:
        for row in sf.sd["m_CraftStatus"]["CraftExParamP"].get("exParamHouse") or []:
            if _handle_val(row.get("Handle")) == ex_handle:
                return row
        return None

    def _empty_house_slot(self, sf: SaveFile) -> int:
        arr = sf.sd["m_CraftStatus"]["CraftExParamP"]["exParamHouse"]
        for i, row in enumerate(arr):
            if not _name(row.get("houseDataId")):
                return i
        raise SaveFileError("no free house exParam slot (max 32)")

    def place_house(self, sf: SaveFile, house_id: str, location: list[float],
                    rotation: list[float] | None = None, free: bool = True,
                    map_id: str = MAP_BASE) -> dict:
        """Place a house shell by cloning indoor/wall areas from an existing same-structure house.

        Indoor bootstrap from templates is UNVERIFIED for brand-new structure ids with no donor
        on the save. Free mode is the default for houses (bag rarely holds building kits).
        """
        hmeta = self.houses.get(house_id)
        if not hmeta:
            raise SaveFileError(f"unknown house {house_id}")
        craft_id = hmeta.get("craftObj")
        if not craft_id or craft_id not in self.objects:
            raise SaveFileError(f"no craft object for house {house_id}")
        # find donor with same structureId
        donor = None
        for row in sf.sd["m_CraftStatus"]["CraftExParamP"].get("exParamHouse") or []:
            hid = _name(row.get("houseDataId"))
            if not hid:
                continue
            other = self.houses.get(hid) or {}
            if other.get("structure") == hmeta.get("structure") and row.get("indoorAreaStHdlArray"):
                donor = row
                break
        if donor is None and hmeta.get("forceMap") == MAP_MYHOUSE:
            # prefer player house as area donor even if structure differs
            for row in sf.sd["m_CraftStatus"]["CraftExParamP"].get("exParamHouse") or []:
                if _name(row.get("houseDataId")) and row.get("entranceMapId") == MAP_MYHOUSE:
                    donor = row
                    break
        if donor is None:
            raise SaveFileError(
                f"no donor house on this save to clone rooms for {house_id}; "
                "build one in game first (indoor bootstrap UNVERIFIED)")

        # place outdoor shell (Free for houses unless Legal + item exists)
        item_id = (self.objects.get(craft_id) or {}).get("itemId")
        use_free = free or not item_id
        placed = self.place(sf, craft_id, map_id, location, rotation, free=use_free, kind="map")

        # allocate exParam house slot
        ex_idx = self._empty_house_slot(sf)
        existing = [ _handle_val(r.get("Handle")) for r in sf.sd["m_CraftStatus"]["CraftExParamP"]["exParamHouse"]
                     if _handle_val(r.get("Handle")) ]
        # house ex handles: 0xFF010000 + n
        base = 0xFF010000
        n = 0
        while True:
            h = base + n
            h_signed = h - 0x100000000 if h >= 0x80000000 else h
            if h_signed not in existing and h not in existing:
                ex_handle = h_signed
                break
            n += 1
            if n > 64:
                raise SaveFileError("could not allocate house exParam handle")

        new_row = copy.deepcopy(donor)
        new_row["Handle"] = {"handle": ex_handle}
        new_row["houseDataId"] = {"Name": house_id, "crc": 0}
        new_row["houseCategory"] = int(hmeta.get("category") or 0)
        new_row["placedMapId"] = map_id
        new_row["entranceMapId"] = hmeta.get("forceMap") or donor.get("entranceMapId")
        new_row["isPlannedConstruct"] = 0
        # Reuse donor indoor area handles (same room instance). Full clone of area blobs is
        # UNVERIFIED; sharing rooms is wrong for a second house — only allow when donor has
        # empty indoor list OR forceMap is unique. For safety: if donor entrance is Map_MyHouse
        # and we're placing another MyHouse-forced house, refuse.
        if hmeta.get("forceMap") == MAP_MYHOUSE and _name(donor.get("houseDataId")):
            # clear indoor links — shell only until proper room clone is implemented
            new_row["indoorAreaStHdlArray"] = []
            note = "shell only (MyHouse room clone UNVERIFIED)"
        else:
            note = "cloned indoor handles from donor (UNVERIFIED)"
        sf.sd["m_CraftStatus"]["CraftExParamP"]["exParamHouse"][ex_idx] = new_row

        # link shell to exParam
        shell = sf.sd["m_CraftStatus"]["craftObjStatusPArray"][placed["index"]]
        shell["exParamHandle"] = {"handle": ex_handle}
        sf.dirty = True
        return {**placed, "houseId": house_id, "exParamHandle": ex_handle, "note": note}

    def move_house(self, sf: SaveFile, house_id: str, location: list[float],
                   rotation: list[float] | None = None) -> dict:
        ex = None
        for row in sf.sd["m_CraftStatus"]["CraftExParamP"].get("exParamHouse") or []:
            if _name(row.get("houseDataId")) == house_id:
                ex = row
                break
        if ex is None:
            raise SaveFileError(f"house {house_id} not placed")
        ex_h = _handle_val(ex.get("Handle"))
        # find shell craft obj
        for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]:
            if (o.get("exParamHandle") or {}).get("handle") == ex_h:
                return self.move(sf, (o.get("Handle") or {}).get("handle"), location, rotation)
        raise SaveFileError(f"no craft shell for house {house_id}")
