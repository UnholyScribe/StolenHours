"""Base Camp island environment (Map_000100) for Village outdoor.

extract(): CUE4Parse World→USD for the persistent + mod/obj/env sublevels, and StaticMesh→glTF
for mdl_map000100_* (skip collision/shadow).
build(): copy glbs + Diff webps into webgui/web/game/map3d/ with a placements manifest
(identity — mesh vertices are already world-baked in meters, Y-up).
"""

from __future__ import annotations

import json
import re
import shutil
import struct
from pathlib import Path

from . import paths, uiassets

OUT = paths.UI_ASSET_DIR / "map3d"
MAP_MESH_ROOT = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "3D" / "Map" / "Map000100"
WORLD_USD_ROOT = paths.EXTRACT_DIR / "Game" / "Content" / "Level" / "Map" / "Map_000100"
TEX_PX = 1024

# Persistent level pulls streaming; mod/obj hold most StaticMeshActors / BP props.
WORLD_PATTERN = (
    r"Level/Map/Map_000100/Map_000100(_mod|_obj|_env|_01_env)?\.umap$"
)
MESH_PATTERN = (
    r"Graphics/3D/Map/Map000100/.*/Mdl/mdl_map000100_(?!.*_(col|sdw)\b).*\.uasset$"
)
ENV_MESH_PATTERN = r"Graphics/3D/Environment/Env000100/Mdl/mdl_env000100_.*\.uasset$"

# Large / distinctive island pieces — always include when present.
PRIORITY = (
    "mdl_map000100_00", "mdl_map000100_01", "mdl_map000100_02", "mdl_map000100_03",
    "mdl_map000100_04", "mdl_map000100_05", "mdl_map000100_06", "mdl_map000100_sea",
    "mdl_map000100_river", "mdl_map000100_taki", "mdl_map000100_wave00",
    "mdl_map000100_ff", "mdl_map000100_51", "mdl_map000100_50", "mdl_map000100_53",
    "mdl_env000100_01", "mdl_env000100_10",
)


def extract(force: bool = False) -> None:
    have = list(MAP_MESH_ROOT.rglob("mdl_map000100_00.glb")) if MAP_MESH_ROOT.exists() else []
    if force or not have:
        uiassets._run_extractor("mesh", MESH_PATTERN)
        try:
            uiassets._run_extractor("mesh", ENV_MESH_PATTERN)
        except Exception:
            pass
    usd = WORLD_USD_ROOT / "Map_000100.usda"
    if force or not usd.exists():
        uiassets._run_extractor("world", WORLD_PATTERN)


def _glb_materials(path: Path) -> list[str]:
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    return [m.get("name", "") for m in json.loads(b[20:20 + n]).get("materials", [])]


def _asset_png(object_path: str | None) -> Path | None:
    if not object_path:
        return None
    rel = object_path.split(".")[0].replace("/Game/", "Game/Content/", 1)
    p = paths.EXTRACT_DIR / (rel + ".png")
    return p if p.exists() else None


def _albedo_path(textures: dict) -> str | None:
    """Map materials use World_Diff_Texture / UV1 Diff keys more than craft Diff_Texture."""
    prefer = (
        "Diff_Texture", "Base_Texture", "World_Diff_Texture", "PM_Diffuse",
        "00_Diff_Texture(UV1)", "01_Diff_Texture(UV1)",
    )
    for k in prefer:
        p = (textures.get(k) or {}).get("ObjectPath") if isinstance(textures.get(k), dict) else textures.get(k)
        if not p:
            continue
        if k == "PM_Diffuse" and "_rse" in p.lower():
            continue
        if "_rse" in p.lower() or "_mask" in p.lower() or "_nml" in p.lower():
            continue
        return p
    for k, v in textures.items():
        p = (v or {}).get("ObjectPath") if isinstance(v, dict) else v
        if not p or not isinstance(p, str):
            continue
        kl = k.lower()
        if "diff" in kl and "_rse" not in p.lower() and "_nml" not in p.lower() and "_mask" not in p.lower():
            return p
    return None


