"""Craft / furniture mesh preview data for the Village house editor.

Resolves GDSCraftObjVisualData.bpPath → StaticMesh under Graphics/3D/Craft,
exports glTF via asset_extract (same path as avatar3d), and writes game/craft3d/manifest.json.

CUE4Parse mesh export writes glTF with material *names* but empty PBR — textures land as sibling
Mat/*.json + Tex/*.png (same as Look). build() packs those into craft3d/t/ and a materials map;
village3d.js binds Diff_Texture onto the loaded meshes.

Full BP→mesh resolution needs ObjBP + Map/* child BP dumps; when a mesh is missing the UI draws a Size box.
"""
from __future__ import annotations

import json
import re
import shutil
import struct
from pathlib import Path

from . import paths, uiassets

GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"
CRAFT_3D = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "3D" / "Craft"
OBJBP = paths.EXTRACT_DIR / "Game" / "Content" / "Program" / "Craft" / "ObjBP"
MAP_PROG = paths.EXTRACT_DIR / "Game" / "Content" / "Program" / "Map"
OUT = paths.UI_ASSET_DIR / "craft3d"
TEX_PX = 512
# House shells (cft00030x via MapJumpFp Building), guild (cft000b*), My House furniture.
# Note: cft000302_* IS the thatched house body (door/bird/propeller nodes), not bare land.
MESH_PATTERN = (
    r"^Game/Content/Graphics/3D/Craft/cft("
    r"000300|000301|000302|000303|000304|000305|000306|000307|000308|000309|00030a|00030b|"
    r"000b00|000b01|000b50|000b51|000ba0|"
    r"000d0d|110001|130001|170001|200001|"
    r"010001|010002|010004|010009|040001|040008"
    r")/\d+/Mdl/mdl_cft\w*\.uasset$"
)
# ObjBPs for placed house furniture + Map child actors that hold the real StaticMesh soft paths.
BP_PATTERN = (
    r"^Game/Content/Program/(Craft/ObjBP/(house/|_Test/|guild/)?BP_(ico|icf)\w+|"
    r"Map/(Bed|Bench|Building|Prop|Furniture|MapJumpFp/Building)/BP_\w+)\.uasset$"
)
DATA_PATTERN = r"^Game/Content/GameData/Craft/GDSCraftObj(Data|VisualData)\.uasset$"
# At least these stems must exist after extract (My House decorate + Thatched House + Guild).
NEED_GLBS = (
    "mdl_cft130001_00", "mdl_cft000d0d_00",
    "mdl_cft000302_03", "mdl_cft000b01_00", "mdl_cft000b00_00",
)
# Building mesh folders to force-pull even when ObjBP only names the MapJumpFp child.
HOUSE_MESH_FOLDERS = (
    "cft000300", "cft000301", "cft000302", "cft000303", "cft000304", "cft000305",
    "cft000306", "cft000307", "cft000308", "cft000309", "cft00030a", "cft00030b",
    "cft000b00", "cft000b01", "cft000b50", "cft000b51", "cft000ba0",
)


def _dump_json_chunks(pattern_fn, stems: list[str], chunk: int = 80) -> None:
    for i in range(0, len(stems), chunk):
        part = stems[i:i + chunk]
        alt = "|".join(re.escape(s) for s in part)
        uiassets._run_extractor("json", pattern_fn(alt))


