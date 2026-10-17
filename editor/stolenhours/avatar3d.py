"""3D character preview data for the Look tab, built from the game's own avatar models.

extract(): CUE4Parse exports every avatar mesh (glTF, with material JSON and textures) and the face-part textures.
build(): copies the meshes, converts the textures the preview shader uses to WebP and writes manifest.json, which maps
each appearance option (save field value) to its meshes / textures, each material to a shading type, each body size
to its bone offsets and each colour option to the game's full colour set.

Coordinates: the glTF export is Y-up metres; the game's bone tables are UE Z-up centimetres, so
three(x, y, z) = UE(X, Z, Y) / 100 for positions and UE(X, Z, Y) for scales.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from . import paths, uiassets

AVATAR_3D = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "3D" / "Avatar"
WEAPON_3D = AVATAR_3D.parent / "Weapon"
SHIELD_3D = AVATAR_3D.parent / "Shield"
MESH_PATTERN = r"^Game/Content/Graphics/3D/Avatar/(.*/Mdl/|Avt1001_hair/)mdl_avt"  # the shared TypeD hair has no Mdl dir
HAIR_D = AVATAR_3D / "Avt1001_hair" / "mdl_avt_hair_typeD.glb"
# Held items are skinned to root > R_hand_item_tag (weapons, tools) or L_hand_item_tag (shields) > wpn/sld, so they
# attach by bone name like the body parts. ModelId2 (a second, unskinned tool piece) is left out: its socket is unknown.
HELD_PATTERN = r"^Game/Content/Graphics/3D/(Weapon|Shield)/.*/Mdl/mdl_(wpn|sld)\w*\.uasset$"
HELD_TABLES = ("Weapon", "LifeTools", "Armor")
# Armour: item (GDSItemArmorData.modelID) -> GDSItemEquipModelData -> Wear meshes. The Wear tables give the slot;
# slot names are the game's equipment slots (ViewEquipModelInfo / m_abilityEquipInvInfo).
WEAR_3D = AVATAR_3D.parent / "Wear"
WEAR_PATTERN = r"^Game/Content/Graphics/3D/(Wear|Accessory)/.*/Mdl/mdl_(wea|acs)\w*\.uasset$"
WEAR_DATA_PATTERN = r"GameData/(Wear/GDSWear|Item/GDSItemEquipModel)\w*Data\.uasset$"
WEAR_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData" / "Wear"
WEAR_SLOTS = {"Hat": "Head", "Body": "tops", "Bottom": "bottoms", "Hand": "arm", "Feet": "foot", "Cape": "mantle"}
# Hats and capes are skinned to root > hat / cape and hang from these body sockets, like weapons from the hand tags.
# Glasses (Wear Accessory, mdl_acs) are unskinned static meshes on a socket not found yet, so they are left out.
SOCKETS = {"Head": "hat_item_tag", "mantle": "cape_item_tag"}
LIFE_DEFAULTS = {"defaultHeadId": "Head", "defaultTopsId": "tops", "defaultBottomsId": "bottoms", "defaultArmId": "arm",
                 "defaultFootId": "foot", "defaultMantleId": "mantle"}
FACE_TEX_PATTERN = r"^Game/Content/Graphics/3D/Avatar/Avt100[2357]_\w+/(\w+/)?tex_avt"
TEX_PX = 512
# Preview poses. "menu" is the Characters-screen idle. The life poses are what the Equipment screen plays: the
# state machines of _AnimBP/avt000000/Avatar_Equipment_AnimBP map each tool type to one sequence (resolved through
# their player nodes; the Life_Pen state is labelled w04 but its player plays w06), and each life's tool type comes
# from its starter tool in GDSLifeData (Tree Branch = Stick, Borrowed Sword = Sword, Claymore = Blade, ...).
ANIMS = {
    "menu": "cmn_charaMakeIdle", "wardrobe": "cmn_changeCostumeLoop", "field": "cmn_idle",
    "life0000": "b00_idleEquip", "life0001": "b02_idleEquip", "life0002": "b01_idleEquip",
    "life0003": "b03_idleEquip", "life0004": "b04_idleEquip", "life0005": "c02_idleEquip",
    "life0006": "c01_idleEquip", "life0007": "c03_idleEquip", "life0008": "c04_idleEquip",
    "life0009": "w03_idleEquip", "life0010": "w02_idleEquip", "life0011": "w01_idleEquip",
    "life0012": "w04_idleEquip", "life0013": "w05_idleEquip", "life0014": "w06_idleEquip",
}
ANIM_PATTERN = r"Avatar/avt000000/Anm/anm_avt000000_(" + "|".join(ANIMS.values()) + r")\.uasset$"


def extract(force: bool = False) -> None:
    if force or not any(AVATAR_3D.rglob("*.glb")) or not HAIR_D.exists():
        uiassets._run_extractor("mesh", MESH_PATTERN)
    if force or not (AVATAR_3D / "Avt1002_brow" / "tex_avt100201_00_rse.png").exists():  # not used by any material
        uiassets._run_extractor("export", FACE_TEX_PATTERN)
    if force or not any(WEAPON_3D.rglob("*.glb")) or not any(SHIELD_3D.rglob("*.glb")):
        uiassets._run_extractor("mesh", HELD_PATTERN)
    if force or not any(WEAR_3D.rglob("*.glb")):
        uiassets._run_extractor("mesh", WEAR_PATTERN)
    if force or not (WEAR_DATA / "GDSWearHatModelData.json").exists():
        uiassets._run_extractor("json", WEAR_DATA_PATTERN)
    if force or not all((AVATAR_3D / "avt000000" / "Anm" / f"anm_avt000000_{n}.anim.json").exists()
                        for n in ANIMS.values()):
        uiassets._run_extractor("anim", ANIM_PATTERN)


def _asset_file(asset_path: str, ext: str) -> Path:
    """'/Game/Graphics/3D/X/mdl_a.mdl_a' -> <extract>/Game/Content/Graphics/3D/X/mdl_a<ext>"""
    rel = asset_path.split(".")[0].replace("/Game/", "Game/Content/", 1)
    return paths.EXTRACT_DIR / (rel + ext)


def _glb_materials(path: Path) -> list[str]:
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    return [m.get("name", "") for m in json.loads(b[20:20 + n]).get("materials", [])]


def _lin(c: dict | None) -> list[float] | None:
    return [round(c["X"], 5), round(c["Y"], 5), round(c["Z"], 5)] if c else None


class _Builder:
    def __init__(self, out: Path):
        from PIL import Image
        self.Image = Image
        self.out = out
        (out / "m").mkdir(parents=True, exist_ok=True)
        (out / "t").mkdir(parents=True, exist_ok=True)
        self.mats_json = {p.stem.lower(): p for d in (AVATAR_3D, WEAPON_3D, SHIELD_3D, WEAR_3D) for p in d.rglob("mat_*.json")}
        self.materials: dict[str, dict] = {}
        self.missing: list[str] = []

    def tex(self, object_path: str | None, lossy: bool = False) -> str | None:
        if not object_path:
            return None
        src = _asset_file(object_path, ".png")
        if not src.exists():
            self.missing.append(src.name)
            return None
        name = f"t/{src.stem.lower()}.webp"
        dst = self.out / name
        if not dst.exists():
            im = self.Image.open(src).convert("RGBA")
            im.thumbnail((TEX_PX, TEX_PX), self.Image.LANCZOS)
            im.save(dst, "WEBP", quality=88, lossless=not lossy, method=4)
        return name

    def material(self, name: str) -> None:
        key = name.lower()
        if key in self.materials:
            return
        src = self.mats_json.get(key)
        if src is None:
            self.materials[key] = {"type": "plain"}
            return
        js = json.loads(src.read_text(encoding="utf-8"))
        t = {k: (v or {}).get("ObjectPath") for k, v in (js.get("Textures") or {}).items()}
        c = js.get("Colors") or {}
        if "L_Eye_Txture" in t:
            m = {"type": "face", "tex": self.tex(t.get("Skin_Texture"))}
        elif "Hair_Color" in c or "HairTangentTex" in t:
            m = {"type": "hair", "tex": self.tex(t.get("Shadow_Texture"))}
        elif "Skin_Texture" in t:
            m = {"type": "skin", "tex": self.tex(t.get("Skin_Texture"))}
        else:
            m = {"type": "diff", "tex": self.tex(t.get("Diff_Texture") or t.get("PM_Diffuse"), lossy=True)}
        self.materials[key] = m

    def mesh(self, asset_path: str | None) -> str | None:
        if not asset_path or asset_path == "None":
            return None
        return self.mesh_file(_asset_file(asset_path, ".glb"))

    def mesh_file(self, src: Path | None) -> str | None:
        if src is None or not src.exists():
            self.missing.append(src.name if src else "?")
            return None
        name = f"m/{src.stem.lower()}.glb"
        dst = self.out / name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
        for mat in _glb_materials(src):
            self.material(mat)
        return name


def _anim(src: Path, dst: Path) -> str:
    """UE-space per-frame local bone transforms -> glTF space, keeping only bones that move.

    Verified on the reference pose against the exported glbs: position (X, Z, Y) / 100, rotation (-x, -z, -y, w).
    The preview plays them as offsets from the skeleton's reference pose, because a few helper bones (*_add*) have
    a different rest pose in each mesh.
    """
    a = json.loads(src.read_text(encoding="utf-8"))
    pos = lambda v: [round(v[0] / 100, 5), round(v[2] / 100, 5), round(v[1] / 100, 5)]
    rot = lambda q: [round(-q[0], 5), round(-q[2], 5), round(-q[1], 5), round(q[3], 5)]
    scl = lambda v: [round(v[0], 4), round(v[2], 4), round(v[1], 4)]
    bones = {}
    for bone in a["bones"]:
        track = {"refP": pos(bone["refPos"]), "refR": rot(bone["refRot"])}
        for k, f in (("pos", pos), ("rot", rot), ("scl", scl)):
            frames = [f(v) for v in bone[k]]
            if any(fr != frames[0] for fr in frames) or (k == "pos" and frames[0] != track["refP"]) \
                    or (k == "rot" and frames[0] != track["refR"]) or (k == "scl" and frames[0] != [1, 1, 1]):
                track[k[0]] = frames
        if len(track) > 2:
            bones[bone["name"]] = track
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps({"fps": a["fps"], "frames": a["frames"], "bones": bones}, separators=(",", ":")),
                   encoding="utf-8")
    return f"a/{dst.name}"


def _path(v: dict, key: str) -> str | None:
    p = (v.get(key) or {}).get("AssetPathName")
    return p if p and p != "None" else None


def _key(k) -> str:
    return k["Name"] if isinstance(k, dict) else k


def _wear(b: _Builder, wanted: set[str]) -> dict:
    """Wear model id -> {slot, m: meshes, dress?, hair?: {hair id or "None": hair type}}.

    Gloves list four meshes (TypeName 0-3) in the order of the bare hands (right, left, right open, left open);
    the preview uses the closed pair like the bare body. UNVERIFIED: that a dress top hides the bottoms."""
    item = uiassets.ITEM_DATA
    eqm = {_key(e["Key"]).lower(): e["Value"] for e in uiassets._data_map(item / "GDSItemEquipModelData.json")}
    hair = {_key(e["Key"]).lower(): {h["Key"]: h["Value"]["HairModelType"] for h in e["Value"]["HairModelInfoList"]}
            for e in uiassets._data_map(item / "GDSItemEquipModelHairTypeData.json")}
    out = {}
    for table, slot in WEAR_SLOTS.items():
        for e in uiassets._data_map(WEAR_DATA / f"GDSWear{table}ModelData.json"):
            model = _key(e["Key"]).lower()
            if model not in wanted or model not in eqm:
                continue
            lst = sorted(eqm[model]["EquipModelList"], key=lambda m: m["Value"]["TypeName"])
            meshes = [m for m in (b.mesh(_path(x["Value"], "modelPath")) for x in lst[:2 if slot == "arm" else 1]) if m]
            if not meshes:
                continue
            w = {"slot": slot, "m": meshes}
            if e["Value"].get("IsDress"):
                w["dress"] = True
            if model in hair:
                w["hair"] = hair[model]
            out[model] = w
    return out


def build(out: Path | None = None, log=print) -> dict:
    out = out or paths.UI_ASSET_DIR / "avatar3d"
    if not any(AVATAR_3D.rglob("*.glb")):
        log("3D preview: no exported avatar meshes; run extract first")
        return {"missing": ["avatar meshes"]}
    b = _Builder(out)
    data = lambda table: uiassets._data_map(uiassets.AVATAR_DATA / f"GDSAvatar{table}Data.json")
    parts: dict[str, dict] = {}

    # the bare body, by the equipment slot that replaces each piece
    body = {}
    for e in data("BodyModel"):
        mesh = lambda *keys: [m for m in (b.mesh(_path(e["Value"], k)) for k in keys) if m]
        body[e["Key"]] = {"tops": mesh("BodyModelPath"), "bottoms": mesh("BottomModelPath"),
                          "arm": mesh("HandRModelPath", "HandLModelPath"), "foot": mesh("FeetModelPath")}
    parts["HeadModelId"] = {e["Key"]: [b.mesh(_path(e["Value"], "HeadModelPath"))] for e in data("HeadModel")}
    # hair has a variant per hat fit: TypeA bare, TypeB/C under hats, TypeD a shared short cut (picked per hat)
    hair, hair_types = {}, {}
    for e in data("HairModel"):
        types = {t["Key"]: _path(t["Value"], "HairModelPath") for t in e["Value"].get("HairModelList") or []}
        hair[e["Key"]] = [b.mesh(types.get("TypeA") or next(iter(types.values()), None))]
        hair_types[e["Key"]] = {t: m for t, p in types.items() if (m := b.mesh(p))}
    parts["HairModelId"] = hair
    parts["EarPartsId"] = {e["Key"]: [b.mesh(_path(e["Value"], "EarMeshPath"))] for e in data("EarParts")}
    parts["NosePartsId"] = {e["Key"]: [b.mesh(_path(e["Value"], "MeshPath"))] for e in data("NoseParts")}
    parts["OptionPartsId"] = {e["Key"]: {
        "meshes": [m for m in (b.mesh(_path(i["Value"], "MeshPath")) for i in e["Value"].get("meshInfoList") or []) if m],
        "tex": b.tex(_path(e["Value"], "TexturePath")), "hideNose": bool(e["Value"].get("IsHideNose"))}
        for e in data("OptionParts")}
    parts["EyePartsId"] = {e["Key"]: b.tex(_path(e["Value"], "TexturePath")) for e in data("EyeParts")}
    parts["EyeBrowPartsId"] = {e["Key"]: b.tex(_path(e["Value"], "TexturePath")) for e in data("EyeBrowParts")}
    parts["MouthPartsId"] = {e["Key"]: b.tex(_path(e["Value"], "TexturePath"), lossy=False) for e in data("MouthParts")}
    for field in parts:
        if isinstance(next(iter(parts[field].values()), None), list):
            parts[field] = {k: [m for m in v if m] for k, v in parts[field].items()}
    parts["BodyModelId"] = body

    sizes = {}
    for e in data("BodySize"):
        bones = {}
        for bone in e["Value"].get("BoneList") or []:
            p, s = bone["Position"], bone["Scale"]
            pos = [p["X"] / 100, p["Z"] / 100, p["Y"] / 100]
            scl = [s["X"], s["Z"], s["Y"]]
            if any(abs(v) > 1e-6 for v in pos) or any(abs(v - 1) > 1e-6 for v in scl):
                bones[bone["Name"]] = {"p": pos, "s": scl}
        sizes[e["Key"]] = bones

    colors = {}
    for e in data("FaceColor"):
        v = e["Value"]
        colors[e["Key"]] = {"skin": _lin(v.get("SkinColor")), "shadow": _lin(v.get("SkinShadowColor")),
                            "cheek": _lin(v.get("SkinCheekColor")), "rim": _lin(v.get("SkinRimColor"))}
    for e in data("HairColor"):
        v = e["Value"]
        colors[e["Key"]] = {"hair": _lin(v.get("HairColor")), "shadow": _lin(v.get("HairShadowColor")),
                            "hi": _lin(v.get("HairHirightColor"))}
    for e in data("EyeColor"):
        v = e["Value"]
        colors[e["Key"]] = {"eye": _lin(v.get("EyeColor")), "hi": _lin(v.get("EyeHighLight"))}

    held_glb = {p.stem.lower(): p for d in (WEAPON_3D, SHIELD_3D) for p in d.rglob("mdl_*.glb")}
    items = {}
    for table in HELD_TABLES:
        for e in uiassets._data_map(uiassets.ITEM_DATA / f"GDSItem{table}Data.json"):
            model = str(e["Value"].get("modelID") or "").lower()
            if model.startswith(("mdl_wpn", "mdl_sld")) and model in held_glb:
                items[e["Key"]] = b.mesh_file(held_glb[model])
    life_data = uiassets.ITEM_DATA.parent / "Life" / "GDSLifeData.json"
    rental = {e["Key"]: [i for i in (e["Value"].get("rentalWeaponId"), e["Value"].get("rentalShieldId")) if i in items]
              for e in uiassets._data_map(life_data)} if life_data.exists() else {}

    armor = {e["Key"]: str(e["Value"].get("modelID") or "").lower()
             for e in uiassets._data_map(uiassets.ITEM_DATA / "GDSItemArmorData.json")}
    wear = _wear(b, set(armor.values()))
    armor = {k: m for k, m in armor.items() if m in wear}
    defaults = {}
    if life_data.exists():
        for e in uiassets._data_map(life_data):
            defaults[e["Key"]] = {slot: armor[e["Value"][k]] for k, slot in LIFE_DEFAULTS.items()
                                  if e["Value"].get(k) in armor}

    anims = {}
    for key, name in ANIMS.items():
        src = AVATAR_3D / "avt000000" / "Anm" / f"anm_avt000000_{name}.anim.json"
        if src.exists():
            anims[key] = _anim(src, out / "a" / f"{name}.json")
        else:
            b.missing.append(src.name)

    manifest = {"parts": parts, "hairTypes": hair_types, "materials": b.materials, "sizes": sizes, "colors": colors,
                "anims": anims, "items": items, "rental": rental, "wear": wear, "armor": armor, "defaults": defaults,
                "sockets": SOCKETS}
    (out / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    missing = sorted(set(b.missing))
    log(f"3D preview in {out}: {len(list((out / 'm').glob('*.glb')))} meshes, {len(list((out / 't').glob('*.webp')))} "
        f"textures, {len(b.materials)} materials, {size / 1e6:.1f} MB, missing {missing[:8] or 'none'}"
        + (f" (+{len(missing) - 8})" if len(missing) > 8 else ""))
    return {"out": str(out), "missing": missing}
