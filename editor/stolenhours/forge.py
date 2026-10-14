"""Vulcan's Forge: craft any recipe's item out of game and pick how it comes out.

Game data:
- `GDSRecipeData` (2012 recipes): product ItemId, `titleType` and `rewardData` rank0..rank3 item ids. Weapons and
  tools have one recipe per grade (`_01`/`_02`/`_03`, titleType = that grade); armor has titleType 0 and its grade
  comes from the craft. 700 recipes give a better item on a great craft (rank2_itemId, e.g. HP Potion -> HP Potion +).
- Gear stats per grade (index = grade - 1) in `GDSItemWeaponData` (physical/magic offense), `GDSItemLifeToolsData`
  (lifeParam) and `GDSItemArmorData` (physical/magic defense, shields included). A value <= 1 on every list means
  the item doesn't come in that grade (Bronze Sword 180/210/250/1/1: Ordinary, Fine, Notable).
- Per grade: `addStatusLotTableList` -> `GDSAddStatusLotTable` (the bonus stat type) and `addSkillLotTableList` ->
  `GDSAddSkillLotTable` (skills with lotWeight > 0 can roll). Grade names from `GDSItemTitleData`.

Two separate results (the game's own wording): rank/grade Ordinary..Legendary, picked before crafting and capped per
item, and quality Normal/Good/Great/Top (`EItemQualityType` 0-3, `name_item_quality_00N`), which the minigame gives
by how many turns are left (players report Good 3+, Great 5+, Top 7+).

Save side (`InventoryInfoEquip`, Unholy's save 2026-10-13): `itemTitle` = grade 1-5, `Quality` = 0-3 (0 on every item
in the save), `addEquipStatus` =
[{Type: EEquipStatusType, Value: 0}], `grantSkillId` = 3 skill names ("None" when empty). Crafted Bronze Sword:
title 2, Type 3, one skill. Bonus Value is 0 on every item in the save.
UNVERIFIED: that the game accepts any grade in the item's window, a bonus stat on any grade, and up to three skills
from that grade's pool; that it computes the bonus amount itself from Value 0; that Quality 1-3 shows as
Good/Great/Top and raises the stats (no item in the save has a quality yet).
Check: forge one of each, load the save, look at the item's details in the bag.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import paths, skillboard, uiassets
from .collection import GAME_DATA, _nouns, _rows, _texts
from .savefile import SaveFile, SaveFileError

DATA_FILE = paths.UI_ASSET_DIR / "forge" / "forge.json"
DETAILS_FILE = paths.UI_ASSET_DIR / "items" / "details.json"
DATA_PATTERN = (r"^Game/Content/GameData/(Recipe/GDSRecipe(Data|TabData)|Item/GDSItem\w*Data|Item/GDSItemText|"
                r"Item/GDSAdd(Skill|Status)LotTable|Item/GDSItemText_Noun|Skill/GDSSkill(Data|Text|Text_Noun)|"
                r"Menu/GDSMenuText)\.uasset$")
GEAR = {"Weapon": [("Attack", "physicalOffenseList"), ("Magic Attack", "magicOffenseList")],
        "LifeTools": [("Power", "lifeParamList")],
        "Armor": [("Defense", "physicalDefenseList"), ("Magic Defense", "magicDefenseList")]}
STATUS_NAMES = {1: "Max HP", 2: "Max SP", 3: "Attack", 4: "Defense", 5: "Magic Attack", 6: "Magic Defense",
                7: "Crafting", 8: "Gathering"}
GRADES = 5
QUALITIES = 4  # EItemQualityType 0..3
FORGE_MAX = 99


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "Item" / "GDSAddSkillLotTable.json").exists() \
            or not (GAME_DATA / "Item" / "GDSItemEffDescData.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)


def build(out: Path | None = None, log=print) -> dict:
    out = out or DATA_FILE.parent
    if not (GAME_DATA / "Item" / "GDSAddSkillLotTable.json").exists():
        log("forge: no exported data; run extract first")
        return {"missing": ["forge data"]}
    item_noun, menu = _nouns("Item/GDSItemText_Noun.json"), _texts("Menu/GDSMenuText.json")
    grades = {int(k): item_noun.get(v.get("titleText"), k) for k, v in _rows("Item/GDSItemTitleData.json").items()}
    qualities = {q: item_noun.get(f"name_item_quality_{q:03d}", str(q)) for q in range(QUALITIES)}
    skill_rows = _rows("Skill/GDSSkillData.json")
    skill_noun, skill_text = _nouns("Skill/GDSSkillText_Noun.json"), _texts("Skill/GDSSkillText.json")
    status_lots = {k: [s["addStatusType"] for s in v["addStatusInfoList"] if s["lotWeight"] > 0]
                   for k, v in _rows("Item/GDSAddStatusLotTable.json").items()}
    skill_lots = {k: [s["SkillID"] for s in v["addSkillInfoList"] if s["lotWeight"] > 0]
                  for k, v in _rows("Item/GDSAddSkillLotTable.json").items()}

    gear = {}
    for table, stats in GEAR.items():
        for iid, v in _rows(f"Item/GDSItem{table}Data.json").items():
            lists = [(label, v[key]) for label, key in stats if any(x > 1 for x in v.get(key) or [])]
            window = [g for g in range(1, GRADES + 1) if any(l[g - 1] > 1 for _, l in lists)]
            gear[iid] = {
                "stats": [[label, l] for label, l in lists],
                "grades": window or list(range(1, GRADES + 1)),
                "bonus": [(status_lots.get(t) or [0])[0] for t in v.get("addStatusLotTableList") or ["None"] * GRADES],
                "pools": [skill_lots.get(t, []) for t in v.get("addSkillLotTableList") or ["None"] * GRADES],
            }
    item_flags = {}
    for f in (GAME_DATA / "Item").glob("GDSItem*Data.json"):
        try:
            for k, v in _rows(f"Item/{f.name}").items():
                if isinstance(v, dict) and isinstance(v.get("flagNo"), int):
                    item_flags[k] = v["flagNo"]
        except (KeyError, IndexError, ValueError):
            pass

    tabs = {v["Category"]: menu.get(v["tabNameId"], str(v["Category"])) for v in _rows("Recipe/GDSRecipeTabData.json").values()}
    items: dict[str, dict] = {}
    for rid, r in _rows("Recipe/GDSRecipeData.json").items():
        iid = r["ItemId"]
        if iid in (None, "None"):
            continue
        m = re.match(r"recipe_life(\d+)_", rid)
        life = f"life{int(m.group(1)):04d}" if m else None
        e = items.setdefault(iid, {"id": iid, "lives": [], "tab": tabs.get(r.get("Category"), ""),
                                   "rarity": r.get("rarity", 0), "mats": {}})
        if life and life not in e["lives"]:
            e["lives"].append(life)
        e["mats"].setdefault(str(r.get("titleType", 0)), [{"id": x["ItemId"], "num": x["numItems"]}
                                                          for x in r.get("itemList", []) if x.get("ItemId") not in (None, "None")])
        rd = r.get("rewardData") or {}
        plus = rd.get("rank2_itemId")
        if plus not in (None, "None", iid):
            e["plus"] = plus
        if iid in gear:
            e.update({k: gear[iid][k] for k in ("stats", "grades", "bonus", "pools")})
    used = sorted({s for e in items.values() for p in e.get("pools", []) for s in p})
    skill_table = skillboard._Table("GDSSkillData")
    skills = {sid: _skill_info(sid, skill_rows, skill_noun, skill_text, skill_table) for sid in used}
    _build_details(gear, grades, qualities, skill_rows, skill_noun, skill_text, skill_table, log)
    made = set(items) | {e["plus"] for e in items.values() if "plus" in e}
    flags = {k: item_flags[k] for k in sorted(made) if k in item_flags}

    data = {"grades": {str(k): v for k, v in grades.items()}, "qualities": {str(k): v for k, v in qualities.items()},
            "status": STATUS_NAMES, "skills": skills,
            "items": list(items.values()), "flags": flags}
    out.mkdir(parents=True, exist_ok=True)
    (out / "forge.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_gear = sum(1 for e in items.values() if "grades" in e)
    log(f"forge: {len(items)} craftable items ({n_gear} gear, {sum(1 for e in items.values() if 'plus' in e)} with a "
        f"+ version), {len(skills)} skills -> {out}")
    return {"items": len(items), "gear": n_gear}


def _skill_info(sid, rows, noun, text, table) -> dict:
    row = rows.get(sid, {})
    name = noun.get(row.get("nameTextID")) or text.get(row.get("nameTextID")) or sid
    args = [table.arg(a) for a in row.get("Params", {}).get("prm", []) if a["m_dataSize"]] if row else []
    desc = re.sub(r"<SKILL_PARAM_(\d+)>", lambda m: str(args[int(m.group(1)) - 1]) if int(m.group(1)) <= len(args)
                  else "?", text.get(row.get("dascTextId"), ""))
    return {"name": name, "desc": desc}


def _build_details(gear, grades, qualities, skill_rows, skill_noun, skill_text, skill_table, log) -> None:
    """`game/items/details.json`: what the Bag shows for an item (gear stats per grade, consumable effects)."""
    item_text = _texts("Item/GDSItemText.json")
    eff_desc = {k: v["DescId"] for k, v in _rows("Item/GDSItemEffDescData.json").items()}
    effects, prices = {}, {}  # prices per grade (index grade-1; non-gear uses the first)
    for f in (GAME_DATA / "Item").glob("GDSItem*Data.json"):
        try:
            rows = _rows(f"Item/{f.name}")
        except (KeyError, IndexError, ValueError):
            continue
        for iid, v in rows.items():
            if not isinstance(v, dict):
                continue
            price = (v.get("priceInfo") or {})
            sell, buy = price.get("priceSellRichList") or [], price.get("priceBuyRichList") or []
            if any(sell) or any(buy):
                prices[iid] = {"sell": sell, "buy": buy}
            if "effParam0" not in v:
                continue
            lines = []
            for n in range(3):
                p = v.get(f"effParam{n}") or {}
                tmpl = item_text.get(eff_desc.get(p.get("effDescId"), ""), "")
                if tmpl:
                    lines.append(tmpl.replace("<ITEM_EFF_VAL>", str(p.get("val", ""))).replace("<ITEM_EFF_TIME>", str(p.get("Time", ""))))
            if lines:
                effects[iid] = lines
    skills = {sid: _skill_info(sid, skill_rows, skill_noun, skill_text, skill_table)
              for sid in skill_rows if sid.startswith("es_")}
    data = {"grades": {str(k): v for k, v in grades.items()}, "qualities": {str(k): v for k, v in qualities.items()},
            "status": STATUS_NAMES, "skills": skills, "effects": effects, "prices": prices,
            "gear": {k: {"stats": v["stats"], "grades": v["grades"]} for k, v in gear.items()}}
    DETAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DETAILS_FILE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"item details: {len(gear)} gear, {len(effects)} with effects, {len(prices)} with prices, "
        f"{len(skills)} equipment skills -> {DETAILS_FILE}")


class Forge:
    def __init__(self, data: dict):
        self.items: dict[str, dict] = {e["id"]: e for e in data["items"]}
        self.skills: dict[str, dict] = data["skills"]
        self.flags: dict[str, int] = data["flags"]
        self.data = data

    @classmethod
    def load(cls, path: Path = DATA_FILE) -> "Forge":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def default_grade(self, item_id: str) -> int | None:
        e = self.items.get(item_id)
        return e["grades"][0] if e and "grades" in e else None

    def craft(self, sf: SaveFile, item_id: str, info: dict, count: int = 1, grade: int | None = None,
              bonus: bool = True, skills: list[str] | None = None, plus: bool = False, quality: int = 0) -> dict:
        """Put `count` of a recipe's item in the bag, as the chosen grade / quality / skills or the + version."""
        e = self.items.get(item_id)
        if e is None:
            raise SaveFileError(f"{item_id} is not made by any recipe")
        if not 1 <= int(count) <= FORGE_MAX:
            raise SaveFileError(f"make 1..{FORGE_MAX} at a time")
        count = int(count)
        if "grades" in e:
            grade = int(grade or e["grades"][0])
            if grade not in e["grades"]:
                raise SaveFileError(f"this item doesn't come in grade {grade}")
            skills = [s for s in skills or [] if s]
            pool = set(e["pools"][grade - 1])
            bad = [s for s in skills if s not in pool]
            if bad:
                raise SaveFileError(f"{', '.join(bad)} can't roll on this item at that grade")
            make = item_id
            if not 0 <= int(quality) < QUALITIES:
                raise SaveFileError(f"quality must be 0..{QUALITIES - 1}")
            kw = {"title": grade, "bonus": e["bonus"][grade - 1] if bonus else 0, "skills": skills,
                  "quality": int(quality)}
        else:
            if grade or skills or quality:
                raise SaveFileError("only gear has a grade, quality and skills")
            make = e.get("plus") if plus else item_id
            if not make:
                raise SaveFileError("this recipe has no + version")
            kw = {}
        meta = info.get(make)
        if not meta or not meta.get("pocket"):
            raise SaveFileError(f"{make} has no known bag pocket")
        pocket, cap = meta["pocket"], int(meta.get("stack") or 1)
        have = next((it for it in sf.items(pocket) if it.item_id == make), None)
        if cap > 1 and have is not None and have.stock is not None:
            if have.stock >= cap:
                raise SaveFileError(f"you already have a full stack ({cap})")
            count = min(have.stock + count, cap) - have.stock
            sf.set_stock(pocket, have.index, have.stock + count)
        elif cap > 1:
            count = min(count, cap)
            sf.add_item(pocket, make, count)
        else:
            for _ in range(count):
                sf.add_item(pocket, make, 1, **kw)
        flag = self.flags.get(make)
        if flag is not None:
            sf.sd["m_FlagStatus"]["GlobalItemGetFlag"][flag] = 1
        sf.dirty = True
        return {"item": make, "pocket": pocket, "count": count}
