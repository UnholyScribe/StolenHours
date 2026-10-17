"""Static map markers: everything the game's world maps place from data tables, per world map.

Sources (all game data; positions are world X/Y, turned into map UV with each map's minimap bounds):
- Towers / travel points / towns: `GDSFastTravel` (Ginormosia towers are titled with their region `name_HugeMap_NN`,
  towns use `ICON_TAB_BOARD_10`).
- Places with a map icon: `<map>_GDSMapFuncPoint` and `<map>_GDSMapJumpFuncPointPlacement` rows whose `mapIconType`
  is set (campfires 171, workbenches 141, guilds and shops, Goddess Statues, warp circles, ...).
- Shrines: `GDSTamagemonoShrineData.MapIconInfo`. Leafe: `<map>_GDSMapPlantLeafePlacement`.
- Gathering: `<map>_GDSMapPickPoint` (Type 1 wood, 2 ore, 3 fish, 4 crops). Monsters: `<map>_GDSMapEnemyPlacementConfig`
  groups, named through `GDSCharaParameterEnemy.charaID` -> `GDSCharaText_Noun`.
- Request givers: `GDSQuestRequesterSetting.search`. Dungeon entrances: `GDSDungeonEntranceIconSetting`.
UNVERIFIED: the game shows many of these only once found / unlocked (conditions and save flags are not applied here),
and the icon picked for towers (118), towns (119), travel points (118), shrines (138), dungeon entrances (135),
request givers (5), monster groups (3 normal, 16 Gold-rank, 17 boss) and gathering (18 wood, 22 ore, 20 fish, 24
crops) follows the icon art and what the in-game map showed in Unholy's screenshots. Monster groups that swap with
the area rank (`CondCmd_AreaRank_Less` / `_Greater` pairs) show the starting set only. Check: compare in game.
"""
from __future__ import annotations

import collections
import re

from .mapevents import _Table

CATEGORIES = [
    # id, label, icon shown in the list
    ("tower", "Towers", 118),
    ("town", "Towns", 119),
    ("travel", "Travel points", 118),
    ("camp", "Campfires", 171),
    ("bench", "Workbenches", 141),
    ("shop", "Shops & guilds", 58),
    ("statue", "Goddess Statues", 116),
    ("shrine", "Shrines", 138),
    ("dungeon", "Dungeons & caves", 135),
    ("place", "Other places", 172),
    ("leafe", "Leafe", 120),
    ("request", "Requests", 5),
    ("monster", "Monsters", 3),
    ("wood", "Trees", 18),
    ("ore", "Ore", 22),
    ("fish", "Fishing spots", 20),
    ("crop", "Crops", 24),
]
PICK = {1: ("wood", 18, "Tree"), 2: ("ore", 22, "Ore"), 3: ("fish", 20, "Fishing spot"), 4: ("crop", 24, "Crops")}
SHOP_ICONS = set(range(57, 104)) | {121, 140, 142, 143, 144, 165, 173, 182}
SKIP_ICONS = {0, 1, 2, 108, 109, 110, 111, 112, 113, 114, 136}  # player, quest pins, event glows, online-only marker


def _noun(rows: dict, key: str) -> str | None:
    row = rows.get(key) or {}
    info = row.get("nounInfo") or row.get("textInfo") or [{}]
    return info[0].get("nounSingularForm_en") or None


def _table(rel: str) -> dict:
    try:
        return _Table(rel).rows
    except (FileNotFoundError, KeyError, IndexError):
        return {}


def _icon_category(t: int) -> str:
    if t == 171:
        return "camp"
    if t == 141:
        return "bench"
    if t in (116, 117):
        return "statue"
    if t in SHOP_ICONS:
        return "shop"
    if t in (36, 49, 123, 135, 181, 217, 218):
        return "dungeon"
    return "place"


def _sub_map_only(conds: list) -> bool:
    """Rows that only exist inside a shrine / sub-level, not on the world map itself."""
    return any(c.get("Cmd", "").startswith(("CondCmd_SubMapId", "CondCmd_IsShrineMinigame", "CondCmd_ShrineMinigame"))
               for c in conds or [])


