"""Re-find the game after a Steam update: paths, save key, pak key, usmap.

Steam can move libraries, bump `buildid`, and change the shipping binary. The editor fingerprints the install
(`appmanifest` buildid + shipping exe size/mtime), and when that changes (or Unholy hits Rewalk) it:

1. Re-discovers Steam roots, game folders and saves (same walk as `steam.py`).
2. Clears any cached save key and re-scans `NFL1-Win64-Shipping.exe` against the save (UTF-16LE candidates).
3. Optionally refreshes the pak AES key + usmap from the public FLi-FModel index into
   `%LOCALAPPDATA%\\StolenHours\\game_cache` (or XDG on Linux). Offline: skips this step.
4. If the .NET asset extractor and a writable project tree are available, can re-run `build-ui`.

The portable exe always re-finds the save key from the game. Bundled UI tables stay until the next ship or a
local `build-ui`; the cache still holds fresh pak/usmap for that rebuild.

UNVERIFIED: FLi-FModel "LATEST" matching the installed Steam build after every patch (check: after an update,
Rewalk reports the new buildid and a successful key roundtrip).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import container, paths, steam, uiassets

FLI_FMODEL_INDEX = "https://drayx.github.io/FLi-FModel/"
CACHE_DIR = paths.USER_DATA / "game_cache"
FINGERPRINT_FILE = CACHE_DIR / "fingerprint.json"
PAK_CACHE = CACHE_DIR / "pak_key.hex"
MAP_CACHE = CACHE_DIR / "mappings.usmap"
STATE_FILE = CACHE_DIR / "rewalk_state.json"


def pak_key_path() -> Path:
    return PAK_CACHE if PAK_CACHE.exists() else paths.PAK_KEY_FILE


def mappings_path() -> Path:
    return MAP_CACHE if MAP_CACHE.exists() else paths.MAPPINGS_FILE


def _manifest_for(game: Path) -> Path | None:
    # .../common/<installdir> -> .../steamapps/appmanifest_*.acf
    steamapps = game.parent.parent
    m = steamapps / f"appmanifest_{steam.APP_ID}.acf"
    return m if m.is_file() else None


def fingerprint(game: Path | None = None) -> dict:
    """Stable identity of the installed game for update detection."""
    games = [game] if game else steam.find_game_dirs()
    if not games:
        return {"ok": False, "error": "game not found", "buildid": None, "exe": None}
    g = games[0]
    exe = g / steam.SHIPPING_REL
    st = exe.stat()
    buildid = None
    lastupdated = None
    name = None
    m = _manifest_for(g)
    if m:
        state = steam._ci(steam._read_vdf(m), "AppState") or {}
        buildid = steam._ci(state, "buildid")
        lastupdated = steam._ci(state, "LastUpdated") or steam._ci(state, "lastupdated")
        name = steam._ci(state, "name")
    return {
        "ok": True,
        "game": str(g),
        "exe": str(exe),
        "exe_size": st.st_size,
        "exe_mtime": int(st.st_mtime),
        "buildid": str(buildid) if buildid is not None else None,
        "lastupdated": str(lastupdated) if lastupdated is not None else None,
        "name": name,
        "manifest": str(m) if m else None,
    }


def _same_fp(a: dict | None, b: dict | None) -> bool:
    if not a or not b or not a.get("ok") or not b.get("ok"):
        return False
    if a.get("buildid") and b.get("buildid"):
        return a["buildid"] == b["buildid"] and a.get("exe_size") == b.get("exe_size")
    return a.get("exe_size") == b.get("exe_size") and a.get("exe_mtime") == b.get("exe_mtime")


def load_saved_fingerprint() -> dict | None:
    try:
        return json.loads(FINGERPRINT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_fingerprint(fp: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_FILE.write_text(json.dumps(fp, indent=2), encoding="utf-8")


def game_changed() -> bool:
    """True when we have no prior fingerprint, or the install no longer matches it."""
    cur = fingerprint()
    if not cur.get("ok"):
        return True
    return not _same_fp(load_saved_fingerprint(), cur)


def clear_key_cache() -> None:
    container._found_key = None


def resolve_save_key(raw: bytes | None = None, prefer_game: bool = False) -> dict:
    """Find a working save AES key. After an update, prefer_game=True ignores a stale project key file."""
    clear_key_cache()
    out = {"ok": False, "source": None, "tested_games": 0}
    if raw is None:
        try:
            raw = paths.default_save_path().read_bytes()
        except (paths.NotFound, OSError) as e:
            out["error"] = str(e)
            return out

    def try_key(key: bytes, source: str) -> bool:
        try:
            container.unpack(raw, key)
        except container.ContainerError:
            return False
        container._found_key = key
        out.update(ok=True, source=source)
        return True

    if not prefer_game and paths.KEY_FILE.exists():
        try:
            if try_key(container.load_key(), "key_file"):
                return out
            out["key_file_stale"] = True
        except container.ContainerError:
            out["key_file_stale"] = True

    for game in steam.find_game_dirs():
        out["tested_games"] += 1
        key = container.key_from_game(game / steam.SHIPPING_REL, raw)
        if key and try_key(key, f"game:{game}"):
            return out
    out["error"] = "no working save key in the key file or Fantasy Life i install"
    return out


def fetch_fli_fmodel(timeout: float = 20.0) -> dict:
    """Pull the latest pak AES key + usmap listed by FLi-FModel into the local cache."""
    out = {"ok": False, "url": FLI_FMODEL_INDEX}
    try:
        with urllib.request.urlopen(FLI_FMODEL_INDEX, timeout=timeout) as r:
            index = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        out["error"] = f"index fetch failed: {e}"
        return out
    if not isinstance(index, dict) or not index:
        out["error"] = "empty FLi-FModel index"
        return out
    latest_ver, latest = None, None
    for ver, row in index.items():
        if isinstance(row, dict) and row.get("LATEST"):
            latest_ver, latest = ver, row
            break
    if latest is None:
        latest_ver, latest = list(index.items())[-1]
    key_hex = (latest.get("MainKey") or "").replace("0x", "").replace("0X", "").strip()
    map_url = latest.get("Url")
    if len(key_hex) != 64 or not map_url:
        out["error"] = f"bad FLi-FModel row for {latest_ver}"
        return out
    try:
        with urllib.request.urlopen(map_url, timeout=timeout) as r:
            usmap = r.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["error"] = f"usmap fetch failed: {e}"
        return out
    if len(usmap) < 64:
        out["error"] = "usmap too small"
        return out
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PAK_CACHE.write_text(key_hex + "\n", encoding="ascii")
    MAP_CACHE.write_bytes(usmap)
    out.update(ok=True, version=latest_ver, file=latest.get("FileName"),
               pak_key=str(PAK_CACHE), mappings=str(MAP_CACHE), bytes=len(usmap))
    return out


def can_build_ui() -> dict:
    """Whether this machine can re-extract game tables (dev tree / tooling)."""
    from . import paths as p
    extractor = p.PROJECT_ROOT / "tools" / "asset_extract"
    dll = extractor / "bin" / "Release" / "net10.0" / "asset_extract.dll"
    return {
        "frozen": paths.FROZEN,
        "extractor_proj": extractor.is_dir(),
        "extractor_dll": dll.is_file(),
        "pak_key": pak_key_path().is_file(),
        "mappings": mappings_path().is_file(),
        "writable_assets": not paths.FROZEN,
    }


def rebuild_ui(force: bool = False, log=print) -> dict:
    """Re-run build-ui when tooling is present. No-op inside the frozen exe."""
    ready = can_build_ui()
    if ready["frozen"] or not ready["writable_assets"]:
        return {"ok": False, "skipped": "frozen_exe", "note": "portable build ships tables; rebuild on the project PC"}
    if not ready["pak_key"] or not ready["mappings"]:
        return {"ok": False, "skipped": "missing_pak_or_usmap", "ready": ready}
    try:
        from . import (avatar3d, collection, companions, forge, island, mapevents, mapview, skillboard)
        for mod in (uiassets, avatar3d, skillboard, mapevents, mapview, collection, forge, island, companions):
            mod.extract(force=force)
            mod.build(log=log)
        return {"ok": True, "ready": ready}
    except Exception as e:
        return {"ok": False, "error": str(e), "ready": ready}


def rewalk(force: bool = False, fetch_assets: bool = True, rebuild: bool = False,
           prefer_game_key: bool = True) -> dict:
    """Full recovery walk. Safe and read-only on the game install (writes only under USER_DATA / project assets)."""
    started = time.time()
    fp = fingerprint()
    prev = load_saved_fingerprint()
    changed = force or not _same_fp(prev, fp)
    report = {
        "ok": False,
        "changed": changed,
        "forced": force,
        "fingerprint": fp,
        "previous": prev,
        "steam_roots": [str(p) for p in steam.find_steam_roots()],
        "games_dirs": [str(p) for p in steam.find_game_dirs()],
        "saves": [str(s.path) for s in steam.find_saves()],
        "key": None,
        "fli_fmodel": None,
        "build_ui": None,
        "seconds": 0.0,
    }
    if not fp.get("ok"):
        report["error"] = fp.get("error") or "game not found"
        _save_state(report)
        return report

    report["key"] = resolve_save_key(prefer_game=prefer_game_key or changed)
    if fetch_assets and changed:
        report["fli_fmodel"] = fetch_fli_fmodel()
    elif fetch_assets and force:
        report["fli_fmodel"] = fetch_fli_fmodel()

    if rebuild and (changed or force):
        report["build_ui"] = rebuild_ui(force=force)

    if report["key"].get("ok"):
        save_fingerprint(fp)
        report["ok"] = True
    report["seconds"] = round(time.time() - started, 2)
    _save_state(report)
    return report


def ensure_current(auto_fetch: bool = True) -> dict:
    """Called on editor start: rewalk only when the install fingerprint changed."""
    if not game_changed():
        fp = fingerprint()
        return {"ok": True, "changed": False, "fingerprint": fp, "note": "game fingerprint unchanged"}
    return rewalk(force=False, fetch_assets=auto_fetch, rebuild=False, prefer_game_key=True)


def status() -> dict:
    fp = fingerprint()
    prev = load_saved_fingerprint()
    state = {}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    key_ok = False
    key_source = None
    try:
        raw = paths.default_save_path().read_bytes()
        # don't mutate cache heavily; test current resolve path
        key = container.resolve_key(raw)
        container.unpack(raw, key)
        key_ok = True
        key_source = "cached" if container._found_key else ("key_file" if paths.KEY_FILE.exists() else "resolved")
    except Exception as e:
        key_source = str(e)
    return {
        "fingerprint": fp,
        "saved": prev,
        "changed": not _same_fp(prev, fp) if fp.get("ok") else True,
        "key_ok": key_ok,
        "key_source": key_source,
        "cache": {
            "dir": str(CACHE_DIR),
            "pak_key": pak_key_path().is_file(),
            "mappings": mappings_path().is_file(),
            "using_cache_pak": PAK_CACHE.exists(),
            "using_cache_map": MAP_CACHE.exists(),
        },
        "can_build_ui": can_build_ui(),
        "last_rewalk": {k: state.get(k) for k in ("ok", "changed", "seconds", "key", "fli_fmodel") if k in state},
        "steam_roots": [str(p) for p in steam.find_steam_roots()],
        "games": [str(p) for p in steam.find_game_dirs()],
        "saves": [str(s.path) for s in steam.find_saves()[:8]],
    }


def _save_state(report: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slim = {k: report.get(k) for k in ("ok", "changed", "forced", "seconds", "fingerprint", "key", "fli_fmodel",
                                         "build_ui", "error")}
    slim["when"] = time.strftime("%Y-%m-%d %H:%M:%S")
    STATE_FILE.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
