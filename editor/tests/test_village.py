import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, savefile, village

MAP_BASE = village.MAP_BASE
MAP_MYHOUSE = village.MAP_MYHOUSE


@pytest.fixture(scope="module")
def vil():
    if not village.DATA_FILE.exists():
        pytest.skip("village craft.json not built")
    return village.Village.load()


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def reparse(sf):
    return savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]


def test_catalog(vil):
    assert len(vil.objects) >= 500
    assert "obj_ico01040010" in vil.objects or any(o.startswith("obj_ico") for o in vil.objects)
    assert any(h.get("forceMap") == MAP_MYHOUSE for h in vil.houses.values()) or vil.houses


def test_grid_roundtrip_outdoor(vil, loaded):
    sf = fresh(loaded)
    _, area = vil.find_area(sf, MAP_BASE, "map")
    origin = vil.area_origin(area, sf)
    # known house shell on Unholy's save
    for o in sf.sd["m_CraftStatus"]["craftObjStatusPArray"]:
        if o.get("craftObjId") == "obj_icf01020030":
            ix, iy, iz, g = vil.loc_to_grid(o["Location"], area, origin)
            assert g == o["gridIdx"]
            assert vil.grid_to_loc(ix, iy, iz, area, origin) == list(o["Location"])
            break
    else:
        pytest.skip("no player house shell on sample save")


def test_state_base_and_myhouse(vil, loaded):
    sf = fresh(loaded)
    base = vil.state(sf, MAP_BASE, "map")
    assert base["area"]["width"] >= 16
    assert base["area"]["numericMapId"] != 0
    assert isinstance(base["placed"], list)
    house = vil.state(sf, MAP_MYHOUSE, "indoor")
    assert house["area"]["mapId"] == MAP_MYHOUSE
    assert house["area"]["numericMapId"] != 0


def test_place_move_remove_free_roundtrip(vil, loaded):
    sf = fresh(loaded)
    # pick a furniture id from catalog that exists as data
    cand = next((o for o in vil.objects.values() if o["category"] == "OBJECT" and o.get("itemId")), None)
    if not cand:
        pytest.skip("no furniture in catalog")
    st = vil.state(sf, MAP_BASE, "map")
    ox, oy, oz = st["area"]["origin"]
    vw = st["area"]["voxel"][0]
    # place near map center cells that already have content
    loc = [ox + 80 * vw, oy + 64 * vw, oz + vw * 0]  # may be wrong z; use layer 1 like furniture
    # use same z as an existing outdoor furniture if any
    furn = [p for p in st["placed"] if p["category"] == "OBJECT"]
    if furn:
        loc[2] = furn[0]["location"][2]
        loc[0] = furn[0]["location"][0] + vw * 4
        loc[1] = furn[0]["location"][1]
    before = len(st["placed"])
    placed = vil.place(sf, cand["id"], MAP_BASE, loc, free=True, kind="map")
    assert placed["handle"]
    assert sf.dirty
    st2 = vil.state(sf, MAP_BASE, "map")
    assert len(st2["placed"]) == before + 1
    moved = vil.move(sf, placed["handle"], [loc[0] + vw, loc[1], loc[2]])
    assert moved["location"][0] == pytest.approx(loc[0] + vw)
    vil.rotate90(sf, placed["handle"])
    vil.remove(sf, placed["handle"], free=True)
    st3 = vil.state(sf, MAP_BASE, "map")
    assert len(st3["placed"]) == before
    sd = reparse(sf)
    assert all(
        (o.get("Handle") or {}).get("handle") != placed["handle"]
        or o.get("craftObjId") in savefile.EMPTY_IDS
        for o in sd["m_CraftStatus"]["craftObjStatusPArray"]
    )


def test_place_indoor_free(vil, loaded):
    sf = fresh(loaded)
    cand = next((o for o in vil.objects.values()
                 if o["id"] == "obj_ico01020030" or (o["category"] == "OBJECT" and o.get("action") == "Chair")), None)
    if not cand:
        pytest.skip("no chair craft object")
    st = vil.state(sf, MAP_MYHOUSE, "indoor")
    ox, oy, oz = st["area"]["origin"]
    loc = [ox + 100, oy + 100, oz]
    before = len(st["placed"])
    placed = vil.place(sf, cand["id"], MAP_MYHOUSE, loc, free=True, kind="indoor")
    assert placed["mapIdNum"] == st["area"]["numericMapId"]
    st2 = vil.state(sf, MAP_MYHOUSE, "indoor")
    assert len(st2["placed"]) == before + 1
    vil.remove(sf, placed["handle"], free=True)
    assert len(vil.state(sf, MAP_MYHOUSE, "indoor")["placed"]) == before
