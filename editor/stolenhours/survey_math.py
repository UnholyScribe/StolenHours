"""
Base Camp survey math worker — named 10 m craft-pad grid + object truth tables.

Runs without Unreal. Writes under %LOCALAPPDATA%\\StolenHours\\survey\\Map_000100\\
(or next to the portable exe when frozen). UE Editor scripts
(tools/SurveyMathWorker/Content/Python) consume the same grid for orbit capture.
"""
from __future__ import annotations

import argparse
import json
import math
import string
import sys
from pathlib import Path

from . import paths, savefile, steam, village as V

MAP_ID = "Map_000100"
# Verified Base Camp craft area (FINDINGS.md).
ORIGIN_CM = (-3150.0, -3950.0, -150.0)
AREA_W_CELLS = 160
AREA_D_CELLS = 128
VOXEL_CM = 50.0
TILE_M = 10.0
TILE_CM = TILE_M * 100.0
YAWS = list(range(0, 360, 45))  # 000,045,...,315

# Door / seat forward on craft glTF local +X (FINDINGS).
DOOR_LOCAL = (1.0, 0.0, 0.0)


def survey_root() -> Path:
    """Portable survey folder — never Unholy's G:\\Stolen Hours."""
    if getattr(sys, "frozen", False):
        p = Path(sys.executable).resolve().parent / "survey" / MAP_ID
    else:
        p = paths.USER_DATA / "survey" / MAP_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


def pad_size_cm() -> tuple[float, float]:
    return AREA_W_CELLS * VOXEL_CM, AREA_D_CELLS * VOXEL_CM


def grid_dims() -> tuple[int, int]:
    w, d = pad_size_cm()
    cols = max(1, int(math.ceil(w / TILE_CM)))
    rows = max(1, int(math.ceil(d / TILE_CM)))
    return cols, rows


def cell_id(col: int, row: int) -> str:
    """A1 = SW corner (min UE_X, min UE_Y). Columns A.., rows 1.."""
    if col < 0 or col >= 26:
        # Extend past Z with AA-style if ever needed
        raise ValueError(f"col out of range: {col}")
    return f"{string.ascii_uppercase[col]}{row + 1}"


def parse_cell_id(cid: str) -> tuple[int, int]:
    cid = cid.strip().upper()
    i = 0
    while i < len(cid) and cid[i].isalpha():
        i += 1
    letters, digits = cid[:i], cid[i:]
    if not letters or not digits:
        raise ValueError(f"bad cell id: {cid}")
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    col -= 1
    return col, int(digits) - 1


def cell_aabb_cm(col: int, row: int) -> dict:
    ox, oy, oz = ORIGIN_CM
    x0 = ox + col * TILE_CM
    y0 = oy + row * TILE_CM
    x1 = min(x0 + TILE_CM, ox + AREA_W_CELLS * VOXEL_CM)
    y1 = min(y0 + TILE_CM, oy + AREA_D_CELLS * VOXEL_CM)
    return {
        "id": cell_id(col, row),
        "col": col,
        "row": row,
        "min_cm": [x0, y0, oz],
        "max_cm": [x1, y1, oz + 150.0 * 6],  # craft height stack hint
        "center_cm": [(x0 + x1) * 0.5, (y0 + y1) * 0.5, oz + 150.0],
        "size_m": [(x1 - x0) / 100.0, (y1 - y0) / 100.0],
    }


def build_grid() -> dict:
    cols, rows = grid_dims()
    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append(cell_aabb_cm(c, r))
    w, d = pad_size_cm()
    return {
        "mapId": MAP_ID,
        "origin_cm": list(ORIGIN_CM),
        "voxel_cm": VOXEL_CM,
        "area_cells": [AREA_W_CELLS, AREA_D_CELLS],
        "pad_size_cm": [w, d],
        "pad_size_m": [w / 100.0, d / 100.0],
        "tile_m": TILE_M,
        "cols": cols,
        "rows": rows,
        "label": "A1 = SW (min UE_X, min UE_Y); columns eastward, rows northward (+UE_Y)",
        "yaws_deg": YAWS,
        "cells": cells,
    }


def yaw_to_door_forward_ue(yaw_deg: float) -> list[float]:
    """UE yaw around Z: 0 faces +X. Door on local +X → world forward after yaw."""
    th = math.radians(yaw_deg)
    # UE left-handed: yaw+ rotates toward +Y
    fx = math.cos(th) * DOOR_LOCAL[0] - math.sin(th) * DOOR_LOCAL[1]
    fy = math.sin(th) * DOOR_LOCAL[0] + math.cos(th) * DOOR_LOCAL[1]
    return [fx, fy, 0.0]


