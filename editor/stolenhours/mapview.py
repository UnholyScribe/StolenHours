"""Live map viewer data: the overworld map art, the game's event map icons, and where every event sits.

All of it comes from the game files:
- World -> map: `Map_200000_GDSMapMinimap` bounds (+-120000). Fitted on the art: u = (maxY - Y) / range,
  v = (X - minX) / range. 99% of the 97 event places land on land pixels with zero offset, the next best layout
  needs a fudge offset and scores 97% (`research/map_fit.py`). UNVERIFIED in game: check the player marker
  against the in-game map once the mod reports the player position.
- Event -> place: `GDSActiveEventConfig.EventPointId` -> `GDSActiveEventPlaceData.purposePointId` ->
  `GDSQuestPurposePoint` (`tgtPosition`, `mapIconType` 113 normal / 114 legendary = the glow under the icon).
- Icons: `GDSMapIconData` (mapIconType -> mapIconId, drawPriority, per-zoom scale) -> `GDSMenuIconTexture`.
- Icon animation: `MenuLayer_Map_Icon` puts `ExtMat_ActiveEvent` = `mat_map_000012` on active-event icons
  (class defaults + `ExchangeExtMat_ActiveEvent` bytecode), a `basemat_ui_ripple_01` instance. Its parameters are
  exported below; the shader math itself is compiled, so the viewer's ripple is a reconstruction (UNVERIFIED:
  compare side by side with the in-game map).
UNVERIFIED: which mapIconType an event shows. Only 12 events carry `OverrideMapIconType`; the rest is chosen in
native code. The rule below (battle 124, gathering by kind 125-128, delivery 129, legendary 130-134, special 219)
follows the icon art and titles. Check: compare each kind against the in-game map.
"""
from __future__ import annotations

import functools
import json
import shutil
from pathlib import Path

from . import paths, uiassets
from .mapevents import GAME_DATA, _Table

OUT = paths.UI_ASSET_DIR / "mapview"
MAP_ID = "Map_200000"
TEX = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D"
MAP_ART = TEX / "UI" / "Map" / MAP_ID / "Tex" / f"minimap_{MAP_ID}_000000.png"
# World-menu maps (GDSWorldMapData) plus Loom dream layer Map_200100 (not on world menu).
WORLD_MAP_IDS = ("Map_200000", "Map_100100", "Map_100101", "Map_100300", "Map_100400", "Map_100500", "Map_000101",
                 "Map_000100", "Map_200100")
DREAM_MAP_ID = "Map_200100"
CRAFT_MAP_ID = "Map_000100"
MAT_DIR = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D" / "UI" / "Map" / "Com" / "Mat"
BASE_MAT_DIR = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D" / "Base_Material" / "UI"
MAP_PX = 8192  # the art's own size: the largest zoom step draws it ~6800px wide on a full-screen editor
PLAYER_ICON = 1
EVENT_ICONS = (124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 219)
GLOW_ICONS = (113, 114)
# Chrome / dream pins Loom catalogued for Live Map fidelity (game textures).
CHROME_ICONS = (6, 10, 11, 27, 28, 29, 122, 123, 139, 191, 220, 221, 245, 250)
# gathering kind -> (normal, legendary) icon types; word lists match Loom AE picker corpus (83/83)
GATHER = {"ore": (125, 131), "tree": (126, 132), "fish": (127, 133), "crop": (128, 134)}
GATHER_WORDS = {"ore": ("Ore", "Mining"), "tree": ("Tree", "Wood"), "fish": ("Fish", "Catch"),
                "crop": ("Veggie", "Harvest", "Dessert", "crop")}
DATA_PATTERN = (r"^Game/Content/(GameData/(Menu/GDS(MapIconData|MenuIconTexture|DungeonEntranceIconSetting)|"
                r"Craft/GDSCraftMiniMapSetting|Quest/GDSQuestPurposePoint|"
                r"Map/Map_\d{6}/Map_\d{6}_GDSMap(Minimap|FuncPoint|JumpFuncPointPlacement|"
                r"PlantLeafePlacement|PickPoint|EnemyPlacementConfig)|Map/GDS(FastTravel|TamagemonoShrineData|"
                r"QuestRequesterSetting|WorldMapData|MapText_Noun)|Chara/GDS(CharaParameterEnemy|CharaText_Noun))|"
                r"Graphics/2D/(UI/Map/Com/Mat/mat_map_\w+|Base_Material/UI/basemat_ui_\w+))\.uasset$")