def build(maps: dict[str, dict], uv) -> dict[str, list]:
    """maps: map id -> minimap row; uv(map_id, x, y) -> (u, v). Returns map id -> [[cat, icon, u, v, name, detail]]."""
    map_noun = _table("Map/GDSMapText_Noun.json")
    chara_noun = _table("Chara/GDSCharaText_Noun.json")
    enemy_param = _table("Chara/GDSCharaParameterEnemy.json")
    icon_rows = {r["mapIconType"]: r for r in _table("Menu/GDSMapIconData.json").values()}
    out: dict[str, list] = {m: [] for m in maps}
    seen: dict[str, set] = collections.defaultdict(set)

    def add(m, cat, icon, x, y, name, detail=""):
        if m not in out:
            return
        u, v = uv(m, x, y)
        if not (-0.05 <= u <= 1.05 and -0.05 <= v <= 1.05):
            return
        key = (cat, round(u, 4), round(v, 4), name)
        if key in seen[m]:
            return
        seen[m].add(key)
        out[m].append([cat, icon, round(u, 5), round(v, 5), name or "", detail])

    def icon_name(t):
        r = icon_rows.get(t)
        return _noun(map_noun, r["mapTextId"]) if r and r["mapTextId"] != "None" else None

    for r in _table("Map/GDSFastTravel.json").values():
        m, pos, title = r["TargetMapID"], r["Position"], _noun(map_noun, r["Title"]) or r["ID"]["Name"]
        if r["Title"].startswith("name_HugeMap_"):
            add(m, "tower", 118, pos["X"], pos["Y"], f"{title} Tower", "Fast travel")
        elif r["iconID"] == "ICON_TAB_BOARD_10":
            add(m, "town", 119, pos["X"], pos["Y"], title, "Town · fast travel")
        else:
            add(m, "travel", 118, pos["X"], pos["Y"], title, "Fast travel point")

    for m in maps:
        for r in _table(f"Map/{m}/{m}_GDSMapFuncPoint.json").values():
            t = r.get("mapIconType", 0)
            pos = r.get("Position") or {}
            if t in SKIP_ICONS or t == 118 or not (pos.get("X") or pos.get("Y")):
                continue
            name = _noun(map_noun, (r.get("GameIconInfo") or {}).get("textId", "None")) or icon_name(t) or r["funcPointId"]
            add(m, _icon_category(t), t, pos["X"], pos["Y"], name)
        for r in _table(f"Map/{m}/{m}_GDSMapJumpFuncPointPlacement.json").values():
            t = r.get("mapIconType", 0)
            pos = r.get("Position") or {}
            if t in SKIP_ICONS or not (pos.get("X") or pos.get("Y")):
                continue
            gi = (r.get("gameIconInfoArray") or [{}])[0]
            name = _noun(map_noun, gi.get("textId", "None")) or icon_name(t) or r["ID"]
            add(m, _icon_category(t), t, pos["X"], pos["Y"], name)
        for r in _table(f"Map/{m}/{m}_GDSMapPlantLeafePlacement.json").values():
            kind = r.get("leafeType", "").removeprefix("plant_leafe_")
            add(m, "leafe", 120, r["Pos"]["X"], r["Pos"]["Y"], "Leafe", f"{kind.title()} Leafe" if kind else "")
        levels = collections.defaultdict(list)
        for r in _table(f"Map/{m}/{m}_GDSMapPickPoint.json").values():
            if r.get("Type") not in PICK or _sub_map_only(r.get("cond")):
                continue
            cat, icon, label = PICK[r["Type"]]
            p = r["actorPos"]
            lv = (r.get("ParamInfo") or {}).get("Level") or 0
            add(m, cat, icon, p["X"], p["Y"], label, f"Lv {lv}" if lv else "")
            levels[cat].append(lv)
        for r in _table(f"Map/{m}/{m}_GDSMapEnemyPlacementConfig.json").values():
            cmds = {c.get("Cmd") for c in r.get("Condition") or []}
            # area-rank pairs swap groups as the area ranks up: keep the starting (rank-less) set; quest-only groups out
            if r.get("subMapId", "None") != "None" or _sub_map_only(r.get("Condition")) or not r.get("Enemy") \
                    or cmds & {"CondCmd_AreaRank_Greater", "CondCmd_QuestPhase_Equal"}:
                continue
            enemies = r["Enemy"]
            p = enemies[0]["PopPoint"]
            names = collections.Counter()
            gold = boss = False
            for e in enemies:
                par = enemy_param.get(e["paramId"]["Name"]) or {}
                names[_noun(chara_noun, f"name_{par.get('charaID')}") or "???"] += 1
                gold |= par.get("rank") == "ETargetRankType::Gold"
                boss |= bool(e.get("isBossFight"))
            label = " + ".join(f"{n} x{c}" if c > 1 else n for n, c in names.most_common())
            lv = max(e.get("Level") or 0 for e in enemies)
            notes = [f"Lv {lv}" if lv else "", "boss" if boss else "strong" if gold else "",
                     "night only" if "CondCmd_GameTimePeriod_IsNight" in cmds else "",
                     "day only" if "CondCmd_GameTimePeriod_IsDay" in cmds else "",
                     "after story progress" if "CondCmd_Phase_Greater" in cmds else ""]
            add(m, "monster", 17 if boss else 16 if gold else 3, p["X"], p["Y"], label, " · ".join(n for n in notes if n))

    for r in _table("Map/GDSTamagemonoShrineData.json").values():
        name = _noun(map_noun, r.get("shrineNameId", "None")) or r["subMapId"]["Name"]
        for info in r.get("MapIconInfo") or []:
            p = info["mapIconPos"]
            add(info["dispMapId"], "shrine", 138, p["X"], p["Y"], name, "Shrine")
    for r in _table("Menu/GDSDungeonEntranceIconSetting.json").values():
        for e in r.get("entranceInfo") or []:
            p = e["worldPos"]
            add(r["mapId"], "dungeon", 135, p["X"], p["Y"], "Dungeon entrance", f"type {e.get('entranceIconType')}")
    for r in _table("Map/GDSQuestRequesterSetting.json").values():
        s = r.get("search") or {}
        p = s.get("mapPos") or {}
        if p.get("X") or p.get("Y"):
            add(s.get("mapId"), "request", 5, p["X"], p["Y"], "Request giver", re.sub(r"^map\d+_", "#", r["ID"]))
    return out
