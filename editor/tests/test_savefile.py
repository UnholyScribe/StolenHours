import shutil

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, paths, safety, savefile


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    import copy
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def test_known_values(loaded):
    assert loaded.character_name == "N30Killer"
    assert loaded.island_name == "Grimfang"
    assert loaded.money == 14633
    assert len(loaded.lives()) == 15


def test_worn_items_are_armour_of_the_current_life(loaded):
    worn = loaded.worn_items()
    assert worn and all(i.startswith(("iam", "iwp", "itl")) for i in worn.values())
    assert set(worn) <= {"weapon", "shield", "Head", "tops", "bottoms", "arm", "foot", "mantle", "glasses", "Accessory"}


def test_skill_panels_match_miner_board(loaded):
    sp = loaded.skill_panels()
    assert all(401 <= f <= 473 for f in sp["learned"])
    assert len(sp["learned"]) == 11
    assert set(sp["unlocked"]) <= set(range(401, 474))


def test_unedited_pack_is_original(loaded):
    assert loaded.to_bin() == loaded.raw


def test_money_edit_survives_pack(loaded):
    sf = fresh(loaded)
    sf.money = 1_234_567
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)
    assert d["saveData"]["m_PlayData"]["Money"] == 1_234_567


def test_money_bounds(loaded):
    sf = fresh(loaded)
    with pytest.raises(savefile.SaveFileError):
        sf.money = -1
    with pytest.raises(savefile.SaveFileError):
        sf.money = 2**31


def test_add_item_and_stock(loaded):
    sf = fresh(loaded)
    before = len(sf.items("invMaterial"))
    with pytest.raises(savefile.SaveFileError):
        sf.add_item("invMaterial", "imt01001150", 5)
    idx = sf.add_item("invMaterial", "imt99999999", 7)
    sf.set_stock("invMaterial", 0, 999)
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)
    inv = d["saveData"]["m_InventoryStatus"]["invMaterial"]
    assert inv[idx]["ItemId"] == "imt99999999" and inv[idx]["stockNum"] == 7
    assert inv[0]["stockNum"] == 999
    handles = [it["Handle"]["handle"] for it in inv if it["ItemId"] not in savefile.EMPTY_IDS]
    assert len(handles) == len(set(handles)) == before + 1


def test_life_edit(loaded):
    sf = fresh(loaded)
    sf.set_life("life0005", level=20, exp=5000, rank=2)
    l = next(x for x in sf.lives() if x["id"] == "life0005")
    assert (l["level"], l["exp"], l["rank"]) == (20, 5000, 2)
    with pytest.raises(savefile.SaveFileError):
        sf.set_life("life9999", level=1)


def test_appearance_edit(loaded):
    sf = fresh(loaded)
    assert sf.appearance()["HairColorId"] == "color_hair_27"
    sf.set_appearance("HairColorId", "color_hair_05")
    sf.set_appearance("EyeScaleIndex", 3)
    for bad in (("HairColorId", "color_eye_05"), ("HairColorId", "color_hair_5"), ("EyeScaleIndex", 256),
                ("Nope", 1)):
        with pytest.raises(savefile.SaveFileError):
            sf.set_appearance(*bad)
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)
    body = d["saveData"]["m_AvatarStatus"]["playerP"][0]["BodyParam"]
    assert body["HairColorId"] == "color_hair_05" and body["EyeScaleIndex"] == 3


def test_unicode_name(loaded):
    sf = fresh(loaded)
    sf.character_name = "Tøck"
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)
    assert d["saveData"]["m_CharaStatus"]["m_stAvatarP"][0]["m_name"]["content"] == "Tøck"


def _only_play_data_changed(loaded, sf, fields):
    d = savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)
    before, after = loaded.data, d
    assert after["header"] == before["header"]
    for k in before["saveData"]:
        if k != "m_PlayData":
            assert after["saveData"][k] == before["saveData"][k], k
    changed = {k for k, v in before["saveData"]["m_PlayData"].items() if after["saveData"]["m_PlayData"][k] != v}
    assert changed == set(fields)
    return after["saveData"]["m_PlayData"]


def test_island_rename_touches_only_the_name(loaded):
    sf = fresh(loaded)
    sf.island_name = "Stormhaven"
    assert _only_play_data_changed(loaded, sf, {"islandName"})["islandName"] == "Stormhaven"


def test_island_rename_unicode_and_limits(loaded):
    sf = fresh(loaded)
    sf.island_name = "Île Tøck"
    assert _only_play_data_changed(loaded, sf, {"islandName"})["islandName"]["content"] == "Île Tøck"
    for bad in ("", "   ", " Lead", "Trail ", "x" * (savefile.ISLAND_NAME_MAX + 1), "bad\nname"):
        with pytest.raises(savefile.SaveFileError):
            sf.island_name = bad


def test_play_time_touches_only_play_time(loaded):
    sf = fresh(loaded)
    sf.play_time_seconds = 100 * 3600
    assert _only_play_data_changed(loaded, sf, {"playTime"})["playTime"] == 360000


def test_play_time_bounded_by_real_time_since_start(loaded):
    sf = fresh(loaded)
    pd = sf.sd["m_PlayData"]
    assert sf.play_time_max == (pd["saveDateTime"] - pd["startDateTime"]) // 10_000_000
    sf.play_time_seconds = sf.play_time_max
    for bad in (-1, sf.play_time_max + 1):
        with pytest.raises(savefile.SaveFileError):
            sf.play_time_seconds = bad


def test_write_makes_backup(loaded, tmp_path, monkeypatch):
    target = tmp_path / paths.SAVE_FILE_NAME
    shutil.copy2(SAMPLE_SAVE, target)
    monkeypatch.setattr(paths, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(safety, "running_game_processes", lambda: [])
    sf = fresh(loaded)
    sf.money = 42
    res = sf.write(target)
    assert savefile.SaveFile.load(target, sf.key).money == 42
    backup = next((tmp_path / "backups").rglob(paths.SAVE_FILE_NAME))
    assert backup.read_bytes() == SAMPLE_SAVE.read_bytes()
    assert res["sha256"] == safety.sha256_file(target)


def test_write_refuses_stale_load(loaded, tmp_path, monkeypatch):
    target = tmp_path / paths.SAVE_FILE_NAME
    shutil.copy2(SAMPLE_SAVE, target)
    monkeypatch.setattr(paths, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(safety, "running_game_processes", lambda: [])
    sf = savefile.SaveFile.load(target, loaded.key)
    target.write_bytes(container.pack(b"GVAS changed by the game", loaded.key))
    sf.money = 1
    with pytest.raises(savefile.SaveFileError, match="changed on disk"):
        sf.write()
    assert not (tmp_path / "backups").exists()


def test_write_locked_while_game_runs(loaded, tmp_path, monkeypatch):
    monkeypatch.setattr(safety, "running_game_processes", lambda: ["NFL1-Win64-Shipping.exe"])
    sf = fresh(loaded)
    with pytest.raises(safety.SafetyError):
        sf.write(tmp_path / "x.bin")
