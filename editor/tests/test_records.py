import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, records, savefile


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def test_records_read_save(loaded, tmp_path):
    r = records.records(loaded, tmp_path / "h.jsonl")
    rows = {row["key"]: row for g in r["groups"] for row in g["rows"]}
    assert rows["m_PlayData.playCountData.pickOreNum"]["value"] == 37
    assert rows["m_PlayData.playCountData.pickOreNum"]["editable"]
    summary = {row["key"]: row["value"] for row in r["summary"]}
    assert summary["playTime"] == loaded.play_time_seconds and summary["Money"] == loaded.money
    assert summary["itemsObtained"] > 0 and r["started"]


def test_history_tracks_changes(loaded, tmp_path):
    hist = tmp_path / "h.jsonl"
    sf = fresh(loaded)
    assert records.record(sf, hist) and not records.record(sf, hist)
    records.set_record(sf, "m_PlayData.playCountData.pickOreNum", 50)
    assert records.record(sf, hist)
    r = records.records(sf, hist)
    ore = next(row for g in r["groups"] for row in g["rows"] if row["key"].endswith("pickOreNum"))
    assert ore["sinceFirst"] == 13 and r["tracking"]["snapshots"] == 2


def test_set_record_roundtrip_and_limits(loaded):
    sf = fresh(loaded)
    records.set_record(sf, "m_PlayData.playCountData.defeatEnemyNum", 1234)
    records.set_record(sf, "m_PlayData.ArenaRank", 3)
    with pytest.raises(savefile.SaveFileError):
        records.set_record(sf, "m_PlayData.ArenaRank", 256)
    with pytest.raises(savefile.SaveFileError):
        records.set_record(sf, "m_PlayData.Money", 5)
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]
    assert d["m_PlayData"]["playCountData"]["defeatEnemyNum"] == 1234 and d["m_PlayData"]["ArenaRank"] == 3
