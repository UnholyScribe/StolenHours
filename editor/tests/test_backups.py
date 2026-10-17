import shutil

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import container, paths, safety, savefile


@pytest.fixture
def save(key, sample_raw, tmp_path, monkeypatch):
    target = tmp_path / "game" / paths.SAVE_FILE_NAME
    target.parent.mkdir()
    shutil.copy2(SAMPLE_SAVE, target)
    monkeypatch.setattr(paths, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(safety, "running_game_processes", lambda: [])
    return target


def test_copy_to_chosen_place_is_exact(save, tmp_path):
    dest = tmp_path / "usb" / "my copy.bin"
    digest = safety.copy_verified(save, dest)
    assert dest.read_bytes() == save.read_bytes()
    assert digest == safety.sha256_file(save)
    assert not list(dest.parent.glob("*.tmp"))


def test_copy_refuses_the_save_itself(save):
    with pytest.raises(safety.SafetyError):
        safety.copy_verified(save, save)


def test_backups_listed_newest_first_and_checked(save):
    safety.backup(save, "manual")
    second = safety.backup(save, "manual")
    assert second.parent.name.endswith("manual-2")
    second.write_bytes(b"damaged")
    rows = safety.list_backups()
    assert [r["reason"] for r in rows] == ["manual 2", "manual"]
    assert [r["intact"] for r in rows] == [False, True]


def test_restore_puts_copy_back_and_backs_up_current(save, tmp_path, key):
    old = tmp_path / "old.bin"
    shutil.copy2(save, old)
    sf = savefile.SaveFile.load(save, key)
    sf.money = 42
    sf.write()
    assert savefile.SaveFile.load(save, key).money == 42
    res = savefile.restore_save(old, save)
    assert save.read_bytes() == old.read_bytes()
    assert savefile.SaveFile.load(save, key).money == 14633
    assert savefile.SaveFile.load(res["backup"], key).money == 42


def test_restore_refuses_damaged_copy_without_touching_save(save, tmp_path, key):
    bad = tmp_path / "bad.bin"
    raw = bytearray(save.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    bad.write_bytes(bytes(raw))
    before = save.read_bytes()
    with pytest.raises((savefile.SaveFileError, container.ContainerError, ValueError)):
        savefile.restore_save(bad, save)
    assert save.read_bytes() == before
    assert not (tmp_path / "backups").exists()


def test_restore_locked_while_game_runs(save, tmp_path, monkeypatch):
    old = tmp_path / "old.bin"
    shutil.copy2(save, old)
    monkeypatch.setattr(safety, "running_game_processes", lambda: ["NFL1-Win64-Shipping.exe"])
    with pytest.raises(safety.SafetyError):
        savefile.restore_save(old, save)


def test_describe_identifies_the_adventure(save, key):
    info = savefile.SaveFile.load(save, key).describe()
    assert info["name"] == "N30Killer" and info["island"] == "Grimfang"
    assert info["sha256"] == safety.sha256_file(save)
    assert "Grimfang" in info["adventure"]