class _TexPack:
    def __init__(self, out: Path):
        from PIL import Image
        self.Image = Image
        self.out = out
        (out / "t").mkdir(parents=True, exist_ok=True)
        self.mats_json: dict[str, Path] = {}
        for p in paths.EXTRACT_DIR.rglob("mat_*.json"):
            if "Map000100" in p.as_posix() or "Env000100" in p.as_posix() or "Map000000" in p.as_posix():
                self.mats_json[p.stem.lower()] = p
        self.materials: dict[str, dict] = {}

    def tex(self, object_path: str | None) -> str | None:
        src = _asset_png(object_path)
        if src is None:
            return None
        name = f"t/{src.stem.lower()}.webp"
        dst = self.out / name
        if not dst.exists():
            im = self.Image.open(src).convert("RGBA")
            im.thumbnail((TEX_PX, TEX_PX), self.Image.LANCZOS)
            im.save(dst, "WEBP", quality=88, lossless=False, method=4)
        return name

    def material(self, name: str) -> None:
        key = name.lower()
        if not key or key in self.materials:
            return
        src = self.mats_json.get(key)
        if src is None:
            self.materials[key] = {}
            return
        js = json.loads(src.read_text(encoding="utf-8"))
        textures = js.get("Textures") or {}
        entry: dict = {}
        dif = _albedo_path(textures)
        if dif:
            entry["tex"] = self.tex(dif)
        for nk in ("World_Normal_Texuture", "NormalTex", "Normal_Texture", "PM_Normals"):
            nml = textures.get(nk)
            path = (nml or {}).get("ObjectPath") if isinstance(nml, dict) else nml
            if path:
                entry["nml"] = self.tex(path)
                break
        self.materials[key] = {k: v for k, v in entry.items() if v}


def _iter_island_glbs() -> list[Path]:
    roots = [
        MAP_MESH_ROOT,
        paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "3D" / "Environment" / "Env000100",
        # Prior probe export (kept if EXTRACT_DIR mesh step was skipped)
        paths.EXTRACT_DIR / "world" / "Map_000100_meshes" / "Game" / "Content" / "Graphics" / "3D" / "Map" / "Map000100",
        paths.PROJECT_ROOT / "assets" / "game" / "world" / "Map_000100_meshes" / "Game" / "Content" / "Graphics" / "3D" / "Map" / "Map000100",
        paths.PROJECT_ROOT / "assets" / "game" / "world" / "Map_000100_meshes" / "Game" / "Content" / "Graphics" / "3D" / "Environment" / "Env000100",
    ]
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.glb"):
            stem = p.stem.lower()
            if stem.endswith("_sdw") or stem.endswith("_col"):
                continue
            # Ship / wavearea scraps clip badly in the schematic — skip until placed via level JSON.
            if "_ship" in stem or "wavearea" in stem:
                continue
            if not (stem.startswith("mdl_map000100_") or stem.startswith("mdl_env000100_")):
                continue
            found.setdefault(stem, p)
    # Prefer priority order, then the rest.
    ordered: list[Path] = []
    for name in PRIORITY:
        if name in found:
            ordered.append(found.pop(name))
    ordered.extend(sorted(found.values(), key=lambda p: p.stem.lower()))
    return ordered


def build(out: Path | None = None, log=print) -> dict:
    out = out or OUT
    glbs = _iter_island_glbs()
    if not glbs:
        log("map3d: no Map000100 glbs; run map3d.extract first")
        return {"meshes": 0}

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "m").mkdir(parents=True, exist_ok=True)
    pack = _TexPack(out)

    placements: list[dict] = []
    for src in glbs:
        stem = src.stem.lower()
        rel = f"m/{stem}.glb"
        shutil.copy2(src, out / rel)
        for mat in _glb_materials(src):
            pack.material(mat)
        placements.append({
            "id": stem,
            "mesh": rel,
            # Vertices are world-baked (meters, Y-up). Identity in Three outdoor.
            "location": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
        })

    manifest = {
        "mapId": "Map_000100",
        "placements": placements,
        "materials": pack.materials,
        "notes": "World-baked island chunks from mdl_map000100_*; World USD under assets/game/.../Map_000100/*.usda",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"map3d: {len(placements)} meshes, {sum(1 for v in pack.materials.values() if v.get('tex'))} textured mats")
    return {"meshes": len(placements), "materials": len(pack.materials)}
