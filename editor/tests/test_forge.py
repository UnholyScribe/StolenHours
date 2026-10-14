import copy
import json

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, forge, paths, savefile
from stolenhours.webgui import server

SWORD, ARMOR, POTION, POTION_PLUS = "iwp02000030", "iam01000600", "ics01000580", "ics01000590"


@pytest.fixture(scope="module")
def fg():
    if not forge.DATA_FILE.exists():
        pytest.skip("forge.json not built")
    return forge.Forge.load()


@pytest.fixture(scope="module")
def cat():
    f = paths.UI_ASSET_DIR / "items" / "catalog.json"
    if not f.exists():
        pytest.skip("item catalog not built")
    return {i["id"]: i for i in json.loads(f.read_text(encoding="utf-8"))}


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def reparse(sf):
    return savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]


def real(sd, pocket):
    return [it for it in sd["m_InventoryStatus"][pocket] if it["ItemId"] not in savefile.EMPTY_IDS]


def test_tables(fg):
    assert fg.data["grades"] == {"1": "Ordinary", "2": "Fine", "3": "Notable", "4": "Supreme", "5": "Legendary"}
    assert fg.data["qualities"] == {"0": "Normal", "1": "Good", "2": "Great", "3": "Top"}
    sword = fg.items[SWORD]
    assert sword["grades"] == [1, 2, 3] and sword["stats"] == [["Attack", [180, 210, 250, 1, 1]]]
    assert sword["bonus"][0] == 3 and all(sword["pools"][:3])
    assert set(sword["mats"]) == {"1", "2", "3"}
    assert fg.items[ARMOR]["grades"] == [1, 2, 3, 4, 5]
    assert fg.items[POTION]["plus"] == POTION_PLUS and "grades" not in fg.items[POTION]
    assert fg.skills["es_alchemy_up02"]["desc"] == "+4 Alchemy"


def test_forge_gear_roundtrip(fg, cat, loaded):
    sf = fresh(loaded)
    before, order = len(real(sf.sd, "invWeapon")), sf.inventory["getOrderCount"]
    skills = fg.items[SWORD]["pools"][2][:2]
    assert fg.craft(sf, SWORD, cat, 1, grade=3, bonus=True, skills=skills, quality=3) == \
        {"item": SWORD, "pocket": "invWeapon", "count": 1}
    sd = reparse(sf)
    bag = real(sd, "invWeapon")
    assert len(bag) == before + 1
    new = bag[-1]
    assert new["ItemId"] == SWORD and new["itemTitle"] == 3 and new["Quality"] == 3
    assert new["addEquipStatus"] == [{"Type": 3, "Value": 0}]
    assert new["grantSkillId"] == skills + ["None"]
    assert new["equipped"] == 0 and new["aocId"] == "None" and new["getOrder"] == order + 1
    handles = [it["Handle"]["handle"] for it in bag]
    assert len(set(handles)) == len(handles)
    assert sd["m_FlagStatus"]["GlobalItemGetFlag"][fg.flags[SWORD]] == 1


def test_forge_many_and_no_bonus(fg, cat, loaded):
    sf = fresh(loaded)
    before = len(real(sf.sd, "invArmor"))
    fg.craft(sf, ARMOR, cat, 3, grade=5, bonus=False)
    new = real(reparse(sf), "invArmor")[before:]
    assert [it["itemTitle"] for it in new] == [5, 5, 5] and [it["Quality"] for it in new] == [0, 0, 0]
    assert all(it["addEquipStatus"] == [{"Type": 0, "Value": 0}] and it["grantSkillId"] == ["None"] * 3 for it in new)


def test_forge_plus_potion(fg, cat, loaded):
    sf = fresh(loaded)
    stock = lambda s, i: sum(it.stock for it in s.items("invConsume") if it.item_id == i)  # noqa: E731
    cap = int(cat[POTION_PLUS]["stack"])
    have = next(it for it in sf.items("invConsume") if it.item_id == POTION_PLUS)
    sf.set_stock("invConsume", have.index, cap - 3)
    assert fg.craft(sf, POTION, cat, 5, plus=True)["count"] == 3
    assert stock(sf, POTION_PLUS) == cap
    with pytest.raises(savefile.SaveFileError):
        fg.craft(sf, POTION, cat, 1, plus=True)
    normal = stock(sf, POTION)
    if normal + 2 <= int(cat[POTION]["stack"]):
        fg.craft(sf, POTION, cat, 2)
        assert stock(sf, POTION) == normal + 2
    held = {it.item_id for it in sf.items("invConsume")}
    new = next(e for e in fg.items.values() if e.get("plus") and e["plus"] not in held
               and cat.get(e["plus"], {}).get("pocket") == "invConsume")
    assert fg.craft(sf, new["id"], cat, 4, plus=True) == {"item": new["plus"], "pocket": "invConsume", "count": 4}
    reparse(sf)
    assert stock(sf, new["plus"]) == 4


def test_forge_rejects(fg, cat, loaded):
    sf = fresh(loaded)
    for kw in ({"grade": 5}, {"grade": 1, "skills": ["es_alchemy_up06"]}, {"count": 0}, {"count": 100},
               {"quality": 4}, {"quality": -1}):
        with pytest.raises(savefile.SaveFileError):
            fg.craft(sf, SWORD, cat, **{"count": 1, **kw})
    with pytest.raises(savefile.SaveFileError):
        fg.craft(sf, POTION, cat, 1, grade=2)
    with pytest.raises(savefile.SaveFileError):
        fg.craft(sf, POTION, cat, 1, quality=2)
    with pytest.raises(savefile.SaveFileError):
        fg.craft(sf, "iwp99999999", cat)
    with pytest.raises(savefile.SaveFileError):
        sf.add_item("invConsume", "ics01000600", 1, title=2)


def test_item_details(fg, cat, loaded):
    if not forge.DETAILS_FILE.exists():
        pytest.skip("details.json not built")
    det = json.loads(forge.DETAILS_FILE.read_text(encoding="utf-8"))
    assert det["gear"][SWORD]["stats"] == [["Attack", [180, 210, 250, 1, 1]]]
    assert "Heal +300 HP" in det["effects"][POTION_PLUS]
    assert det["prices"][POTION_PLUS]["sell"][0] == 60 and det["prices"]["ilt02000020"]["sell"][:3] == [550, 920, 1480]
    assert det["skills"]["es_alchemy_up02"]["desc"] == "+4 Alchemy"
    sf = fresh(loaded)
    fg.craft(sf, SWORD, cat, 1, grade=3, bonus=True, skills=fg.items[SWORD]["pools"][2][:1], quality=2)
    be = server.Backend()
    be.sf = sf
    new = be.api_items("invWeapon")[-1]
    assert new["gear"] == {"grade": 3, "quality": 2, "bonus": 3, "skills": fg.items[SWORD]["pools"][2][:1],
                           "equipped": False}
    assert all("gear" not in it for it in be.api_items("invConsume"))


def test_bag_add_doesnt_copy_template_gear_state(loaded):
    """add_item used to clone the last item, so new gear inherited its grade, skills and equipped mark."""
    sf = fresh(loaded)
    inv = sf.inventory["invWeapon"]
    last = max(i for i, it in enumerate(inv) if it["ItemId"] not in savefile.EMPTY_IDS)
    inv[last]["equipped"], inv[last]["grantSkillId"][0] = 1, "es_attack_up02"
    slot = sf.add_item("invWeapon", SWORD, title=2)
    new = inv[slot]
    assert new["equipped"] == 0 and new["grantSkillId"] == ["None"] * 3 and new["itemTitle"] == 2
    reparse(sf)
