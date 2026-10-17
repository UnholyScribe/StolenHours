import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import collection, container, savefile

COOK = "life0009"


@pytest.fixture(scope="module")
def col():
    if not collection.DATA_FILE.exists():
        pytest.skip("collection.json not built")
    return collection.Collection.load()


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def reparse(sf):
    return savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]


def test_catalog(col):
    assert len(col.recipes) == 2012 and len(col.library) == 385
    assert {r["life"] for r in col.recipes.values()} == {f"life{n:04d}" for n in range(9, 15)}
    assert sum(1 for r in col.recipes.values() if not r["book"]) == 1
    names = {e["name"] for e in col.library.values()}
    assert {"Hearhare", "Laura", "Oak Tree"} <= names
    assert col.gifts["aoc_02"]["name"] == "Deluxe Edition" and col.gifts["aoc_02"]["flag"] == 7501
    assert col.gifts["economy"]["kind"] == "level5"
    assert 7700 in col.code_flags and 7998 in col.code_flags and 7501 not in col.code_flags


def test_save_matches_learned_marks(col, loaded):
    """Every learned recipe in the sample save carries bitFlag 9, the book's get flag and the book in the bag."""
    fs, books = loaded.sd["m_FlagStatus"]["GlobalItemGetFlag"], {it["ItemId"] for it in loaded.inventory["invRecipe"]}
    learned = col.learned(loaded)
    assert learned
    for rid in learned:
        r = col.recipes[rid]
        assert col._recipe_map(loaded)[rid]["bitFlag"] == collection.RECIPE_LEARNED
        assert fs[r["flag"]] == 1 and r["book"] in books


def test_unlock_recipes_roundtrip(col, loaded):
    sf = fresh(loaded)
    locked = [r["id"] for r in col.recipes.values() if r["life"] == COOK and r["id"] not in col.learned(sf)]
    before = len([it for it in sf.inventory["invRecipe"] if it["ItemId"] not in savefile.EMPTY_IDS])
    assert col.unlock_recipes(sf, locked) == len(locked) and sf.dirty
    assert col.unlock_recipes(sf, locked) == 0
    sd = reparse(sf)
    bag = [it for it in sd["m_InventoryStatus"]["invRecipe"] if it["ItemId"] not in savefile.EMPTY_IDS]
    assert len(bag) == before + sum(1 for r in locked if col.recipes[r]["book"])
    handles = [it["Handle"]["handle"] for it in bag]
    assert len(set(handles)) == len(handles)
    for i, it in enumerate(sd["m_InventoryStatus"]["invRecipe"][:len(bag)]):
        assert it["Handle"]["handle"] == ((i + 1) * 4 << 16) | (0x8000 + i)
    rmap = {e["key"]: e["value"]["bitFlag"] for e in sd["m_RecipeStatus"]["recipeInfoMap"]}
    assert all(rmap[r] == 9 for r in locked)


def _catalog():
    import json
    from stolenhours import paths
    f = paths.UI_ASSET_DIR / "items" / "catalog.json"
    if not f.exists():
        pytest.skip("item catalog not built")
    return {i["id"]: i for i in json.loads(f.read_text(encoding="utf-8"))}


def test_gift_code_items_exist(col):
    cat = _catalog()
    for code, _, _, items in collection.GIFT_CODES:
        for iid, _ in items:
            assert cat.get(iid, {}).get("pocket"), (code, iid)
    raccoon = {i["id"] for i in col.gifts["rompass_0001"]["items"]}
    assert raccoon == {i for i, _ in next(c for c in collection.GIFT_CODES if c[0] == "AF579XS2")[3]}


def test_grant_code_roundtrip(col, loaded):
    cat, sf = _catalog(), fresh(loaded)
    potions = lambda s: sum(it.stock for it in s.items("invConsume") if it.item_id == "ics01000580")  # noqa: E731
    before = potions(sf)
    assert col.grant(sf, "T2GC6EQL", cat) == 22 and sf.dirty
    assert potions(sf) == before + 5
    col.grant(sf, "AF579XS2", cat)
    sd = reparse(sf)
    armor = [it["ItemId"] for it in sd["m_InventoryStatus"]["invArmor"]]
    assert "iam02000100" in armor
    with pytest.raises(savefile.SaveFileError):
        col.grant(sf, "NOPE1234", cat)


def test_unlock_library_and_reclaim(col, loaded):
    sf = fresh(loaded)
    lid = next(k for k, e in col.library.items() if not sf.sd["m_FlagStatus"]["GlobalLibraryFlag"][e["flag"]])
    assert col.unlock_library(sf, [lid]) == 1
    i = col.library[lid]["flag"]
    bits = sf.sd["m_FlagStatus"]["GlobalBitFlag"]
    bits[7501] = 1
    bits[7705] = 1
    assert col.reclaim(sf, ["aoc_02"], [7705]) == 2
    sd = reparse(sf)
    assert sd["m_FlagStatus"]["GlobalLibraryFlag"][i] == 1 and sd["m_FlagStatus"]["GlobalLibraryNewFlag"][i] == 1
    assert sd["m_FlagStatus"]["GlobalBitFlag"][7501] == 0 and sd["m_FlagStatus"]["GlobalBitFlag"][7705] == 0
    with pytest.raises(savefile.SaveFileError):
        col.reclaim(sf, codes=[7501])
