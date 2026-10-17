import os
import time

import pytest

from stolenhours import steam

ACCT_A, ACCT_B = "111", "222"


def touch(p, data=b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def make_game(lib, installdir):
    touch(lib / "steamapps" / "common" / installdir / steam.SHIPPING_REL)
    (lib / "steamapps" / f"appmanifest_{steam.APP_ID}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{steam.APP_ID}"\n\t"installdir"\t\t"{installdir}"\n}}\n')


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """Steam on X:\\Weird Steam, the game on Y:\\Lib in a renamed folder, two accounts."""
    x, y = tmp_path / "X", tmp_path / "Y"
    root = x / "Weird Steam"
    touch(root / "steam.exe")
    lib = y / "Lib"
    lib_vdf = lib.as_posix().replace("/", "\\\\")
    touch(root / "steamapps" / "libraryfolders.vdf", (
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"' + str(root).replace("\\", "\\\\") + '"\n\t}\n'
        '\t"1"\n\t{\n\t\t"path"\t\t"' + lib_vdf + '"\n\t\t"apps"\n\t\t{\n\t\t\t"2993780"\t\t"1"\n\t\t}\n\t}\n}\n'
    ).encode())
    make_game(lib, "FLi Renamed")
    sid = lambda a: str(int(a) + steam.STEAMID64_BASE)
    touch(root / "config" / "loginusers.vdf", (
        '"users"\n{\n'
        f'\t"{sid(ACCT_A)}"\n\t{{\n\t\t"PersonaName"\t\t"Alice"\n\t\t"MostRecent"\t\t"0"\n\t}}\n'
        f'\t"{sid(ACCT_B)}"\n\t{{\n\t\t"PersonaName"\t\t"Bob"\n\t\t"MostRecent"\t\t"1"\n\t}}\n}}\n').encode())
    a = touch(root / "userdata" / ACCT_A / steam.APP_ID / "remote" / "002DAE74-00-gamedata.bin")
    time.sleep(0.02)
    touch(root / "userdata" / ACCT_B / steam.APP_ID / "remote" / "002DAE74-00-gamedata.bin")
    os.utime(a, None)  # A has the newest file, B is the most recent login

    monkeypatch.setattr(steam, "_registry_steam_paths", lambda: [root])
    monkeypatch.setattr(steam, "_drives", lambda: [x, y])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    for env in (steam.ENV_STEAM, steam.ENV_GAME, steam.ENV_SAVE):
        monkeypatch.delenv(env, raising=False)
    return {"root": root, "lib": lib, "x": x, "y": y, "tmp": tmp_path}


def test_vdf_parser():
    d = steam.parse_vdf('// c\n"a"\n{\n\t"b"\t\t"C:\\\\x"\n\t"q"\t"say \\"hi\\""\n\t"n" { "k" "v" }\n}\n')
    assert d == {"a": {"b": "C:\\x", "q": 'say "hi"', "n": {"k": "v"}}}


def test_finds_steam_game_and_saves(machine):
    assert steam.find_steam_roots() == [machine["root"].resolve()]
    assert steam.find_game_dirs() == [machine["lib"] / "steamapps" / "common" / "FLi Renamed"]
    saves = steam.find_saves()
    assert [s.account_id for s in saves] == [ACCT_B, ACCT_A]
    assert saves[0].persona == "Bob" and saves[0].most_recent_user
    assert steam.default_save() == saves[0].path


def test_old_libraryfolders_format(machine):
    (machine["root"] / "steamapps" / "libraryfolders.vdf").write_text(
        '"LibraryFolders"\n{\n\t"TimeNextStatsReport"\t\t"1"\n\t"1"\t\t"'
        + str(machine["lib"]).replace("\\", "\\\\") + '"\n}\n')
    assert steam.find_game_dirs() == [machine["lib"] / "steamapps" / "common" / "FLi Renamed"]


def test_no_registry_scans_drives(machine, monkeypatch):
    monkeypatch.setattr(steam, "_registry_steam_paths", lambda: [])
    monkeypatch.setattr(steam, "_COMMON_STEAM", ("Weird Steam",))
    assert steam.find_steam_roots() == [machine["root"].resolve()]


def test_game_found_without_any_steam(machine, monkeypatch):
    monkeypatch.setattr(steam, "_registry_steam_paths", lambda: [])
    monkeypatch.setattr(steam, "_COMMON_STEAM", ())
    monkeypatch.setattr(steam, "_COMMON_LIBS", ("Lib",))
    assert steam.find_game_dirs() == [machine["lib"] / "steamapps" / "common" / "FLi Renamed"]


def test_game_found_without_manifest(machine):
    (machine["lib"] / "steamapps" / f"appmanifest_{steam.APP_ID}.acf").unlink()
    assert steam.find_game_dirs() == [machine["lib"] / "steamapps" / "common" / "FLi Renamed"]


def test_direct_launch_save_is_listed_after_steam(machine):
    touch(machine["tmp"] / "local" / "Game" / "Saved" / "SaveGames" / "slot.bin")
    saves = steam.find_saves()
    assert saves[-1].kind == "direct-launch" and saves[0].kind == "steam"


def test_env_overrides(machine, monkeypatch, tmp_path):
    other = tmp_path / "Z" / "Game Copy"
    touch(other / steam.SHIPPING_REL)
    monkeypatch.setenv(steam.ENV_GAME, str(other))
    monkeypatch.setenv(steam.ENV_SAVE, str(tmp_path / "custom.bin"))
    assert steam.find_game_dirs()[0] == other
    assert steam.default_save() == tmp_path / "custom.bin"


def test_nothing_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(steam, "_registry_steam_paths", lambda: [])
    monkeypatch.setattr(steam, "_drives", lambda: [tmp_path])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    for env in (steam.ENV_STEAM, steam.ENV_GAME, steam.ENV_SAVE):
        monkeypatch.delenv(env, raising=False)
    assert steam.find_steam_roots() == [] and steam.find_game_dirs() == [] and steam.default_save() is None
