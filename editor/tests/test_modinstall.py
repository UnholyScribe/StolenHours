import pytest

from stolenhours import modinstall, safety


@pytest.fixture
def game(tmp_path, monkeypatch):
    g = tmp_path / "FANTASY LIFE i"
    mods = g / "Game" / "Binaries" / "Win64" / "ue4ss" / "Mods"
    mods.mkdir(parents=True)
    (mods.parent / "UE4SS.dll").write_bytes(b"dll")
    (mods / "mods.txt").write_text("BPModLoaderMod : 1\n\n; Built-in keybinds, do not move up!\nKeybinds : 1\n",
                                   encoding="utf-8")
    monkeypatch.setattr(modinstall, "MOD_BACKUPS", tmp_path / "mod_backups")
    monkeypatch.setattr(safety, "running_game_processes", lambda: [])
    return g


def _mods(game):
    return game / "Game" / "Binaries" / "Win64" / "ue4ss" / "Mods"


def test_no_ue4ss_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(safety, "running_game_processes", lambda: [])
    st = modinstall.status(tmp_path)
    assert st["ue4ss"] is False and st["installed"] is None
    with pytest.raises(safety.SafetyError, match="UE4SS"):
        modinstall.install(tmp_path)


def test_fresh_install_enables_before_keybinds(game):
    assert modinstall.status(game)["installed"] is None
    r = modinstall.install(game)
    assert r["current"] and r["enabled"] and r["installed"] == r["bundled"]
    text = (_mods(game) / "mods.txt").read_text(encoding="utf-8")
    assert text.index("StolenHours : 1") < text.index("Keybinds : 1")
    assert r["backup"] and (modinstall.MOD_BACKUPS.iterdir().__next__() / "SHA256.txt").exists()


def test_update_backs_up_old_mod_and_reenables(game):
    old = _mods(game) / "StolenHours" / "Scripts" / "main.lua"
    old.parent.mkdir(parents=True)
    old.write_text('local VERSION = "0.3.0"\n', encoding="utf-8")
    txt = _mods(game) / "mods.txt"
    txt.write_text(txt.read_text(encoding="utf-8").replace("; Built", "StolenHours : 0\n; Built"), encoding="utf-8")
    st = modinstall.status(game)
    assert st["installed"] == "0.3.0" and not st["enabled"] and not st["current"]
    r = modinstall.install(game)
    assert r["current"] and r["installed"] != "0.3.0"
    saved = next(modinstall.MOD_BACKUPS.iterdir())
    assert "0.3.0" in saved.name
    assert (saved / "StolenHours" / "Scripts" / "main.lua").read_text(encoding="utf-8") == 'local VERSION = "0.3.0"\n'
    assert txt.read_text(encoding="utf-8").count("StolenHours :") == 1


def test_refuses_while_game_runs(game, monkeypatch):
    monkeypatch.setattr(safety, "running_game_processes", lambda: ["NFL1-Win64-Shipping.exe"])
    with pytest.raises(safety.SafetyError):
        modinstall.install(game)
    assert not (_mods(game) / "StolenHours").exists()
