import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, island, savefile

CLEARED = island.CLEARED


@pytest.fixture(scope="module")
def isl():
    if not island.DATA_FILE.exists():
        pytest.skip("island.json not built")
    return island.Island.load()


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def reparse(sf):
    return savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]


def test_catalog(isl):
    assert len(isl.obstacles) >= 40
    assert any(o["map"] == "Map_000100" for o in isl.obstacles.values())
    assert any(o["map"] == "Map_000202" for o in isl.obstacles.values())
    assert "obstacle_Map_000100_myhouse" in isl.obstacles


def test_state_and_clear_roundtrip(isl, loaded):
    sf = fresh(loaded)
    st = isl.state(sf)
    assert "terrain" in st and st["remaining"] >= 0
    left = [o["id"] for o in st["obstacles"] if not o["cleared"] and o["map"] == "Map_000100"]
    assert left
    target = left[0]
    craft = isl.obstacles[target].get("craft")
    before_release = sf.sd["m_PlayData"]["playCountData"]["obstacleReleaseNum"]
    assert isl.clear_obstacles(sf, [target]) == 1 and sf.dirty
    assert sf.sd["m_FlagStatus"]["GlobalSyncByteFlag"][isl.obstacles[target]["idx"]] == CLEARED
    if craft:
        assert all(o.get("craftObjId") != craft for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"])
    assert sf.sd["m_PlayData"]["playCountData"]["obstacleReleaseNum"] == before_release + 1
    assert isl.clear_obstacles(sf, [target]) == 0
    sd = reparse(sf)
    assert sd["m_FlagStatus"]["GlobalSyncByteFlag"][isl.obstacles[target]["idx"]] == CLEARED


def test_reset_shave(isl, loaded):
    sf = fresh(loaded)
    n = isl.terrain_summary(sf)["shaved"]
    if n == 0:
        # force one shave bit so the reset path is covered on a pristine sample
        for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]:
            if o.get("craftObjId") == "land_obj":
                o["objStatusBitFlag"] = island.SHAVE
                break
        n = 1
    assert isl.reset_shave(sf) >= 1 and sf.dirty
    assert isl.terrain_summary(sf)["shaved"] == 0
    sd = reparse(sf)
    assert all(not (o.get("objStatusBitFlag") or 0) & island.SHAVE
               for o in sd["m_CraftStatus"]["craftObjStatusPArray"])
