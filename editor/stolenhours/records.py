"""Play records: everything the save counts about how you play, plus the editor's own history of each save.

Save fields (types from the pattern file):
- `m_PlayData.playCountData` (PLAY_DATA_COUNT): u32 counters (monsters, bosses, gathering by kind, crafting
  requests, ...), `developmentRank` s32, `islandPurchaseNums` Array<u32>, two Map<u8, u32> per enemy type / weapon.
- `m_PlayData`: playTime (seconds), startDateTime / saveDateTime (.NET ticks), Money, goddessHerbBlue/Gold,
  sweetChestnut, interactionPoint (s32), ArenaRank (u8), plantdungeonMaxReachGen (u32).
- collection counts: set entries in `m_FlagStatus` GlobalItemGetFlag (items ever obtained), GlobalLibraryFlag,
  GlobalVisitMapFlag, GlobalHelpOpenFlag, GlobalAchievementReceiveFlag; recipes with a non-zero bitFlag.
The game keeps no lifetime totals (e.g. Dosh earned), so the editor snapshots every save it opens in
`USER_DATA/records_history.jsonl` and shows the change since the first and the previous snapshot.
UNVERIFIED: labels are read from the field names; several counters stay 0 on Unholy's chapter-3 save
(defeatEnemyNum among them), so when the game starts counting each one is not confirmed.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import paths
from .savefile import SaveFile, SaveFileError

HISTORY_FILE = paths.USER_DATA / "records_history.jsonl"
U32, S32, U8 = (0, 2**32 - 1), (0, 2**31 - 1), (0, 255)
DOTNET_EPOCH = 621355968000000000

# (group, [(path, label, range or None for read-only)]); paths are dotted from saveData
COUNT = "m_PlayData.playCountData."
GROUPS = [
    ("Battle", [
        (COUNT + "defeatEnemyNum", "Monsters defeated", U32),
        (COUNT + "defeatBossNum", "Bosses defeated", U32),
        (COUNT + "defeatBossWithMultiPlayNum", "Bosses defeated in multiplayer", U32),
    ]),
    ("Gathering", [
        (COUNT + "pickTreeNum", "Trees felled", U32),
        (COUNT + "pickOreNum", "Ore mined", U32),
        (COUNT + "pickFishNum", "Fish caught", U32),
        (COUNT + "pickVegetableNum", "Crops harvested", U32),
        (COUNT + "pickBossTreeNum", "Boss trees felled", U32),
        (COUNT + "pickBossOreNum", "Boss ore mined", U32),
        (COUNT + "pickBossFishNum", "Boss fish caught", U32),
        (COUNT + "pickBossVegetableNum", "Boss crops harvested", U32),
        (COUNT + "pickBossTreeWithMultiPlayNum", "Boss trees felled in multiplayer", U32),
        (COUNT + "pickBossOreWithMultiPlayNum", "Boss ore mined in multiplayer", U32),
        (COUNT + "pickBossFishWithMultiPlayNum", "Boss fish caught in multiplayer", U32),
        (COUNT + "pickBossVegetableWithMultiPlayNum", "Boss crops harvested in multiplayer", U32),
        (COUNT + "pickShellNum", "Shells gathered", U32),
        (COUNT + "pickBugNum", "Bugs caught", U32),
        (COUNT + "pickEggNum", "Eggs gathered", U32),
        (COUNT + "pickGrassAndflowerNum", "Herbs and flowers picked", U32),
        (COUNT + "pickMushroomNum", "Mushrooms picked", U32),
        (COUNT + "pickFruitsNum", "Fruit picked", U32),
    ]),
    ("Crafting and farming", [
        (COUNT + "requestBlacksmithNPCNum", "Blacksmith requests", U32),
        (COUNT + "requestNeedleworkerNPCNum", "Tailor requests", U32),
        (COUNT + "requestCarpenterNPCNum", "Carpenter requests", U32),
        (COUNT + "requestCookNPCNum", "Cook requests", U32),
        (COUNT + "requestAlchemistNPCNum", "Alchemist requests", U32),
        (COUNT + "requestArtistNPCNum", "Artist requests", U32),
        (COUNT + "itemCraftUseAddItemNum", "Crafts with added items", U32),
        (COUNT + "harvestingGameNormalClearNum", "Harvest minigames cleared", U32),
        (COUNT + "sowingSeedsOrWateringNum", "Seeds sown or watered", U32),
        (COUNT + "galleryRevenueNum", "Gallery sales", U32),
    ]),
    ("Island and world", [
        (COUNT + "questClearNum", "Quests cleared", U32),
        (COUNT + "obstacleReleaseNum", "Obstacles cleared", U32),
        (COUNT + "getTamagemonoNum", "Strangelings found", U32),
        (COUNT + "tamagemonoReleaseNum", "Strangelings released", U32),
        (COUNT + "trustValMaxNum", "Friends at max trust", U32),
        (COUNT + "growUpPlantDungeonNum", "Dungeon trees grown", U32),
        (COUNT + "joinChallengeTourNum", "Challenge tours joined", U32),
        (COUNT + "instantCharaJoinNum", "Guests joined", U32),
        (COUNT + "developmentRank", "Development rank", S32),
        ("m_PlayData.plantdungeonMaxReachGen", "Deepest dungeon-tree generation", U32),
        ("m_PlayData.ArenaRank", "Arena rank", U8),
    ]),
    ("Currencies", [
        ("m_PlayData.goddessHerbBlue", "Blue goddess herbs", S32),
        ("m_PlayData.goddessHerbGold", "Gold goddess herbs", S32),
        ("m_PlayData.sweetChestnut", "Sweet chestnuts", S32),
        ("m_PlayData.interactionPoint", "Interaction points", S32),
    ]),
]
EDITABLE = {p: rng for _, rows in GROUPS for p, _, rng in rows if rng}


def _get(sd: dict, path: str):
    o = sd
    for part in path.split("."):
        o = o[part]
    return o


def _set(sd: dict, path: str, value) -> None:
    *head, last = path.split(".")
    o = sd
    for part in head:
        o = o[part]
    o[last] = value


def _ticks(t: int) -> str | None:
    if not t:
        return None
    return datetime.fromtimestamp((t - DOTNET_EPOCH) / 1e7, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def _count(flags: list) -> int:
    return sum(1 for f in flags if f)


def snapshot(sf: SaveFile) -> dict:
    """Every number shown on the Records page, flat, for history and deltas."""
    sd = sf.sd
    pd, fs = sd["m_PlayData"], sd["m_FlagStatus"]
    out = {p: _get(sd, p) for _, rows in GROUPS for p, _, _ in rows}
    out.update({
        "playTime": pd["playTime"], "Money": pd["Money"],
        "islandPurchases": sum(pd["playCountData"]["islandPurchaseNums"]),
        "itemsObtained": _count(fs["GlobalItemGetFlag"]), "library": _count(fs["GlobalLibraryFlag"]),
        "mapsVisited": _count(fs["GlobalVisitMapFlag"]), "helpPages": _count(fs["GlobalHelpOpenFlag"]),
        "achievements": _count(fs["GlobalAchievementReceiveFlag"]), "storyFlags": _count(fs["GlobalBitFlag"]),
        "recipes": sum(1 for r in sd["m_RecipeStatus"]["recipeInfoMap"] if r["value"]["bitFlag"]),
        "lifeLevels": sum(l["level"] or 0 for l in sf.lives() if l["id"] != "life0000"),
        "licenses": sum(1 for l in sf.lives() if l["rank"] > 0 and l["id"] != "life0000"),
        "mapEventsCleared": sum(1 for e in sd["m_QuestStatus"]["Active"] if e["value"]["phase"] in (254, 255)),
        "items": sum(it.stock or 0 for c in sf.inventory_categories() for it in sf.items(c)),
    })
    return out


SUMMARY = [
    ("playTime", "Play time"), ("Money", "Dosh"), ("lifeLevels", "Total life levels"), ("licenses", "Licenses held"),
    ("items", "Items carried"), ("itemsObtained", "Different items obtained"), ("recipes", "Recipes known"),
    ("library", "Library entries"), ("mapsVisited", "Places visited"), ("mapEventsCleared", "Map events cleared"),
    ("islandPurchases", "Island purchases"), ("achievements", "Achievements received"), ("helpPages", "Help pages read"),
    ("storyFlags", "Story flags set"),
]


def _save_id(sf: SaveFile) -> str:
    pd = sf.sd["m_PlayData"]
    return f"{pd['startDateTime']}|{sf.island_name}"


def _history(save_id: str, path: Path = HISTORY_FILE) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("save") == save_id:
            out.append(e)
    return out


def record(sf: SaveFile, path: Path = HISTORY_FILE) -> bool:
    """Append a snapshot of the save as loaded from disk when it differs from the last one. Returns True if added."""
    sid, snap = _save_id(sf), snapshot(sf)
    hist = _history(sid, path)
    if hist and hist[-1]["values"] == snap:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"save": sid, "time": time.strftime("%Y-%m-%d %H:%M"),
                            "saved": _ticks(sf.sd["m_PlayData"]["saveDateTime"]), "values": snap}) + "\n")
    return True


def records(sf: SaveFile, path: Path = HISTORY_FILE) -> dict:
    sd, snap = sf.sd, snapshot(sf)
    hist = _history(_save_id(sf), path)
    first = hist[0] if hist else None
    prev = next((h for h in reversed(hist) if h["values"] != snap), None)

    def row(key, label, rng=None):
        v = snap[key]
        r = {"key": key, "label": label, "value": v, "editable": rng is not None}
        if rng:
            r["max"] = rng[1]
        if first and isinstance(first["values"].get(key), (int, float)):
            r["sinceFirst"] = v - first["values"][key]
        if prev and isinstance(prev["values"].get(key), (int, float)):
            r["sincePrev"] = v - prev["values"][key]
        return r

    pc = sd["m_PlayData"]["playCountData"]
    return {
        "started": _ticks(sd["m_PlayData"]["startDateTime"]), "saved": _ticks(sd["m_PlayData"]["saveDateTime"]),
        "tracking": {"since": first["time"] if first else None, "snapshots": len(hist),
                     "prev": prev["time"] if prev else None},
        "summary": [row(k, label) for k, label in SUMMARY],
        "groups": [{"title": g, "rows": [row(p, label, rng) for p, label, rng in rows]} for g, rows in GROUPS],
        "byEnemyType": pc["defeatEnemyNumByTypeID"], "byWeapon": pc["defeatEnemyNumWithWeapon"],
    }


def set_record(sf: SaveFile, key: str, value: int) -> None:
    rng = EDITABLE.get(key)
    if rng is None:
        raise SaveFileError(f"{key} is not an editable record")
    value = int(value)
    if not rng[0] <= value <= rng[1]:
        raise SaveFileError(f"value must be {rng[0]}..{rng[1]}")
    if _get(sf.sd, key) != value:
        _set(sf.sd, key, value)
        sf.dirty = True
