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
# world maps shown by the game's map menu (GDSWorldMapData), in its order; Base Camp's art is built from the island
WORLD_MAP_IDS = ("Map_200000", "Map_100100", "Map_100101", "Map_100300", "Map_100400", "Map_100500", "Map_000101",
                 "Map_000100")
MAT_DIR = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D" / "UI" / "Map" / "Com" / "Mat"
BASE_MAT_DIR = paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D" / "Base_Material" / "UI"
MAP_PX = 8192  # the art's own size: the largest zoom step draws it ~6800px wide on a full-screen editor
PLAYER_ICON = 1
EVENT_ICONS = (124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 219)
GLOW_ICONS = (113, 114)
# gathering kind -> (normal, legendary) icon types; word lists match the event titles
GATHER = {"ore": (125, 131), "tree": (126, 132), "fish": (127, 133), "crop": (128, 134)}
GATHER_WORDS = {"ore": ("Ore", "Mining"), "tree": ("Tree", "Wood"), "fish": ("Fish",),
                "crop": ("Veggie", "Harvest", "Dessert")}
DATA_PATTERN = (r"^Game/Content/(GameData/(Menu/GDS(MapIconData|MenuIconTexture|DungeonEntranceIconSetting)|"
                r"Quest/GDSQuestPurposePoint|Map/Map_\d{6}/Map_\d{6}_GDSMap(Minimap|FuncPoint|JumpFuncPointPlacement|"
                r"PlantLeafePlacement|PickPoint|EnemyPlacementConfig)|Map/GDS(FastTravel|TamagemonoShrineData|"
                r"QuestRequesterSetting|WorldMapData|MapText_Noun)|Chara/GDS(CharaParameterEnemy|CharaText_Noun))|"
                r"Graphics/2D/(UI/Map/Com/Mat/mat_map_\w+|Base_Material/UI/basemat_ui_\w+))\.uasset$")
TEX_PATTERN = (rf"Graphics/2D/UI/(Map/{MAP_ID}/Tex/minimap_{MAP_ID}_000000|Map/Map_\d{{6}}/Tex/tex_map\d{{6}}_000000|"
               r"Icon/Map/tex_icon_map_mui)")


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "Menu" / "GDSDungeonEntranceIconSetting.json").exists() \
            or not (BASE_MAT_DIR / "basemat_ui_ripple_01.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)
    if force or not MAP_ART.exists() or not _art_path("Map_100100").exists():
        uiassets._run_extractor("export", TEX_PATTERN)


def _art_path(map_id: str) -> Path:
    if map_id == MAP_ID:
        return MAP_ART
    return TEX / "UI" / "Map" / map_id / "Tex" / f"tex_map{map_id.removeprefix('Map_')}_000000.png"


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
    """UNVERIFIED rule (see module doc): the map icon an active event shows."""
    if override:
        return override
    kind = next((k for k, words in GATHER_WORDS.items() if any(w in title for w in words)), None)
    if etype == 2 and kind:
        return GATHER[kind][1 if legendary else 0]
    if etype == 1 or etype == 0:
        return 130 if legendary else 124
    if etype == 3:
        return 129
    return 219


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
    minimaps = {m: _minimap_row(m) for m in WORLD_MAP_IDS}
    minimaps = {m: mm for m, mm in minimaps.items() if mm and m in world}

    def uv(map_id, x, y):
        return _uv({"X": x, "Y": y}, minimaps[map_id])

    from . import mapmarkers
    markers = mapmarkers.build(minimaps, uv)
    marker_icons = {m[1] for ms in markers.values() for m in ms} | {c[2] for c in mapmarkers.CATEGORIES}

    (out / "icons").mkdir(parents=True, exist_ok=True)
    (out / "maps").mkdir(parents=True, exist_ok=True)
    icons = {}
    for t in sorted({PLAYER_ICON, *GLOW_ICONS, *EVENT_ICONS, *marker_icons}):
        if t not in icon_rows or icon_rows[t]["mapIconId"] not in textures:
            continue
        row = icon_rows[t]
        asset = textures[row["mapIconId"]]["iconInfoPerId"]["AssetPath"].split(".")[0]
        src = paths.EXTRACT_DIR / "Game" / "Content" / (asset.removeprefix("/Game/") + ".png")
        shutil.copyfile(src, out / "icons" / f"{t}.png")
        w, hgt = Image.open(src).size
        sc = row["iconScaleInfo"]
        icons[t] = {"size": [w, hgt], "priority": row["drawPriority"], "zoomScaled": sc["isChangedByMapScale"],
                    "scale": {k: sc[f"scale_{k}"]["X"] for k in ("s", "m", "l")},
                    "texture": Path(asset).name}

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
        events[eid] = {"u": u, "v": v, "glow": glow, "title": title,
                       "icon": icon_type(title, t.get("ActiveEventType", 0), t.get("OverrideMapIconType", 0),
                                         glow == 114)}

    Image.MAX_IMAGE_PIXELS = None
    maps = []
    for m, row in minimaps.items():
        src = _art_path(m)
        if src.exists():
            art = Image.open(src).convert("RGB")
            if m == MAP_ID and art.size != (MAP_PX, MAP_PX):
                art = art.resize((MAP_PX, MAP_PX), Image.LANCZOS)
            art.save(out / "maps" / f"{m}.jpg", quality=90)
        maps.append({
            "id": m, **world[m], "art": f"maps/{m}.jpg" if src.exists() else None,
            "bounds": {k: row[k] for k in ("minX", "maxX", "minY", "maxY")},
            "zoom": row["scaleTypeInfo"], "mapIconScale": row["mapIconScale"], "textureSize": row["mapTextureSizeX"],
            "scroll": [row["scrollMinX"], row["scrollMaxX"]], "markers": markers.get(m, []),
        })
    (out / "map.jpg").unlink(missing_ok=True)
    meta = {
        "eventMap": MAP_ID, "maps": maps, "categories": mapmarkers.CATEGORIES,
        "icons": icons, "events": events, "player": PLAYER_ICON,
        "activeEventMaterial": _material(MAT_DIR / "mat_map_000012.json"),
    }
    (out / "mapview.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts = {m["id"]: len(m["markers"]) for m in maps}
    log(f"map viewer: {len(maps)} maps {counts}, {len(events)} event places, {len(icons)} icons -> {out}")
    return {"maps": len(maps), "events": len(events), "icons": len(icons), "markers": counts}