TEX_PATTERN = (r"Graphics/2D/UI/(Map/Map_\d{6}/Tex/(minimap_Map_\d{6}_000000|tex_map\d{6}_000000)|"
               r"Icon/Map/tex_icon_map_mui)")


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "Menu" / "GDSDungeonEntranceIconSetting.json").exists() \
            or not (BASE_MAT_DIR / "basemat_ui_ripple_01.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)
    if force or not MAP_ART.exists() or not _art_path("Map_100100").exists():
        uiassets._run_extractor("export", TEX_PATTERN)


def _art_path(map_id: str) -> Path:
    """Prefer the game's own filename: Ginormosia/dream use minimap_*; towns use tex_map*."""
    d = TEX / "UI" / "Map" / map_id / "Tex"
    for name in (f"minimap_{map_id}_000000.png", f"tex_map{map_id.removeprefix('Map_')}_000000.png"):
        p = d / name
        if p.exists():
            return p
    return d / f"tex_map{map_id.removeprefix('Map_')}_000000.png"


def _minimap_row(map_id: str) -> dict | None:
    """The map menu's minimap row: the one named after the map (not debug / parts / room variants)."""
    try:
        rows = _Table(f"Map/{map_id}/{map_id}_GDSMapMinimap.json").rows
    except (FileNotFoundError, KeyError, IndexError):
        return None
    for key in (f"minimap_{map_id}", f"{map_id}_minimap"):
        if key in rows:
            return rows[key]
    return next(iter(rows.values()), None)


def icon_type(title: str, etype: int, override: int, legendary: bool) -> int:
    """Active Event mapIconType — Loom STRONGLY SUPPORTED (MAP_SYSTEM / map_gaps_dump)."""
    if override:
        return override
    kind = next((k for k, words in GATHER_WORDS.items() if any(w in title for w in words)), None)
    if etype == 2:
        return GATHER.get(kind or "ore", GATHER["ore"])[1 if legendary else 0]
    if etype == 1:
        return 130 if legendary else 124
    if etype == 3:
        return 129
    if etype == 4:
        return 219
    # type 0 story-ish rows normally carry Override=124; fall back to battle pin
    return 130 if legendary else 124


def _craft_hud() -> dict | None:
    """Base Camp craft-pad minimap crop from GDSCraftMiniMapSetting (Loom CONFIRMED)."""
    try:
        rows = _Table("Craft/GDSCraftMiniMapSetting.json").rows
    except (FileNotFoundError, KeyError, IndexError):
        return None
    row = rows.get("cft_mm_param_map_000100") or rows.get("cft_mm_param_00_01")
    if not row:
        return None
    return {
        "baseTextureWidth": row["baseTextureWidth"], "baseTextureHeight": row["baseTextureHeight"],
        "targetWidth": row["targetWidth"], "targetHeight": row["targetHeight"],
        "targetOffsetX": row["targetOffsetX"], "targetOffsetY": row["targetOffsetY"],
    }


def _uv(pos: dict, mm: dict) -> tuple[float, float]:
    u = (mm["maxY"] - pos["Y"]) / (mm["maxY"] - mm["minY"])
    v = (pos["X"] - mm["minX"]) / (mm["maxX"] - mm["minX"])
    return round(u, 6), round(v, 6)


@functools.cache
def _bounds() -> dict:
    try:
        meta = json.loads((OUT / "mapview.json").read_text(encoding="utf-8"))
        return next(m["bounds"] for m in meta["maps"] if m["id"] == MAP_ID)
    except (FileNotFoundError, KeyError, ValueError, StopIteration):
        return {"minX": -120000, "maxX": 120000, "minY": -120000, "maxY": 120000}


def world_to_map(x: float, y: float) -> dict:
    """World position -> map UV with the built bounds (the minimap table's, +-120000 when not built yet)."""
    u, v = _uv({"X": x, "Y": y}, _bounds())
    return {"u": u, "v": v}


def _material(path: Path) -> dict:
    """Scalar/vector parameters of a material instance over its parent's defaults."""
    inst = json.loads(path.read_text(encoding="utf-8"))[0]["Properties"]
    parent = inst["Parent"]["ObjectPath"].rsplit("/", 1)[1].split(".")[0]
    base = json.loads((BASE_MAT_DIR / f"{parent}.json").read_text(encoding="utf-8"))[0]["CachedExpressionData"]
    names = [p["Name"] for p in base["RuntimeEntries"]["ParameterInfoSet"]]
    params = dict(zip(names, base["ScalarValues"]))
    vnames = [p["Name"] for p in base["RuntimeEntries[1]"]["ParameterInfoSet"]]
    vecs = {n: [c["R"], c["G"], c["B"], c["A"]] for n, c in zip(vnames, base["VectorValues"])}
    for p in inst.get("ScalarParameterValues", []):
        params[p["ParameterInfo"]["Name"]] = p["ParameterValue"]
    for p in inst.get("VectorParameterValues", []):
        c = p["ParameterValue"]
        vecs[p["ParameterInfo"]["Name"]] = [c["R"], c["G"], c["B"], c["A"]]
    return {"material": path.stem, "parent": parent, "scalars": params, "vectors": vecs}


def build(out: Path = OUT, log=print) -> dict:
    if not MAP_ART.exists() or not (GAME_DATA / "Menu" / "GDSMapIconData.json").exists():
        log("map viewer: game data not extracted; run extract first")
        return {"missing": ["map viewer data"]}
    from PIL import Image

    mm = _Table(f"Map/{MAP_ID}/{MAP_ID}_GDSMapMinimap.json").rows[f"minimap_{MAP_ID}"]
    config, target = _Table("Quest/GDSActiveEventConfig.json"), _Table("Quest/GDSActiveEventTarget.json")
    place, purpose = _Table("Quest/GDSActiveEventPlaceData.json"), _Table("Quest/GDSQuestPurposePoint.json")
    icon_rows = {r["mapIconType"]: r for r in _Table("Menu/GDSMapIconData.json").rows.values()}
    textures = _Table("Menu/GDSMenuIconTexture.json").rows
    titles = {k: (v["Text"][0].get("nounSingularForm_en") if v.get("Text") else "")
              for k, v in _Table("Quest/GDSQuestTitleText.json").rows.items()}

    world = {}
    noun = _Table("Map/GDSMapText_Noun.json").rows
    for r in _Table("Map/GDSWorldMapData.json").rows.values():
        if r["mapId"] in WORLD_MAP_IDS and r["mapId"] not in world:
            name = ((noun.get(r["nameId"]) or {}).get("nounInfo") or [{}])[0].get("nounSingularForm_en")
            world[r["mapId"]] = {"name": "Ginormosia" if r["mapId"] == MAP_ID else name or r["mapId"],
                                 "region": r["MapRegion"]}
    # Dream / Roguelike overworld is not on GDSWorldMapData (Loom CONFIRMED).
    if DREAM_MAP_ID not in world:
        world[DREAM_MAP_ID] = {"name": "Snoozaland", "region": 3}
    minimaps = {m: _minimap_row(m) for m in WORLD_MAP_IDS}
    minimaps = {m: row for m, row in minimaps.items() if row and m in world}

    def uv(map_id, x, y):
        return _uv({"X": x, "Y": y}, minimaps[map_id])

    from . import mapmarkers
    markers = mapmarkers.build(minimaps, uv)
    marker_icons = {m[1] for ms in markers.values() for m in ms} | {c[2] for c in mapmarkers.CATEGORIES}

    (out / "icons").mkdir(parents=True, exist_ok=True)
    (out / "maps").mkdir(parents=True, exist_ok=True)
    icons = {}
    # Ship every atlas type that has a texture — game chrome, not a shortlist.
    want_icons = set(icon_rows) | {PLAYER_ICON, *GLOW_ICONS, *EVENT_ICONS, *CHROME_ICONS, *marker_icons}
    for t in sorted(want_icons):
        if t not in icon_rows:
            continue
        mid = icon_rows[t]["mapIconId"]
        if not mid or mid == "None" or mid not in textures:
            continue
        row = icon_rows[t]
        asset = textures[mid]["iconInfoPerId"]["AssetPath"].split(".")[0]
        src = paths.EXTRACT_DIR / "Game" / "Content" / (asset.removeprefix("/Game/") + ".png")
        if not src.exists():
            continue
        shutil.copyfile(src, out / "icons" / f"{t}.png")
        w, hgt = Image.open(src).size
        sc = row["iconScaleInfo"]
        icons[t] = {"size": [w, hgt], "priority": row["drawPriority"], "zoomScaled": sc["isChangedByMapScale"],
                    "scale": {k: sc[f"scale_{k}"]["X"] for k in ("s", "m", "l")},
                    "texture": Path(asset).name, "mapIconId": mid,
                    "outOfRange": bool(row.get("outOfRangeDisplay")),
                    "enableSelect": bool(row.get("enableSelect"))}

    areas = {}
    try:
        map_noun = _Table("Map/GDSMapText_Noun.json").rows
        for aid, a in _Table("Map/GDSAreaDef.json").rows.items():
            info = (map_noun.get(a.get("m_areaNameId")) or {}).get("nounInfo") or [{}]
            name = info[0].get("nounSingularForm_en")
            if name:
                areas[aid] = name
    except (FileNotFoundError, KeyError, IndexError):
        pass

    events = {}
    for eid, c in config.rows.items():
        pl = place.rows.get(c["EventPointId"], {})
        pp = purpose.rows.get(pl.get("purposePointId"))
        if pl.get("mapId") != MAP_ID or not pp:
            continue
        t = target.rows.get(eid, {})
        glow = pp["mapIconType"]
        title = titles.get(c["TitleId"]) or eid
        u, v = _uv(pp["tgtPosition"], mm)
        area = pl.get("AreaID")
        events[eid] = {"u": u, "v": v, "glow": glow, "title": title,
                       "icon": icon_type(title, t.get("ActiveEventType", 0), t.get("OverrideMapIconType", 0),
                                         glow == 114),
                       "area": area, "areaName": areas.get(area) or "",
                       "place": c.get("EventPointId") or ""}

    craft = _craft_hud()
    Image.MAX_IMAGE_PIXELS = None
    maps = []
    for m, row in minimaps.items():
        src = _art_path(m)
        art_rel = None
        if src.exists():
            art = Image.open(src).convert("RGB")
            if m in (MAP_ID, DREAM_MAP_ID) and art.size[0] >= MAP_PX:
                if art.size != (MAP_PX, MAP_PX):
                    art = art.resize((MAP_PX, MAP_PX), Image.LANCZOS)
            art.save(out / "maps" / f"{m}.jpg", quality=90)
            art_rel = f"maps/{m}.jpg"
            if m == CRAFT_MAP_ID and craft:
                # Game craft HUD crop — same Base Camp art the pad minimap uses.
                bw, bh = craft["baseTextureWidth"], craft["baseTextureHeight"]
                ox, oy = craft["targetOffsetX"], craft["targetOffsetY"]
                tw, th = craft["targetWidth"], craft["targetHeight"]
                full = art if art.size == (bw, bh) else art.resize((bw, bh), Image.LANCZOS)
                full.crop((ox, oy, ox + tw, oy + th)).save(out / "maps" / f"{m}_craft.jpg", quality=92)
        entry = {
            "id": m, **world[m], "art": art_rel,
            "bounds": {k: row[k] for k in ("minX", "maxX", "minY", "maxY")},
            "zoom": row["scaleTypeInfo"], "mapIconScale": row["mapIconScale"], "textureSize": row["mapTextureSizeX"],
            "scroll": [row["scrollMinX"], row["scrollMaxX"]], "markers": markers.get(m, []),
        }
        if m == CRAFT_MAP_ID and craft and (out / "maps" / f"{m}_craft.jpg").exists():
            entry["craftHud"] = {**craft, "art": f"maps/{m}_craft.jpg"}
        maps.append(entry)
    (out / "map.jpg").unlink(missing_ok=True)
    meta = {
        "eventMap": MAP_ID, "dreamMap": DREAM_MAP_ID, "maps": maps, "categories": mapmarkers.CATEGORIES,
        "icons": icons, "events": events, "player": PLAYER_ICON,
        "activeEventMaterial": _material(MAT_DIR / "mat_map_000012.json"),
        "extMaterials": {
            "ripple": "mat_map_000010", "activeEvent": "mat_map_000012", "questOrder": "mat_map_000022",
            "questArea": "mat_map_000020", "story": "mat_map_000023", "fastTravel": "mat_map_000060",
            "fastTravelRankUp": "mat_map_000061", "alchemy": "mat_map_000040", "magicCircle": "mat_map_000050",
        },
    }
    (out / "mapview.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts = {m["id"]: len(m["markers"]) for m in maps}
    log(f"map viewer: {len(maps)} maps {counts}, {len(events)} event places, {len(icons)} icons -> {out}")
    return {"maps": len(maps), "events": len(events), "icons": len(icons), "markers": counts}
