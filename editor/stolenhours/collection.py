"""Recipes, the Library (the game's encyclopedia) and Gifts: what the save has, and unlocking or re-claiming them.

Game data:
- `GDSRecipeData` (2012 recipes: product ItemId, rarity, Category) and `GDSItemRecipeData` (the recipe book items:
  recipeId, item key `irp_...`, flagNo into GlobalItemGetFlag).
- `GDSLibraryListData` (385 entries; Category 0 monsters, 1 gathering spots, 2 Strangelings, 3 characters) with a
  FlagID resolved through `GDSLibraryFlag.idx`; `GDSLibraryItemData` (875 items with "where to find" hints).
- Gifts: `GDSAOCCommonData` (add-on packs, receiveFlag/newFlag), `GDSLevel5IdStatusRewardData` (LEVEL5 ID bonus
  content), both with contents in `GDSAOCAddItemData`; `GDSPasswordData` (gift codes built into the game).
  Downloaded gift codes have no local table; each one claimed sets one `password_recieve_download_NNN` flag.
  Flag names resolve through `GDSGlobalBitFlag.idx`.

Save side (Unholy's save, 2026-10-12):
- A learned recipe has all three: `m_RecipeStatus.recipeInfoMap[id].bitFlag` = 9 (every learned recipe; the
  rest are 0), GlobalItemGetFlag[flagNo] = 1 and its book item in `invRecipe` (2048 slots, enough for all).
- Library: `GlobalLibraryFlag[idx]` = seen, `GlobalLibraryNewFlag[idx]` = the "new" mark (set together).
- Library items: GlobalItemGetFlag[flagNo] of the item (obtained at least once).
- Gifts: GlobalBitFlag[idx] of the receive flag. aoc_new_NN is set alongside aoc_recieve_NN; re-claiming leaves
  it alone.
UNVERIFIED:
- bitFlag 9 = bits 0 and 3; which bit means what is not known, so unlocking copies the value learned recipes have.
  Check: unlock one recipe, load the save, open the crafting list for that Life.
- Clearing a gift's receive flag makes the game hand it out again (add-on packs and LEVEL5 ID rewards on the next
  load, gift codes when the code is entered again). The downloaded gift codes may also be checked online.
  Check: re-claim one, load the save, open Menu > Gifts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import paths, uiassets
from .savefile import SaveFile, SaveFileError

GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"
DATA_FILE = paths.UI_ASSET_DIR / "collection" / "collection.json"
DATA_PATTERN = (r"^Game/Content/GameData/(Recipe/GDSRecipe(Data|TabData)|Item/GDSItem\w*Data|Item/GDSItemText_Noun|"
                r"Activity/GDSLibrary\w+|Chara/GDSCharaText_Noun|Map/GDSPickParamData|Tamagemono/GDSTamagemonoData|"
                r"AOC/\w+|Delivery/\w+|Level5IdStatus/\w+|System/GDSGlobalBitFlag|Menu/GDSMenuText)\.uasset$")
RECIPE_LEARNED = 9
# Public gift codes and what they give (fantasylife.wiki.gg Gift_Codes, fantasylife.jp, checked 2026-10-12; the same
# list as the Discord bot's #fli-gift-codes). Downloaded codes can't be tied to their flag until one is redeemed.
# AF579XS2's rewards are exactly the built-in code rompass_0001 (Raccoon set), so that one is checked offline.
LEGENDARY = [("imt01004940", 3), ("imt01004950", 3), ("imt01004960", 3), ("imt01004970", 3), ("imt01004980", 3),
             ("imt01004990", 3)]
GIFT_CODES = [
    ("X43H5MV6", "1st Anniversary", "May 2026", [("imt01004800", 200), ("ics01001030", 5), ("ics01001050", 5),
                                                ("ics01000750", 5), ("ics01001170", 5), ("ics01001550", 5)]),
    ("G67W5CLX", "1.5 million copies sold", "January 2026", LEGENDARY + [("imt01004800", 150)]),
    ("M53UA8Y2", "Japan Game Awards", "September 2025", [("ico03010370", 1), ("ico03010980", 1), ("ico03010200", 1),
                                                        ("imt01004800", 100)]),
    ("Q8RD9AME", "Version 1.5.0", "August 2025", [("ics01001650", 3), ("ics01002810", 3), ("ics01003110", 3),
                                                 ("imt01004800", 50)]),
    ("K9E8VADB", "1.2 million copies sold", "July 2025", LEGENDARY),
    ("AF579XS2", "1 million copies sold", "June 2025", [("iam02000070", 1), ("iam02000080", 1), ("iam02000090", 1),
                                                       ("iam02000100", 1)]),
    ("X95SB4UD", "800,000 copies sold", "June 2025", [("ics01000610", 10), ("ics01000690", 10), ("ics01000790", 5)]),
    ("E47LWJGP", "Surprise Dosh gift", "May 2025", [("imt01000520", 5), ("imt01000530", 5)]),
    ("A5C9X7VR", "500,000 copies sold", "May 2025", [("iam01003910", 1), ("iam01003410", 1), ("imt01004640", 1),
                                                    ("ics01000540", 5), ("imt01000530", 10)]),
    ("A56LCE87", "Wishlist campaign", "May 2025", [("ics01000600", 5), ("ics01000680", 5), ("ics01000620", 5),
                                                  ("ics01000700", 5), ("ics01000780", 3)]),
    ("T2GC6EQL", "Launch celebration", "May 2025", [("ics01000580", 5), ("ics01000660", 5), ("ics01000780", 3),
                                                   ("ics01000820", 3), ("ics01000860", 3), ("ics01000620", 3)]),
]
BUILT_IN_CODE = {"AF579XS2": "rompass_0001"}
LIBRARY_CATS = {0: "Monsters", 1: "Gathering spots", 2: "Strangelings", 3: "Characters"}
GIFT_FLAG = re.compile(r"^(password_recieve_\w+|compensation_receive_\d+)$")


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "Activity" / "GDSLibraryListData.json").exists() \
            or not (GAME_DATA / "AOC" / "GDSAOCCommonData.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)


def _rows(rel: str) -> dict:
    props = json.loads((GAME_DATA / rel).read_text(encoding="utf-8"))[0]["Properties"]
    return {(r["Key"]["Name"] if isinstance(r["Key"], dict) else r["Key"]): r["Value"] for r in props["m_dataMap"]}


def _nouns(rel: str) -> dict[str, str]:
    out = {}
    for k, v in _rows(rel).items():
        info = (v.get("textInfo") or [{}])[0]
        if info.get("nounSingularForm_en"):
            out[k] = info["nounSingularForm_en"]
    return out


def _texts(rel: str) -> dict[str, str]:
    out = {}
    for k, v in _rows(rel).items():
        info = (v.get("textInfo") or [{}])[0]
        if info.get("text_en"):
            out[k] = info["text_en"]
    return out


def _contents(rows: list, id_key: str, num_key: str) -> list[dict]:
    return [{"id": r[id_key], "num": r[num_key]} for r in rows if r.get(id_key) not in (None, "None")]


def build(out: Path | None = None, log=print) -> dict:
    out = out or DATA_FILE.parent
    if not (GAME_DATA / "Activity" / "GDSLibraryListData.json").exists():
        log("collection: no exported data; run extract first")
        return {"missing": ["collection data"]}
    item_noun, chara_noun = _nouns("Item/GDSItemText_Noun.json"), _nouns("Chara/GDSCharaText_Noun.json")
    menu = _texts("Menu/GDSMenuText.json")
    flags = {k: v["idx"] for k, v in _rows("System/GDSGlobalBitFlag.json").items()}

    books = {v["recipeId"]: (k, v["flagNo"]) for k, v in _rows("Item/GDSItemRecipeData.json").items()}
    tabs = {v["Category"]: menu.get(v["tabNameId"], str(v["Category"])) for v in _rows("Recipe/GDSRecipeTabData.json").values()}
    recipes = []
    for rid, r in _rows("Recipe/GDSRecipeData.json").items():
        m = re.match(r"recipe_life(\d+)_", rid)
        book, flag = books.get(rid, (None, None))
        recipes.append({"id": rid, "life": f"life{int(m.group(1)):04d}" if m else None, "item": r["ItemId"],
                        "rarity": r.get("rarity", 0), "cat": r.get("Category"), "book": book, "flag": flag})

    lib_idx = {k: v["idx"] for k, v in _rows("Activity/GDSLibraryFlag.json").items()}
    picks, strange = _rows("Map/GDSPickParamData.json"), _rows("Tamagemono/GDSTamagemonoData.json")
    library = []
    for lid, v in _rows("Activity/GDSLibraryListData.json").items():
        obj, cat = v["ObjecyID"], v["Category"]
        if cat == 1:
            name = item_noun.get(picks.get(obj, {}).get("namePlateIconInfo", {}).get("textId"))
        elif cat == 2:
            name = chara_noun.get("name_" + strange.get(obj, {}).get("charaID", ""))
        else:
            name = chara_noun.get("name_" + obj)
        if v["FlagID"] in lib_idx:
            library.append({"id": lid, "cat": cat, "obj": obj, "name": name or obj, "flag": lib_idx[v["FlagID"]]})

    item_flags = {}
    for f in (GAME_DATA / "Item").glob("GDSItem*Data.json"):
        if f.stem == "GDSItemRecipeData":
            continue
        try:
            for k, v in _rows(f"Item/{f.name}").items():
                if isinstance(v, dict) and isinstance(v.get("flagNo"), int):
                    item_flags[k] = v["flagNo"]
        except (KeyError, IndexError, ValueError):
            pass
    lib_items = [{"id": k, "flag": item_flags[k]} for k in _rows("Activity/GDSLibraryItemData.json") if k in item_flags]

    adds = _rows("AOC/GDSAOCAddItemData.json")
    gifts = []
    for gid, v in _rows("AOC/GDSAOCCommonData.json").items():
        gifts.append({"id": gid, "kind": "pack", "name": item_noun.get(v["textId"], gid),
                      "flag": flags.get(v["receiveFlag"]), "newFlag": flags.get(v["newFlag"]),
                      "items": _contents(adds.get(gid, {}).get("addItemInfoList", []), "addItemId", "addItemNum")})
    for gid, v in _rows("Level5IdStatus/GDSLevel5IdStatusRewardData.json").items():
        gifts.append({"id": gid, "kind": "level5", "name": item_noun.get(v["textId"], gid), "rank": v["requiredUnlockRank"],
                      "flag": flags.get(v["recievedBitFlagId"]), "newFlag": flags.get(v["NewFlagID"]),
                      "items": _contents(adds.get(gid, {}).get("addItemInfoList", []), "addItemId", "addItemNum")})
    for gid, v in _rows("Delivery/GDSPasswordData.json").items():
        gifts.append({"id": gid, "kind": "code", "name": "Built-in gift code", "flag": flags.get(v["recievedBitFlagId"]),
                      "items": _contents(v.get("rewardItemInfos", []), "ItemId", "Value")})
    known = {g["flag"] for g in gifts}
    codes = sorted((idx, k) for k, idx in flags.items() if GIFT_FLAG.match(k) and idx not in known)

    data = {"recipes": recipes, "recipeTabs": tabs, "library": library, "libraryCats": LIBRARY_CATS,
            "libraryItems": lib_items, "gifts": gifts, "codeFlags": [{"flag": i, "id": k} for i, k in codes]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "collection.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"collection: {len(recipes)} recipes, {len(library)} library entries, {len(lib_items)} library items, "
        f"{len(gifts)} gifts, {len(codes)} gift-code flags -> {out}")
    return {"recipes": len(recipes), "library": len(library), "gifts": len(gifts)}


class Collection:
    def __init__(self, data: dict):
        self.recipes: dict[str, dict] = {r["id"]: r for r in data["recipes"]}
        self.tabs = {int(k): v for k, v in data["recipeTabs"].items()}
        self.library: dict[str, dict] = {e["id"]: e for e in data["library"]}
        self.cats = {int(k): v for k, v in data["libraryCats"].items()}
        self.lib_items: dict[str, int] = {e["id"]: e["flag"] for e in data["libraryItems"]}
        self.gifts: dict[str, dict] = {g["id"]: g for g in data["gifts"]}
        self.code_flags: dict[int, str] = {c["flag"]: c["id"] for c in data["codeFlags"]}

    @classmethod
    def load(cls, path: Path = DATA_FILE) -> "Collection":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---- save access -----------------------------------------------------------
    @staticmethod
    def _flags(sf: SaveFile) -> dict:
        return sf.sd["m_FlagStatus"]

    @staticmethod
    def _recipe_map(sf: SaveFile) -> dict[str, dict]:
        return {e["key"]: e["value"] for e in sf.sd["m_RecipeStatus"]["recipeInfoMap"]}

    def learned(self, sf: SaveFile) -> set[str]:
        return {k for k, v in self._recipe_map(sf).items() if v["bitFlag"]}

    # ---- views -----------------------------------------------------------------
    def recipe_state(self, sf: SaveFile) -> dict:
        learned = self.learned(sf)
        return {"learned": sorted(learned), "tabs": self.tabs,
                "recipes": [{**r, "learned": r["id"] in learned} for r in self.recipes.values()]}

    def library_state(self, sf: SaveFile) -> dict:
        seen, got = self._flags(sf)["GlobalLibraryFlag"], self._flags(sf)["GlobalItemGetFlag"]
        return {"cats": self.cats,
                "entries": [{**e, "seen": bool(seen[e["flag"]])} for e in self.library.values()],
                "items": [{"id": k, "seen": bool(got[f])} for k, f in self.lib_items.items()]}

    def gift_state(self, sf: SaveFile) -> dict:
        bits = self._flags(sf)["GlobalBitFlag"]
        gifts = [{**g, "claimed": g["flag"] is not None and bool(bits[g["flag"]])} for g in self.gifts.values()]
        codes = [{"flag": i, "id": k} for i, k in sorted(self.code_flags.items()) if bits[i]]
        known = []
        for code, why, when, items in GIFT_CODES:
            g = self.gifts.get(BUILT_IN_CODE.get(code, ""))
            known.append({"code": code, "why": why, "when": when, "items": [{"id": i, "num": n} for i, n in items],
                          "gift": g and g["id"], "claimed": bool(g and bits[g["flag"]]) if g else None})
        return {"gifts": gifts, "codes": codes, "known": known}

    def grant(self, sf: SaveFile, code: str, info: dict[str, dict]) -> int:
        """Put a gift code's rewards straight into the bag (no code entry, no flag). Returns items added."""
        entry = next((c for c in GIFT_CODES if c[0] == code), None)
        if entry is None:
            raise SaveFileError(f"unknown gift code {code}")
        n = 0
        for iid, num in entry[3]:
            meta = info.get(iid)
            if not meta or not meta.get("pocket"):
                raise SaveFileError(f"{iid} has no known bag pocket")
            pocket, cap = meta["pocket"], int(meta.get("stack") or 1)
            have = next((it for it in sf.items(pocket) if it.item_id == iid), None)
            if cap > 1 and have is not None and have.stock is not None:
                sf.set_stock(pocket, have.index, min(have.stock + num, cap))
            elif cap > 1:
                sf.add_item(pocket, iid, min(num, cap))
            else:
                for _ in range(num):
                    sf.add_item(pocket, iid, 1)
            n += num
        sf.dirty = True
        return n

    # ---- edits -----------------------------------------------------------------
    def unlock_recipes(self, sf: SaveFile, ids: list[str]) -> int:
        """Give each recipe the three marks a learned recipe has. Returns how many were newly learned."""
        rmap, get = self._recipe_map(sf), self._flags(sf)["GlobalItemGetFlag"]
        have = {it["ItemId"] for it in sf.inventory["invRecipe"]}
        n = 0
        for rid in ids:
            r = self.recipes.get(rid)
            if r is None or rid not in rmap:
                raise SaveFileError(f"unknown recipe {rid}")
            if rmap[rid]["bitFlag"]:
                continue
            if r["book"] and r["book"] not in have:
                sf.add_item("invRecipe", r["book"], 1)
                have.add(r["book"])
            if r["flag"] is not None:
                get[r["flag"]] = 1
            rmap[rid]["bitFlag"] = RECIPE_LEARNED
            n += 1
        if n:
            sf.dirty = True
        return n

    def unlock_library(self, sf: SaveFile, ids: list[str]) -> int:
        fs = self._flags(sf)
        n = 0
        for lid in ids:
            if lid in self.library:
                i = self.library[lid]["flag"]
                if not fs["GlobalLibraryFlag"][i]:
                    fs["GlobalLibraryFlag"][i] = fs["GlobalLibraryNewFlag"][i] = 1
                    n += 1
            elif lid in self.lib_items:
                i = self.lib_items[lid]
                if not fs["GlobalItemGetFlag"][i]:
                    fs["GlobalItemGetFlag"][i] = 1
                    n += 1
            else:
                raise SaveFileError(f"unknown library entry {lid}")
        if n:
            sf.dirty = True
        return n

    def reclaim(self, sf: SaveFile, ids: list[str] | None = None, codes: list[int] | None = None) -> int:
        """Clear receive flags so the game hands those gifts out again."""
        bits = self._flags(sf)["GlobalBitFlag"]
        n = 0
        for gid in ids or []:
            g = self.gifts.get(gid)
            if g is None or g["flag"] is None:
                raise SaveFileError(f"unknown gift {gid}")
            if bits[g["flag"]]:
                bits[g["flag"]] = 0
                n += 1
        for i in codes or []:
            if int(i) not in self.code_flags:
                raise SaveFileError(f"flag {i} is not a gift-code flag")
            if bits[int(i)]:
                bits[int(i)] = 0
                n += 1
        if n:
            sf.dirty = True
        return n
