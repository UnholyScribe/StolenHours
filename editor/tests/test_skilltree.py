import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, savefile, skilltree

MINER = "life0005"


@pytest.fixture(scope="module")
def tree():
    if not skilltree.BOARDS_FILE.exists():
        pytest.skip("boards.json not built")
    return skilltree.SkillTree.load()


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def panel(state, no):
    return next(p for p in state["panels"] if p["no"] == no)


def test_level_table_matches_save(tree, loaded):
    lives = {l["id"]: l for l in loaded.lives()}
    for life in ("life0000", MINER):
        assert tree.sp_for_level(lives[life]["level"]) == lives[life]["skillMaxPoint"]


def test_miner_state(tree, loaded):
    st = tree.state(loaded, MINER)
    assert st["learned"] == 11 and st["sp"] == {"earned": 51, "spent": 51, "free": 0}
    assert st["total"] == 64  # the game shows "11/64"
    assert panel(st, 0)["status"] == "root"
    assert panel(st, 1)["status"] == "learned"
    # parent (36) learned, needs 20 panels
    assert panel(st, 37)["status"] == "locked"
    # parent learned, needs 10 panels: unlocked on the save
    assert panel(st, 38)["status"] == "available" and panel(st, 38)["unlocked"]


def test_unlock_rule_reproduces_save(tree, loaded):
    sf = fresh(loaded)
    _, unlock = tree._flags(sf)
    before = [i for i, v in enumerate(unlock) if v]
    for i in before:
        unlock[i] = 0
    tree._refresh_unlocks(sf)
    assert [i for i, v in enumerate(unlock) if v] == before


def test_learn_needs_sp(tree, loaded):
    sf = fresh(loaded)
    with pytest.raises(savefile.SaveFileError, match="SP"):
        tree.learn(sf, MINER, 38)


def test_learn_and_remove_roundtrip(tree, loaded):
    sf = fresh(loaded)
    tree.set_level_sp(sf, MINER, 13, 20)
    st = tree.state(sf, MINER)
    assert st["sp"]["earned"] == tree.sp_for_level(20)
    assert tree.learn(sf, MINER, 38) == [439]
    assert tree.state(sf, MINER)["learned"] == 12
    with pytest.raises(savefile.SaveFileError, match="next to it"):
        tree.learn(sf, MINER, 41)
    # forgetting 36 drops 36 (437), 38 (439) and 37 is not learned
    assert sorted(tree.remove(sf, MINER, 36)) == [437, 439]
    assert tree.state(sf, MINER)["learned"] == 10
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)
    flags = d["saveData"]["m_FlagStatus"]["skillPanelBitFlag"]
    assert flags[437] == 0 and flags[436] == 1


def test_free_learn_raises_max_sp(tree, loaded):
    sf = fresh(loaded)
    tree.learn(sf, MINER, 41, free=True)
    st = tree.state(sf, MINER)
    assert panel(st, 41)["status"] == "learned" and panel(st, 39)["status"] == "learned"
    assert st["sp"]["free"] == 0 and st["sp"]["earned"] > 51


def test_blank_panels_pass_through(tree, loaded):
    sf = fresh(loaded)
    flags = tree.learn(sf, MINER, 22, free=True)  # 22 hangs off blank 21
    assert 422 not in flags and 423 in flags
    st = tree.state(sf, MINER)
    assert panel(st, 21)["status"] == "blank" and panel(st, 22)["status"] == "learned"
    assert 423 in tree.remove(sf, MINER, 19)


def test_learn_all_and_reset(tree, loaded):
    sf = fresh(loaded)
    tree.learn_all(sf, MINER)
    st = tree.state(sf, MINER)
    assert st["learned"] == st["total"]
    tree.reset(sf, MINER)
    assert tree.state(sf, MINER)["learned"] == 0
