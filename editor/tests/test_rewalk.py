import json

import pytest

from stolenhours import container, rewalk, steam


@pytest.fixture
def fp_machine(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    root.mkdir(parents=True)
    (root / "steam.exe").write_bytes(b"x")
    lib = tmp_path / "Lib"
    game = lib / "steamapps" / "common" / "FLi"
    exe = game / steam.SHIPPING_REL
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"dummy")
    (lib / "steamapps").mkdir(parents=True, exist_ok=True)
    (lib / "steamapps" / f"appmanifest_{steam.APP_ID}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{steam.APP_ID}"\n\t"installdir"\t\t"FLi"\n'
        f'\t"buildid"\t\t"111"\n\t"name"\t\t"FANTASY LIFE i"\n}}\n', encoding="utf-8")
    monkeypatch.setattr(steam, "find_game_dirs", lambda: [game])
    monkeypatch.setattr(steam, "find_steam_roots", lambda: [root])
    monkeypatch.setattr(rewalk, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(rewalk, "FINGERPRINT_FILE", tmp_path / "cache" / "fingerprint.json")
    monkeypatch.setattr(rewalk, "PAK_CACHE", tmp_path / "cache" / "pak_key.hex")
    monkeypatch.setattr(rewalk, "MAP_CACHE", tmp_path / "cache" / "mappings.usmap")
    monkeypatch.setattr(rewalk, "STATE_FILE", tmp_path / "cache" / "rewalk_state.json")
    return {"game": game, "exe": exe, "lib": lib}


def test_fingerprint_buildid(fp_machine):
    fp = rewalk.fingerprint(fp_machine["game"])
    assert fp["ok"] and fp["buildid"] == "111" and fp["exe_size"] == 5


def test_game_changed_and_save(fp_machine):
    assert rewalk.game_changed()
    fp = rewalk.fingerprint()
    rewalk.save_fingerprint(fp)
    assert not rewalk.game_changed()
    # simulate Steam update
    (fp_machine["lib"] / "steamapps" / f"appmanifest_{steam.APP_ID}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{steam.APP_ID}"\n\t"installdir"\t\t"FLi"\n'
        f'\t"buildid"\t\t"222"\n}}\n', encoding="utf-8")
    assert rewalk.game_changed()


def test_resolve_key_falls_through_stale_file(tmp_path, monkeypatch, key, sample_raw):
    """A wrong project key file must not block scanning the real game after an update."""
    bad = tmp_path / "aes_key.hex"
    bad.write_text("00" * 32, encoding="ascii")
    monkeypatch.setattr(container.paths, "KEY_FILE", bad)
    container._found_key = None
    # With sample_raw and a real game install (or key from fixture path), resolve must still work
    # if the game key scan finds nothing this skips — use the known good key as game result.
    monkeypatch.setattr(container.steam, "find_game_dirs", lambda: [tmp_path / "nogame"])
    monkeypatch.setattr(container, "key_from_game", lambda exe, raw: key)
    got = container.resolve_key(sample_raw)
    assert got == key


def test_fetch_fli_fmodel_writes_cache(fp_machine, monkeypatch):
    index = {
        "2.2.0": {
            "LATEST": True,
            "Url": "https://example.test/map.usmap",
            "FileName": "FLi-2.2.0.usmap",
            "MainKey": "0x" + "AB" * 32,
        }
    }

    class Resp:
        def __init__(self, data):
            self._data = data if isinstance(data, bytes) else data.encode()

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(url, timeout=20.0):
        if url.rstrip("/").endswith("FLi-FModel"):
            return Resp(json.dumps(index))
        return Resp(b"USMAP" + b"\0" * 100)

    monkeypatch.setattr(rewalk.urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(rewalk, "FLI_FMODEL_INDEX", "https://example.test/FLi-FModel/")
    out = rewalk.fetch_fli_fmodel()
    assert out["ok"] and out["version"] == "2.2.0"
    assert rewalk.PAK_CACHE.read_text(encoding="ascii").strip() == "AB" * 32
    assert rewalk.MAP_CACHE.read_bytes().startswith(b"USMAP")