def _extract_mesh_folders(folders: list[str], chunk: int = 40) -> None:
    for i in range(0, len(folders), chunk):
        part = folders[i:i + chunk]
        alt = "|".join(re.escape(f) for f in part)
        uiassets._run_extractor(
            "mesh",
            rf"^Game/Content/Graphics/3D/Craft/({alt})/\d+/Mdl/mdl_cft\w*\.uasset$",
        )


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "Craft" / "GDSCraftObjVisualData.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)
    objbp_n = len(list(OBJBP.rglob("BP_*.json"))) if OBJBP.exists() else 0
    if force or objbp_n < 100:
        try:
            uiassets._run_extractor("json", BP_PATTERN)
        except Exception:
            pass
    # Map child actors (Bed/Bench/…) hold the real StaticMesh soft paths for most furniture.
    missing_map: list[str] = []
    if OBJBP.exists():
        for p in OBJBP.rglob("BP_*.json"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for child in re.findall(r"/Game/Program/Map/([\w/]+/BP_cft[\w]+)", text):
                rel = child.split(".")[0]
                if not (MAP_PROG / f"{rel}.json").exists():
                    missing_map.append(Path(rel).name)
    if missing_map:
        try:
            _dump_json_chunks(
                lambda alt: rf"^Game/Content/Program/Map/.*/({alt})\.uasset$",
                sorted(set(missing_map)),
            )
        except Exception:
            pass
    def _softs() -> set[str]:
        out: set[str] = set()
        for root in (OBJBP, MAP_PROG):
            if not root.exists():
                continue
            for p in root.rglob("BP_*.json"):
                out.update(_mesh_soft_paths(p))
        return out

    def _need_folders(have: set[str]) -> list[str]:
        folders: set[str] = set()
        for soft in _softs():
            stem = Path(soft.split(".")[0]).name.lower()
            if stem.endswith("_sdw") or stem in have:
                continue
            parts = soft.replace("/Game/Graphics/3D/Craft/", "").split("/")
            if parts and parts[0].startswith("cft"):
                folders.add(parts[0])
        return sorted(folders)

    glbs = {p.stem.lower() for p in CRAFT_3D.rglob("*.glb")} if CRAFT_3D.exists() else set()
    # Sparse seed covers My House fixtures when the tree is empty; then pull every missing folder.
    if force or not glbs or any(n not in glbs for n in NEED_GLBS):
        uiassets._run_extractor("mesh", MESH_PATTERN)
        glbs = {p.stem.lower() for p in CRAFT_3D.rglob("*.glb")} if CRAFT_3D.exists() else set()
    need = sorted(set(_need_folders(glbs)) | {
        f for f in HOUSE_MESH_FOLDERS
        if not any(p.stem.lower().startswith(f"mdl_{f}") for p in (CRAFT_3D.rglob("*.glb") if CRAFT_3D.exists() else []))
    })
    if need:
        _extract_mesh_folders(need)


def _rows(rel: str) -> dict:
    props = json.loads((GAME_DATA / rel).read_text(encoding="utf-8"))[0]["Properties"]
    return {(r["Key"]["Name"] if isinstance(r["Key"], dict) else r["Key"]): r["Value"]
            for r in props["m_dataMap"]}


def _mesh_soft_paths(bp_json: Path) -> list[str]:
    """Pull /Game/Graphics/3D/Craft/.../mdl_* soft paths from a dumped ObjBP / Map BP."""
    text = bp_json.read_text(encoding="utf-8", errors="ignore")
    return sorted(set(re.findall(r"/Game/Graphics/3D/Craft/[^\"]+mdl_cft[^\"]+", text)))


def _glb_for_soft(soft: str) -> Path | None:
    # /Game/Graphics/3D/Craft/cftX/00/Mdl/mdl_cftX_00.mdl_cftX_00 → extract glb
    rel = soft.split(".")[0].replace("/Game/", "Game/Content/", 1)
    p = paths.EXTRACT_DIR / (rel + ".glb")
    if p.exists() and not p.stem.lower().endswith("_sdw"):
        return p
    return None


def _index_bp_meshes() -> dict[str, list[str]]:
    """BP stem (lowercase, no _C) -> list of mesh soft paths found in dumped JSON."""
    out: dict[str, list[str]] = {}
    roots = [OBJBP]
    if MAP_PROG.exists():
        roots.append(MAP_PROG)
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("BP_*.json"):
            stem = p.stem.lower()
            if stem.endswith("_c"):
                stem = stem[:-2]
            softs = _mesh_soft_paths(p)
            if softs:
                out.setdefault(stem, [])
                for s in softs:
                    if s not in out[stem]:
                        out[stem].append(s)
            text = p.read_text(encoding="utf-8", errors="ignore")
            for child in re.findall(r"/Game/Program/Map/[^\"']+", text):
                child_stem = Path(child.split(".")[0]).name.lower()
                if child_stem.endswith("_c"):
                    child_stem = child_stem[:-2]
                out.setdefault(stem, [])
                for s in out.get(child_stem) or []:
                    if s not in out[stem]:
                        out[stem].append(s)
    return out


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


class _TexPack:
    """Copy craft Diff_Textures into craft3d/t/ as WebP; build material name → tex path."""

    def __init__(self, out: Path):
        from PIL import Image
        self.Image = Image
        self.out = out
        (out / "t").mkdir(parents=True, exist_ok=True)
        self.mats_json = {p.stem.lower(): p for p in CRAFT_3D.rglob("mat_*.json")} if CRAFT_3D.exists() else {}
        self.materials: dict[str, dict] = {}
        self.missing: list[str] = []

    def tex(self, object_path: str | None) -> str | None:
        src = _asset_png(object_path)
        if src is None:
            if object_path:
                self.missing.append(Path(object_path.split(".")[0]).name)
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
        t = {k: (v or {}).get("ObjectPath") for k, v in (js.get("Textures") or {}).items()}
        # Prefer real albedo. Some craft mats put RSE into PM_Diffuse and the color in
        # Base_Texture / Diff_Texture (thatch grass does this — binding RSE → white roofs).
        def _albedo_path() -> str | None:
            for k in ("Diff_Texture", "Base_Texture", "PM_Diffuse"):
                p = t.get(k)
                if not p:
                    continue
                if k == "PM_Diffuse" and "_rse" in p.lower() and (
                        t.get("Diff_Texture") or t.get("Base_Texture")):
                    continue
                return p
            return t.get("PM_Diffuse")
        dif = _albedo_path()
        nml = t.get("NormalTex") or t.get("Normal_Texture") or t.get("PM_Normals")
        entry: dict = {}
        if dif:
            entry["tex"] = self.tex(dif)
        if nml:
            entry["nml"] = self.tex(nml)
        self.materials[key] = {k: v for k, v in entry.items() if v}


def build(out: Path | None = None, log=print) -> dict:
    out = out or OUT
    if not (GAME_DATA / "Craft" / "GDSCraftObjVisualData.json").exists():
        log("craft3d: no Craft visual data; run extract first")
        return {"missing": ["craft visuals"]}
    objs = _rows("Craft/GDSCraftObjData.json")
    visuals = _rows("Craft/GDSCraftObjVisualData.json")
    glbs = {p.stem.lower(): p for p in CRAFT_3D.rglob("*.glb") if not p.stem.lower().endswith("_sdw")} if CRAFT_3D.exists() else {}
    bp_meshes = _index_bp_meshes()
    pack = _TexPack(out)

    out.mkdir(parents=True, exist_ok=True)
    (out / "m").mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    copied = 0
    boxed = 0

    # Prefer body meshes over door/apron scraps when a BP lists several soft paths.
    def _pick_mesh(softs: list[str]) -> Path | None:
        ranked: list[tuple[int, Path]] = []
        for soft in softs or []:
            g = _glb_for_soft(soft)
            if not g:
                mdl = Path(soft.split(".")[0]).name.lower()
                g = glbs.get(mdl)
            if not g:
                continue
            name = g.stem.lower()
            score = 0
            if name.endswith("_door"):
                score -= 5
            if "_sdw" in name:
                score -= 10
            # Prefer larger body shells
            score += min(8, g.stat().st_size // 200_000)
            ranked.append((score, g))
        if not ranked:
            return None
        ranked.sort(key=lambda t: t[0], reverse=True)
        return ranked[0][1]

    def _resolve_bp_json(bp: str) -> Path | None:
        name = Path(bp.split(".")[0]).name + ".json"
        for cand in (OBJBP / name, OBJBP / "house" / name, OBJBP / "guild" / name,
                     OBJBP / "_Test" / name):
            if cand.exists():
                return cand
        # Subfolder search
        hits = list(OBJBP.rglob(name)) if OBJBP.exists() else []
        return hits[0] if hits else None

    for oid, row in objs.items():
        # Furniture (ico), buildings/houses (icf), guild/test shells (cft_…)
        if not (oid.startswith(("obj_ico", "obj_icf", "obj_cft"))):
            continue
        vid = row.get("craftObjVisualId")
        vis = visuals.get(vid) or {}
        size = vis.get("Size") or {}
        cat = (row.get("Category") or row.get("category") or "")
        if isinstance(cat, dict):
            cat = cat.get("Name") or cat.get("Value") or ""
        entry = {
            "id": oid,
            "w": int(size.get("Width") or 1),
            "d": int(size.get("Depth") or 1),
            "h": int(size.get("Height") or 1),
            "mesh": None,
            "visual": vid,
            "shape": vis.get("shapeDataId") or None,
            "footprint": {
                "width": int(size.get("Width") or 1),
                "depth": int(size.get("Depth") or 1),
            },
        }
        bp = (vis.get("bpPath") or {}).get("AssetPathName") or ""
        stem = Path(bp.split(".")[0]).name.lower() if bp else ""
        if stem.endswith("_c"):
            stem = stem[:-2]
        mesh_path = _pick_mesh(bp_meshes.get(stem) or [])
        # Resolve mesh from child BP path names embedded in ObjBP dumps (Bench/Bed/Building/…)
        if mesh_path is None and bp:
            bp_json = _resolve_bp_json(bp)
            if bp_json is not None:
                text = bp_json.read_text(encoding="utf-8", errors="ignore")
                # Prefer MapJumpFp Building child → cft00030x house body, then any mdl soft path.
                softs = list(re.findall(r"/Game/Graphics/3D/Craft/[^\"]+mdl_cft[^\"]+", text))
                for m in re.findall(r"BP_MJFp_Building_(cft[0-9a-f]+_\w+)", text, re.I):
                    softs.append(f"/Game/Graphics/3D/Craft/{m.split('_')[0]}/{m.split('_')[1]}/Mdl/mdl_{m}.0")
                for m in re.findall(r"cft[0-9a-f]+_\d+", text, re.I):
                    softs.append(f"/Game/Graphics/3D/Craft/{m.rsplit('_', 1)[0]}/{m.rsplit('_', 1)[1]}/Mdl/mdl_{m}.0")
                mesh_path = _pick_mesh(softs)
                if mesh_path is None:
                    for m in re.findall(r"cft[0-9a-f]+_\d+", text, re.I):
                        key = f"mdl_{m}".lower()
                        if key in glbs:
                            mesh_path = glbs[key]
                            break
                        for stem_g, gpath in glbs.items():
                            if m.lower() in stem_g and not stem_g.endswith("_door"):
                                mesh_path = gpath
                                break
                        if mesh_path:
                            break
        if mesh_path and mesh_path.exists():
            dest = f"m/{mesh_path.stem}.glb"
            target = out / dest
            if not target.exists() or target.stat().st_size != mesh_path.stat().st_size:
                shutil.copy2(mesh_path, target)
            entry["mesh"] = dest
            for mat in _glb_materials(mesh_path):
                pack.material(mat)
            copied += 1
        else:
            boxed += 1
        manifest[oid] = entry

    manifest["_materials"] = pack.materials
    _write_room_shell_textures(out, log)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                                       encoding="utf-8")
    log(f"craft3d: {copied} meshes, {boxed} footprint-only, {len(pack.materials)} materials -> {out}"
        + (f" (missing tex {pack.missing[:6]})" if pack.missing else ""))
    return {"meshes": copied, "boxed": boxed, "objects": len(manifest) - 1,
            "materials": len(pack.materials), "missing_tex": pack.missing}


def _write_room_shell_textures(out: Path, log=print) -> None:
    """My House shell: Tropical Wall atlas → tiled wallpaper + threshold wood (decorate mode)."""
    from PIL import Image
    wall_src = CRAFT_3D / "cft010001" / "00" / "Tex" / "tex_cft010001_00_dif.png"
    if not wall_src.exists():
        log(f"craft3d: room wall tex missing ({wall_src.name}); shell stays procedural")
        return
    im = Image.open(wall_src).convert("RGBA")
    w, h = im.size
    # Top half of Tropical Wall = full wall height (chevron → yellow panels → wainscot).
    im.crop((0, 0, w, h // 2)).save(out / "myhouse_wall.png")
    # Warm plank swatch from the atlas lower band for the south threshold decal.
    im.crop((0, h // 2, max(64, w // 4), h // 2 + max(64, h // 4))).save(out / "myhouse_threshold.png")
    log("craft3d: wrote myhouse_wall.png + myhouse_threshold.png from Tropical Wall")
