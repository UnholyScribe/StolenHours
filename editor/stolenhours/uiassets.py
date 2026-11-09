"""Builds the editor's look from the game's own art.

Step 1 (extract): tools/asset_extract (CUE4Parse) reads the encrypted IoStore containers read-only and writes PNGs
and font files to assets/game. Needs the .NET 10 SDK, research/private/pak_key.hex and the usmap mappings.
Step 2 (build): picks the pieces the editor uses and writes them under stable names to webgui/web/game.
Both outputs are git-ignored; the editor falls back to plain CSS when they are missing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import paths

EXTRACTOR = paths.PROJECT_ROOT / "tools" / "asset_extract"
EXTRACTOR_DLL = EXTRACTOR / "bin" / "Release" / "net10.0" / "asset_extract.dll"
UI = "Graphics/2D/UI/"
TEXTURE_PATTERN = UI + ("(Com|Window|Title|Life|Main|Save|Loading|CharaMake|Icon/(Item_small|Life|MoneyType|ScreenTitle"
                        "|Status|Character|Rarity|Category|Avt|CharaMake))/")
FONT_PATTERN = r"(L5_Latin_DP1_SF01-Bold|FOT-RodinNTLGPro-(M|DB))\.ufont$"
DATA_PATTERN = (r"GameData/(Avatar/|Chara/GDSCharamakeText|Item/GDSItem(Armor|Consume|Craft|Important|Kit|LifeTools"
                r"|Material|PowerUp|Recipe|Weapon|Vehicle|Treasure)Data|Item/GDSItemText_Noun|Life/GDSLifeData)")
ITEM_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData" / "Item"
ITEM_TABLES = ("Armor", "Consume", "Craft", "Important", "Kit", "LifeTools", "Material", "PowerUp", "Recipe",
               "Weapon", "Vehicle", "Treasure")
# item Category -> save inventory pocket; verified against every item in Unholy's save (see FINDINGS)
CATEGORY_POCKET = {10: "invWeapon", 20: "invLifeTools", 30: "invShield", 40: "invArmor", 60: "invConsume",
                   80: "invKit", 90: "invMaterial", 95: "invRecipe", 100: "invImportant", 110: "invMount",
                   130: "invPowerUp"}
# UNVERIFIED: no such item in the save yet. Check by adding one, then looking in that bag pocket in game.
GUESSED_POCKET = {50: "invArmor", 70: "invCraft"}
VARIANT_SUFFIX = re.compile(r"_(EX|BOX|BT)\d*$")
AVATAR_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData" / "Avatar"
CHARAMAKE_TEXT = paths.EXTRACT_DIR / "Game" / "Content" / "GameData" / "Chara" / "GDSCharamakeText.json"

# save field (m_AvatarStatus.playerP[0].BodyParam) -> (game table, menu label, kind)
AVATAR_FIELDS = [
    ("BodyModelId", "GDSAvatarBodyModelData", "Style", "parts"),
    ("BodyId", "GDSAvatarBodyData", "Build", "parts"),
    ("HeadModelId", "GDSAvatarHeadModelData", "Face Shape", "parts"),
    ("FaceColorId", "GDSAvatarFaceColorData", "Skin Tone", "color"),
    ("HairModelId", "GDSAvatarHairModelData", "Hairstyle", "parts"),
    ("HairColorId", "GDSAvatarHairColorData", "Hair Color", "color"),
    ("EyePartsId", "GDSAvatarEyePartsData", "Eyes", "parts"),
    ("EyeColorId", "GDSAvatarEyeColorData", "Eye Color", "color"),
    ("EyeBrowPartsId", "GDSAvatarEyeBrowPartsData", "Eyebrows", "parts"),
    ("NosePartsId", "GDSAvatarNosePartsData", "Nose", "parts"),
    ("MouthPartsId", "GDSAvatarMouthPartsData", "Mouth", "parts"),
    ("EarPartsId", "GDSAvatarEarPartsData", "Ears", "parts"),
    ("OptionPartsId", "GDSAvatarOptionPartsData", "Extras", "parts"),
    ("VoiceId", "GDSAvatarVoiceData", "Voice", "text"),
]
COLOR_KEYS = {"GDSAvatarFaceColorData": "SkinIconColor", "GDSAvatarHairColorData": "HairIconColor",
              "GDSAvatarEyeColorData": "EyeIconColor"}

# life id -> icon code in Icon/Life. Order matches the life names already tied to the save (see FINDINGS).
LIFE_ICON = {
    "life0000": "b00", "life0001": "b01", "life0002": "b02", "life0003": "b03", "life0004": "b04",
    "life0005": "c01", "life0006": "c02", "life0007": "c03", "life0008": "g01", "life0009": "w01",
    "life0010": "w02", "life0011": "w03", "life0012": "w04", "life0013": "w05", "life0014": "w06",
}

# output name -> source file stem (searched anywhere under the extract dir)
SINGLES = {
    "wallpaper.jpg": "_tex_title_launcher",
    "honeycomb.jpg": "tex_title_000000",
    "hand.png": "tex_com_cursorpointer_000000",
    "alert.png": "tex_window_000020",
    "check.png": "tex_com_check_000210",
    "arrow_l.png": "tex_com_arrow_000200",
    "arrow_r.png": "tex_com_arrow_000210",
    "arrow_l_on.png": "tex_com_arrow_000201",
    "arrow_r_on.png": "tex_com_arrow_000211",
    "card_combat.png": "tex_life_000200",
    "card_gather.png": "tex_life_000210",
    "card_craft.png": "tex_life_000220",
    "card_locked.png": "tex_life_000230",
    "ribbon.png": "tex_life_000400",
    "laurel.png": "tex_life_000500",
    "coin.png": "tex_icon_screentitle_020020",
    "nav_overview.png": "tex_icon_screentitle_000160",
    "nav_lives.png": "tex_icon_screentitle_000140",
    "nav_inventory.png": "tex_icon_screentitle_021020",
    "nav_appearance.png": "tex_icon_screentitle_000020",
    "nav_live.png": "tex_icon_screentitle_000050",
    "nav_file.png": "tex_icon_screentitle_000120",
    "nav_map.png": "tex_icon_screentitle_000090",
    "nav_backups.png": "tex_icon_screentitle_000210",
    "nav_livemap.png": "tex_icon_screentitle_000180",
    "nav_collection.png": "tex_icon_screentitle_000040",
    "nav_forge.png": "tex_icon_screentitle_000130",
    "nav_island.png": "tex_icon_screentitle_000100",
}
FONTS = {
    "fonts/heading.otf": "L5_Latin_DP1_SF01-Bold.ufont",
    "fonts/body.otf": "FOT-RodinNTLGPro-M.ufont",
    "fonts/body_bold.otf": "FOT-RodinNTLGPro-DB.ufont",
}
ITEM_ICON_PX = 112
PORTRAIT_PX = 512


def _run_extractor(mode: str, pattern: str, out_dir: Path | None = None) -> None:
    if not EXTRACTOR_DLL.exists():
        subprocess.run(["dotnet", "build", "-c", "Release", "-nologo", "-v", "q"], cwd=EXTRACTOR, check=True)
    from . import rewalk
    key = rewalk.pak_key_path().read_text().strip()
    paks = paths.game_dir() / "Game" / "Content" / "Paks"
    dest = out_dir or paths.EXTRACT_DIR
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dotnet", str(EXTRACTOR_DLL), str(paks), key, str(rewalk.mappings_path()), mode, pattern,
                    str(dest)], check=True)


def extract(force: bool = False) -> None:
    if force or not any(paths.EXTRACT_DIR.rglob("_tex_title_launcher.png")):
        _run_extractor("export", TEXTURE_PATTERN)
    if force or not any(paths.EXTRACT_DIR.rglob("*.ufont")):
        _run_extractor("raw", FONT_PATTERN)
    if force or not CHARAMAKE_TEXT.exists() or not any(paths.EXTRACT_DIR.rglob("tex_icon_avt*.png")):
        _run_extractor("json", DATA_PATTERN)
        _run_extractor("export", UI + "(CharaMake|Icon/(Avt|CharaMake))/")
    if force or not any(paths.EXTRACT_DIR.rglob("tex_icon_stamp_000010.png")):
        _run_extractor("export", UI + "Icon/Item/tex_icon_(emote|stamp)_")


def _srgb_hex(c: dict) -> str:
    def ch(v: float) -> int:
        v = max(0.0, min(1.0, v))
        v = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        return round(v * 255)
    return "#{:02x}{:02x}{:02x}".format(ch(c["X"]), ch(c["Y"]), ch(c["Z"]))


def _data_map(path: Path) -> list:
    import json
    props = json.loads(path.read_text(encoding="utf-8"))[0]["Properties"]
    return props.get("m_dataMap") or next(iter(props.values()))


def item_catalog(icon_dir: Path) -> list[dict]:
    """Every item the game's item tables define, with its English name, pocket and the icon the game shows.

    Ids missing from these tables (e.g. 'money', 'exp', '*_BOX', test entries in community lists) are not items.
    """
    import json

    names = {}
    for e in _data_map(ITEM_DATA / "GDSItemText_Noun.json"):
        info = (e["Value"].get("textInfo") or [{}])[0]
        names[e["Key"]] = info.get("nounSingularForm_en") or ""
    icons = {p.stem for p in icon_dir.glob("*.png")}
    out = []
    for table in ITEM_TABLES:
        f = ITEM_DATA / f"GDSItem{table}Data.json"
        if not f.exists():
            continue
        for e in _data_map(f):
            v = e["Value"]
            if not isinstance(v, dict) or "nameId" not in v:
                continue
            item_id = e["Key"]
            name = names.get(v.get("nameId") or "", "")
            if not name or item_id.lower().startswith("test"):
                continue
            if table == "Recipe":
                name = f"Recipe: {name}"
            icon = v.get("overwriteIconName") or "None"
            icon = item_id if icon == "None" else icon
            cat = v.get("Category")
            out.append({"id": item_id, "name": name, "table": table, "category": cat,
                        "pocket": CATEGORY_POCKET.get(cat) or GUESSED_POCKET.get(cat),
                        "pocket_guess": cat in GUESSED_POCKET, "icon": icon if icon in icons else None,
                        # no icon = NPC-only or test item; a _EX/_BOX/_BT suffix = internal copy of a base item
                        # (same name and icon, none present in the save)
                        "hidden": icon not in icons or bool(VARIANT_SUFFIX.search(item_id)), "stack": v.get("StackMax"), "sort": v.get("sortOrder", 0)})
    return out


def avatar_catalog(icon_index: dict[str, Path], icon_out: Path) -> dict:
    """Every appearance option the game defines, with English names, icons, swatches and unlock flags."""
    from PIL import Image

    text = {e["Key"]: (e["Value"]["textInfo"][0].get("text_en") or "") for e in _data_map(CHARAMAKE_TEXT)}
    icon_out.mkdir(parents=True, exist_ok=True)
    fields = []
    for field, table, label, kind in AVATAR_FIELDS:
        options = []
        for e in _data_map(AVATAR_DATA / f"{table}.json"):
            v = e["Value"]
            name = text.get(v.get("nameTextID") or "", "")
            opt = {"id": e["Key"], "name": name, "order": v.get("order", 999),
                   "hidden": not name, "unlock": any(c.get("Cmd") == "CondCmd_IsHaveItem" for c in v.get("cond") or [])}
            if table in COLOR_KEYS and v.get(COLOR_KEYS[table]):
                opt["color"] = _srgb_hex(v[COLOR_KEYS[table]])
            icon = (v.get("IconName") or "None").lower()
            if icon != "none":
                src = next((p for stem, p in icon_index.items() if stem.startswith("tex_" + icon)), None)
                if src:
                    dst = icon_out / f"{icon}.png"
                    if not dst.exists():
                        im = Image.open(src)
                        im.thumbnail((160, 160), Image.LANCZOS)
                        im.save(dst, optimize=True)
                    opt["icon"] = f"game/avatar/{icon}.png"
            options.append(opt)
        options.sort(key=lambda o: (o["hidden"], o["order"]))
        fields.append({"field": field, "label": label, "kind": kind, "options": options})
    return {"fields": fields}


def build(out: Path = paths.UI_ASSET_DIR, log=print) -> dict:
    from PIL import Image

    index = {p.name: p for p in paths.EXTRACT_DIR.rglob("*") if p.is_file()}
    out.mkdir(parents=True, exist_ok=True)
    missing = []

    def save(src_name: str, dst: Path, px: int | None = None) -> bool:
        src = index.get(src_name)
        if src is None:
            missing.append(src_name)
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix != ".png":
            shutil.copyfile(src, dst)
            return True
        im = Image.open(src)
        if px:
            im.thumbnail((px, px), Image.LANCZOS)
        if dst.suffix == ".jpg":
            im.convert("RGB").save(dst, quality=90)
        else:
            im.save(dst, optimize=True)
        return True

    for dst, stem in SINGLES.items():
        save(stem + ".png", out / dst)
    for dst, src in FONTS.items():
        save(src, out / dst)
    for life, code in LIFE_ICON.items():
        save(f"tex_icon_life_{code}_000011.png", out / "life" / f"{life}.png", 160)
        save(f"tex_icon_life_{code}_000501.png", out / "life" / f"{life}_portrait.png", PORTRAIT_PX)

    items = 0
    item_dir = out / "items"
    item_dir.mkdir(exist_ok=True)
    for name, src in index.items():
        if name.startswith("tex_icon_") and (src.parent.name == "Item_small" or (
                src.parent.name == "Item" and name.startswith(("tex_icon_emote_", "tex_icon_stamp_")))):
            dst = item_dir / (name[len("tex_icon_"):])
            if not dst.exists():
                im = Image.open(src)
                im.thumbnail((ITEM_ICON_PX, ITEM_ICON_PX), Image.LANCZOS)
                im.save(dst, optimize=True)
            items += 1
    catalog_items = 0
    if (ITEM_DATA / "GDSItemText_Noun.json").exists():
        import json
        cat = item_catalog(item_dir)
        (item_dir / "catalog.json").write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
        catalog_items = len(cat)
    else:
        missing.append("item data (GDSItemText_Noun)")

    avatar_options = 0
    if CHARAMAKE_TEXT.exists():
        import json
        stems = {p.stem.lower(): p for p in index.values() if p.suffix == ".png"}
        catalog = avatar_catalog(stems, out / "avatar")
        (out / "avatar" / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        avatar_options = sum(len(f["options"]) for f in catalog["fields"])
    else:
        missing.append("avatar data (GDSCharamakeText)")
    result = {"out": str(out), "item_icons": items, "items": catalog_items, "avatar_options": avatar_options,
              "missing": missing}
    log(f"UI assets in {out}: {len(SINGLES)} singles, {len(LIFE_ICON)} lives, {items} item icons, "
        f"{catalog_items} game items, "
        f"{avatar_options} appearance options, missing {missing or 'none'}")
    return result
