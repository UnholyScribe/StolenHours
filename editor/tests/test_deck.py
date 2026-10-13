"""Steam Deck / Proton: the editor in its own Wine prefix finds Steam, the game and the save through drive Z:."""

import os

import pytest

from stolenhours import deck, paths, safety, steam
from test_steam import make_game, touch

ACCT = "333"


@pytest.fixture
def deck_fs(tmp_path, monkeypatch):
    """A Deck as Wine shows it: Z:\\home\\deck\\.local\\share\\Steam, the game on the SD card."""
    if os.name != "nt":
        pytest.skip("the Z: mapping only exists for Windows programs")
    z = tmp_path / "Z"
    root = z / "home" / "deck" / ".local" / "share" / "Steam"
    sd = z / "run" / "media" / "mmcblk0p1"
    touch(root / "steamapps" / "libraryfolders.vdf", (
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"/home/deck/.local/share/Steam"\n\t}\n'
        '\t"1"\n\t{\n\t\t"path"\t\t"/run/media/mmcblk0p1"\n\t}\n}\n').encode())
    make_game(sd, "FANTASY LIFE i")
    touch(root / "userdata" / ACCT / steam.APP_ID / "remote" / "002DAE74-00-gamedata.bin")
    (z / "home" / "deck" / ".steam").mkdir()  # the usual symlink folder; must not add a second root

    monkeypatch.setattr(deck, "ROOT", str(z))
    monkeypatch.setattr(deck, "under_wine", lambda: True)
    monkeypatch.setattr(steam, "_registry_steam_paths", lambda: [])
    monkeypatch.setattr(steam, "_drives", lambda: [])
    monkeypatch.setenv("HOME", "/home/deck")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "pfx-local"))
    for env in (steam.ENV_STEAM, steam.ENV_GAME, steam.ENV_SAVE):
        monkeypatch.delenv(env, raising=False)
    return {"z": z, "root": root, "sd": sd}


def test_host_path(deck_fs):
    assert deck.host_path("/run/media/mmcblk0p1") == deck_fs["sd"]
    assert deck.host_path("D:\\SteamLibrary") == deck.Path("D:\\SteamLibrary")


def test_finds_steam_game_and_save_on_deck(deck_fs):
    assert steam.find_steam_roots() == [deck_fs["root"].resolve()]
    assert steam.find_game_dirs() == [deck_fs["sd"] / "steamapps" / "common" / "FANTASY LIFE i"]
    saves = steam.find_saves()
    assert [(s.kind, s.account_id) for s in saves] == [("steam", ACCT)]


def test_flatpak_steam(deck_fs):
    flat = deck_fs["z"] / "home" / "deck" / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam"
    (flat / "steamapps").mkdir(parents=True)
    (flat / "userdata").mkdir()
    assert [r.resolve() for r in deck.linux_steam_roots()] == [deck_fs["root"].resolve(), flat.resolve()]


def test_not_wine_adds_nothing(deck_fs, monkeypatch):
    monkeypatch.setattr(deck, "under_wine", lambda: False)
    assert deck.linux_steam_roots() == [] and not deck.on_linux_host()


def test_game_running_seen_through_proc(deck_fs, monkeypatch):
    proc = deck_fs["z"] / "proc"
    touch(proc / "101" / "cmdline", b"Z:\\home\\deck\\SD\\FANTASY LIFE i\\Game\\Binaries\\Win64\\NFL1-Win64-Shipping.exe\0-x\0")
    touch(proc / "101" / "comm", b"NFL1-Win64-Ship\n")
    touch(proc / "202" / "cmdline", b"/usr/bin/bash\0")
    touch(proc / "202" / "comm", b"bash\n")
    touch(proc / "self" / "cmdline", b"NFL1.exe\0")  # not a pid folder
    assert deck.running_on_host(paths.GAME_PROCESS_NAMES) == ["NFL1-Win64-Shipping.exe"]
    # only the 15-character name the kernel keeps (cmdline unreadable or rewritten)
    (proc / "101" / "cmdline").write_bytes(b"wine64-preloader\0")
    assert deck.running_on_host(paths.GAME_PROCESS_NAMES) == ["NFL1-Win64-Shipping.exe"]
    (proc / "101" / "comm").write_bytes(b"winedevice.exe\n")
    assert deck.running_on_host(paths.GAME_PROCESS_NAMES) == []


def test_save_lock_sees_game_in_other_prefix(deck_fs, monkeypatch):
    touch(deck_fs["z"] / "proc" / "77" / "cmdline", b"Z:\\x\\NFL1-Win64-Shipping.exe\0")
    assert "NFL1-Win64-Shipping.exe" in safety.running_game_processes()
    with pytest.raises(safety.SafetyError):
        safety.require_game_closed()