def compass_ue(fwd: list[float]) -> str:
    fx, fy = fwd[0], fwd[1]
    if abs(fx) >= abs(fy):
        return "E (+X)" if fx > 0 else "W (-X)"
    return "N (+Y)" if fy > 0 else "S (-Y)"


def three_from_ue_xz(ue_x: float, ue_y: float) -> dict:
    """Outdoor schematic: Three X=−UE_Y/100, Z=UE_X/100 (FINDINGS 2026-10-17)."""
    return {"x": -ue_y / 100.0, "z": ue_x / 100.0}


def three_yaw_from_save(save_yaw: float) -> float:
    """Outdoor Three Y quat degrees: −90 − saveYaw (door on +X)."""
    return -90.0 - save_yaw


def cell_for_ue(ue_x: float, ue_y: float, grid: dict) -> str | None:
    ox, oy, _ = grid["origin_cm"]
    col = int((ue_x - ox) // TILE_CM)
    row = int((ue_y - oy) // TILE_CM)
    if col < 0 or row < 0 or col >= grid["cols"] or row >= grid["rows"]:
        return None
    return cell_id(col, row)


def build_objects(sf: savefile.SaveFile, grid: dict) -> dict:
    raw = json.loads((paths.UI_ASSET_DIR / "village" / "craft.json").read_text(encoding="utf-8"))
    v = V.Village(raw)
    st = v.state(sf, map_id=MAP_ID, kind="map")
    craft_man = {}
    cpath = paths.UI_ASSET_DIR / "craft3d" / "manifest.json"
    if cpath.exists():
        craft_man = json.loads(cpath.read_text(encoding="utf-8"))
        craft_man.pop("_materials", None)

    out = []
    for p in st["placed"]:
        cat = p.get("category") or ""
        if cat in ("LAND", "WATER", "WEED"):
            continue
        loc = p["location"]
        rot = p["rotation"]
        save_yaw = float(rot[1])
        fwd = yaw_to_door_forward_ue(save_yaw)
        cid = p.get("craftObjId") or ""
        mesh = (craft_man.get(cid) or {}).get("mesh")
        entry = {
            "handle": p.get("handle"),
            "craftObjId": cid,
            "name": p.get("name") or cid,
            "category": cat,
            "houseId": p.get("houseId"),
            "location_cm": list(loc),
            "rotation_deg": list(rot),
            "save_yaw_deg": save_yaw,
            "door_forward_ue": fwd,
            "door_compass_ue": compass_ue(fwd),
            "three_xz": three_from_ue_xz(loc[0], loc[1]),
            "three_yaw_deg": three_yaw_from_save(save_yaw),
            "cell": cell_for_ue(loc[0], loc[1], grid),
            "mesh": mesh,
            "w": p.get("w"),
            "d": p.get("d"),
            "h": p.get("h"),
        }
        out.append(entry)

    return {
        "mapId": MAP_ID,
        "door_local_axis": list(DOOR_LOCAL),
        "yaw_formula_outdoor": "three_yaw_deg = -90 - save_yaw_deg",
        "ue_to_three": "Three.X = -UE_Y/100; Three.Y = UE_Z/100; Three.Z = UE_X/100",
        "count": len(out),
        "objects": out,
    }


def write_axes_md(path: Path) -> None:
    path.write_text(
        """# Outdoor axes (frozen survey truth)

Game / SurveyMathWorker use **Unreal** centimetres, Z-up.

## Craft pad

- Origin (land_obj grid 0): `(-3150, -3950, -150)` cm
- Area: 160 × 128 cells × 50 cm → 80 m × 64 m
- Survey tiles: 10 m × 10 m, `A1` = SW (min UE_X, min UE_Y)

## UE → Stolen Hours Three.js (outdoor)

```
Three.X = -UE_Y / 100   # east = -UE_Y
Three.Y =  UE_Z / 100   # up
Three.Z =  UE_X / 100   # south = +UE_X
```

Guild / mountain (UE −X) sit at Three −Z (north).

## Yaw (door / seat on craft glTF local +X)

```
three_yaw_deg = -90 - save_yaw_deg
```

Examples:

| saveYaw | door (UE) | Three yaw | faces |
|--------:|-----------|----------:|-------|
| 0 | +X east | −90 | south (+Z) |
| 90 | +Y | −180 | west (−X) |
| 180 | −X | −270 / 90 | north (−Z) |
| 270 | −Y | −360 / 0 | east (+X) |

Do **not** use `90 + saveYaw` outdoors — that aimed benches/houses at the lake.

## Sources

- `grid.json`, `objects.json` beside this file
- Orbit PNGs under `{CellId}/yawNNN.png` after UE capture
""",
        encoding="utf-8",
    )


def write_cell_metas(grid: dict, root: Path, cam_height_cm: float = 1500.0) -> int:
    """Write per-cell meta.json with planned camera poses (PNGs come from UE capture)."""
    n = 0
    pitch = -55.0  # look down toward pad
    for cell in grid["cells"]:
        cid = cell["id"]
        folder = root / cid
        folder.mkdir(parents=True, exist_ok=True)
        cx, cy, cz = cell["center_cm"]
        frames = []
        for yaw in YAWS:
            frames.append({
                "yaw_deg": yaw,
                "file": f"yaw{yaw:03d}.png",
                "camera_cm": [cx, cy, cz + cam_height_cm],
                "camera_rot_deg": [pitch, yaw, 0.0],  # pitch, yaw, roll (UE)
                "look_at_cm": [cx, cy, cz],
            })
        meta = {
            "cell": cell,
            "mapId": MAP_ID,
            "frames": frames,
            "capture": "pending",  # UE smw_capture_orbit.py sets "ok"
        }
        (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        n += 1
    return n


def build_import_manifest(objects: dict, root: Path) -> Path:
    """UE smw_import_level.py reads this to spawn glTFs at native UE poses."""
    craft_base = paths.UI_ASSET_DIR / "craft3d"
    map_base = paths.UI_ASSET_DIR / "map3d"
    map_man = json.loads((map_base / "manifest.json").read_text(encoding="utf-8"))
    placements = []
    for pl in map_man.get("placements") or []:
        mesh = pl.get("mesh")
        if not mesh:
            continue
        placements.append({
            "kind": "map3d",
            "id": pl.get("id"),
            "glb": str((map_base / mesh).resolve()),
            "location_cm": list(pl.get("location") or [0, 0, 0]),
            "rotation_deg": list(pl.get("rotation") or [0, 0, 0]),
            "note": "world-baked island chunk; may sit at origin",
        })
    for o in objects.get("objects") or []:
        mesh = o.get("mesh")
        if not mesh:
            continue
        glb = craft_base / mesh
        if not glb.exists():
            continue
        placements.append({
            "kind": "craft",
            "id": o.get("craftObjId"),
            "name": o.get("name"),
            "handle": o.get("handle"),
            "glb": str(glb.resolve()),
            "location_cm": o["location_cm"],
            "rotation_deg": o["rotation_deg"],
            "cell": o.get("cell"),
        })
    path = root / "import_manifest.json"
    path.write_text(
        json.dumps({
            "mapId": MAP_ID,
            "origin_cm": list(ORIGIN_CM),
            "grid_tile_m": TILE_M,
            "placements": placements,
        }, indent=2),
        encoding="utf-8",
    )
    return path


def export_all(save_path: Path | None = None) -> dict:
    root = survey_root()
    sp = save_path or steam.find_saves()[0].path
    sf = savefile.SaveFile.load(sp)
    grid = build_grid()
    objects = build_objects(sf, grid)
    (root / "grid.json").write_text(json.dumps(grid, indent=2), encoding="utf-8")
    (root / "objects.json").write_text(json.dumps(objects, indent=2), encoding="utf-8")
    write_axes_md(root / "axes.md")
    n_meta = write_cell_metas(grid, root)
    imp = build_import_manifest(objects, root)
    # Copy into UE project Content for the editor scripts
    ue_content = paths.PROJECT_ROOT / "tools" / "SurveyMathWorker" / "Content" / "Python"
    if ue_content.is_dir():
        for name in ("grid.json", "objects.json", "import_manifest.json"):
            src = root / name
            if src.exists():
                (ue_content / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "root": str(root),
        "save": str(sp),
        "cells": len(grid["cells"]),
        "objects": objects["count"],
        "metas": n_meta,
        "import_manifest": str(imp),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stolen Hours Base Camp survey math worker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_exp = sub.add_parser("export", help="Write grid.json, objects.json, axes.md, cell metas")
    p_exp.add_argument("--save", type=Path, default=None)
    sub.add_parser("root", help="Print survey output directory")
    args = ap.parse_args(argv)
    if args.cmd == "root":
        print(survey_root())
        return 0
    if args.cmd == "export":
        info = export_all(args.save)
        print(json.dumps(info, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
