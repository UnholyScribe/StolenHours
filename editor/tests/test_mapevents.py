import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, mapevents, savefile

LEGEND_ORE = "qsf_active_event_011_01"  # West Dryridge Desert, needs area rank
FOSSIL = "qsf_active_event_041_01"


@pytest.fixture(scope="module")
def ev():
    if not mapevents.EVENTS_FILE.exists():
        pytest.skip("events.json not built")
    return mapevents.MapEvents.load()


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def reparse(sf):
    return savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]


def test_catalog(ev):
    cats = {}
    for e in ev.events.values():
        cats[e["cat"]] = cats.get(e["cat"], 0) + 1
    assert cats["legendary"] == 13 and cats["special"] == 9 and cats["boss"] == 3 and cats["delivery"] == 78
    assert ev.events[LEGEND_ORE]["title"] == "Hunt for the Legendary Ore"
    assert ev.areas["map200000_area001"] == "West Dryridge Desert"


def test_save_state(ev, loaded):
    st = ev.state(loaded)
    assert st["live"] == [] and st["cleared"] == []
    t = st["time"]
    minutes = int(loaded.sd["m_PhaseInfo"]["envInfo"]["gameTime"])
    assert ((t["day"] - 1) * 1440 + t["hour"] * 60 + t["minute"]) == minutes and t["period"] == 0
    # rank 1 areas: legendary hunts are gated by area rank
    assert any("rank" in u for u in st["unmet"][LEGEND_ORE])


def test_emerge_and_dismiss_roundtrip(ev, loaded):
    sf = fresh(loaded)
    ev.emerge(sf, [LEGEND_ORE, FOSSIL])
    d = reparse(sf)
    q = d["m_QuestStatus"]
    assert {e["key"] for e in q["ActiveEventInfo"]} == {LEGEND_ORE, FOSSIL}
    assert all(e["value"]["timePeriodChangeCount"] == 0 for e in q["ActiveEventInfo"])
    assert next(e for e in q["Active"] if e["key"] == LEGEND_ORE)["value"]["phase"] == 1
    ev.dismiss(sf, [FOSSIL])
    assert ev.live_ids(sf) == [LEGEND_ORE]
    ev.clear(sf)
    assert ev.live_ids(sf) == []
    assert sf.to_bin() and reparse(sf)["m_QuestStatus"]["ActiveEventInfo"] == []


def test_emerge_replaces_same_place(ev, loaded):
    sf = fresh(loaded)
    by_place = {}
    for e in ev.events.values():
        by_place.setdefault(e["place"], []).append(e["id"])
    first, second = next(ids for ids in by_place.values() if len(ids) > 1)[:2]
    ev.emerge(sf, [first])
    assert ev.emerge(sf, [second]) == [first]
    assert ev.live_ids(sf) == [second]


def test_draw_follows_rules(ev, loaded):
    sf = fresh(loaded)
    picked = ev.draw(sf, 10, seed=1)
    assert 0 < len(picked) <= 10
    assert len({ev.events[i]["place"] for i in picked}) == len(picked)
    ctx = ev._ctx(sf)
    assert all(not ev._unmet(sf, ev.events[i], ctx) for i in picked)
    free = ev.draw(sf, 10, rules=False, cats=["legendary", "boss"], seed=2)
    assert sum(ev.events[i]["cat"] == "legendary" for i in free) <= 1
    assert all(ev.events[i]["cat"] in ("legendary", "boss") for i in free)
    assert sorted(ev.live_ids(sf)) == sorted(free)


def test_time_and_weather(ev, loaded):
    sf = fresh(loaded)
    ev.set_time(sf, 22, 30, period=1)
    ev.set_weather(sf, 2)
    d = reparse(sf)
    env = d["m_PhaseInfo"]["envInfo"]
    assert env["gameTime"] == 1440 + 22 * 60 + 30 and env["gameTimePeriodType"] == 1
    assert {w["weatherType"] for w in d["m_WeatherStatus"]["WeatherInfo"]} == {2}
    with pytest.raises(savefile.SaveFileError):
        ev.set_time(sf, 24, 0)
