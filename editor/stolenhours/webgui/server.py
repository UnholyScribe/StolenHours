"""Local HTTP backend for the game-styled editor. Serves web/ and a JSON API at POST /api/<method>.

Bound to 127.0.0.1 only; every API call must carry the per-session token, so other local pages can't drive it.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import (collection, forge, gear, live, mapevents, mapview, modinstall, paths, records, safety, savefile,
                skilltree, uiassets)

WEB_DIR = paths.PACKAGE_DIR / "webgui" / "web"
LIVE_DOSH = ("GDDPlayData", "m_permanent.Money")
# live objects from the in-game dump; whether the world follows a write right away is UNVERIFIED
LIVE_CLOCK = {"time": ("GDDPhaseStatus", "m_permanent.envInfo.gameTime"),
              "period": ("GDDPhaseStatus", "m_permanent.envInfo.gameTimePeriodType"),
              "weather": ("GDDWeatherStatus", "m_permanent.WeatherInfo.weatherType")}
LIVE_EVENT_PATHS = [("GDDQuestStatus", "m_permanent.ActiveEventInfo"),
                    ("GDDQuestStatus", "m_volatile.ActiveEventStatusV.openActiveEventList"),
                    ("GDDQuestStatus", "m_permanent.Active")]

# the pywebview window, once app.py opens it; None in browser mode (no native file dialogs there)
WINDOW = None
BIN_TYPES = ("Fantasy Life i save (*.bin)", "All files (*.*)")

mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("text/javascript", ".js")


class ApiError(Exception):
    pass


class Backend:
    def __init__(self, save_path: Path | None = None):
        self.lock = threading.RLock()
        self.sf: savefile.SaveFile | None = None
        self.save_path = save_path
        self.catalog = self._load_item_catalog()
        self.item_names = {i["id"]: i["name"] for i in self.catalog} or savefile.load_item_names()
        self.item_info = {i["id"]: i for i in self.catalog}
        self.bridge = live.LiveBridge()
        self.main_gear = gear.MainGear(self.bridge)

    @staticmethod
    def _load_item_catalog() -> list:
        try:
            return json.loads((paths.UI_ASSET_DIR / "items" / "catalog.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []

    # ---- helpers ---------------------------------------------------------------
    def _need(self) -> savefile.SaveFile:
        if self.sf is None:
            raise ApiError("no save loaded")
        return self.sf

    def _item(self, it: savefile.Item, rec: dict | None = None) -> dict:
        info = self.item_info.get(it.item_id, {})
        out = {"index": it.index, "id": it.item_id, "name": self.item_names.get(it.item_id, it.item_id),
               "stock": it.stock, "category": it.category, "icon": info.get("icon", it.item_id)}
        if rec and "itemTitle" in rec:
            out["gear"] = {"grade": rec["itemTitle"], "quality": rec["Quality"],
                           "bonus": rec["addEquipStatus"][0]["Type"] if rec["addEquipStatus"] else 0,
                           "skills": [s for s in rec["grantSkillId"] if s and s != "None"],
                           "equipped": bool(rec["equipped"])}
        return out

    # ---- API -------------------------------------------------------------------
    def api_state(self) -> dict:
        procs = safety.running_game_processes()
        saves = [str(p) for p in paths.candidate_save_paths()]
        with self.lock:
            sf = self.sf
            return {"loaded": sf is not None, "path": str(sf.path) if sf else (str(self.save_path or "") or
                                                                             (saves[0] if saves else "")),
                    "saves": saves, "dirty": bool(sf and sf.dirty), "game_running": bool(procs),
                    "stale": bool(sf) and self._disk_changed(sf),
                    "mod_alive": self.bridge.mod_alive(), "assets": (paths.UI_ASSET_DIR / "wallpaper.jpg").exists()}

    def _disk_changed(self, sf: savefile.SaveFile) -> bool:
        """True once the file on disk no longer matches what was loaded (usually: the game saved)."""
        try:
            st = sf.path.stat()
        except OSError:
            return False
        key = (st.st_mtime_ns, st.st_size, id(sf.raw))
        if getattr(self, "_disk_seen", (None,))[0] != key:
            try:
                changed = sf.path.read_bytes() != sf.raw
            except OSError:
                return False
            self._disk_seen = (key, changed)
        return self._disk_seen[1]

    def api_load(self, path: str = "") -> dict:
        target = Path(path) if path else (self.save_path or paths.default_save_path())
        sf = savefile.SaveFile.load(target)
        with self.lock:
            self.sf, self.save_path = sf, target
        self._record_history(sf)
        return self.api_summary()

    @staticmethod
    def _record_history(sf: savefile.SaveFile) -> None:
        try:
            records.record(sf)
        except (OSError, KeyError, ValueError):
            pass  # history is a convenience; never block loading or saving

    def api_summary(self) -> dict:
        with self.lock:
            sf = self._need()
            return {"path": str(sf.path), "name": sf.character_name, "island": sf.island_name, "money": sf.money,
                    "money_max": savefile.MONEY_MAX, "play_time": sf.play_time_seconds, "life": sf.current_life,
                    "play_time_max": sf.play_time_max, "island_max": savefile.ISLAND_NAME_MAX,
                    "lives": sf.lives(), "categories": sf.inventory_categories(),
                    "counts": {c: len(sf.items(c)) for c in sf.inventory_categories()}, "dirty": sf.dirty}

    def api_items(self, category: str) -> list:
        with self.lock:
            sf = self._need()
            return [self._item(it, sf.inventory[it.category][it.index]) for it in sf.items(category)]

    def api_search_items(self, query: str, pocket: str = "", limit: int = 40) -> list:
        q = query.strip().lower()
        if not q:
            return []
        if not self.catalog:
            hits = [{"id": k, "name": v, "icon": k} for k, v in self.item_names.items()
                    if q in v.lower() or q == k.lower()]
        else:
            hits = [i for i in self.catalog if not i["hidden"] and (not pocket or i["pocket"] == pocket)
                    and (q in i["name"].lower() or q == i["id"].lower())]
        hits.sort(key=lambda i: (not i["name"].lower().startswith(q), len(i["name"]), i.get("sort", 0)))
        return [{"id": i["id"], "name": i["name"], "icon": i.get("icon"), "pocket": i.get("pocket"),
                 "pocket_guess": i.get("pocket_guess", False)} for i in hits[:limit]]

    def api_set_overview(self, name: str, money: int, island: str | None = None, play_time: int | None = None) -> dict:
        with self.lock:
            sf = self._need()
            # validate everything before changing anything, so a bad field doesn't leave a half-applied edit
            trial = savefile.SaveFile(sf.path, sf.raw, sf.key, {"saveData": {
                "m_PlayData": dict(sf.sd["m_PlayData"]), "m_CharaStatus": {"m_stAvatarP": [dict(sf.avatar)]}}})
            trial.character_name, trial.money = name, int(money)
            if island is not None:
                trial.island_name = island
            if play_time is not None:
                trial.play_time_seconds = int(play_time)
            if name != sf.character_name:
                sf.character_name = name
            if int(money) != sf.money:
                sf.money = int(money)
            if island is not None and island != sf.island_name:
                sf.island_name = island
            if play_time is not None and int(play_time) != sf.play_time_seconds:
                sf.play_time_seconds = int(play_time)
        return self.api_summary()

    def api_set_life(self, life_id: str, level: int, exp: int, rank: int) -> dict:
        with self.lock:
            sf = self._need()
            old = next((l["level"] for l in sf.lives() if l["id"] == life_id), None)
            sf.set_life(life_id, level=int(level), exp=int(exp), rank=int(rank))
            if old is not None and int(level) != old and self._tree(required=False):
                self._tree().set_level_sp(sf, life_id, old, int(level))
        return self.api_summary()

    def _tree(self, required: bool = True) -> skilltree.SkillTree | None:
        if getattr(self, "_skilltree", None) is None:
            try:
                self._skilltree = skilltree.SkillTree.load()
            except FileNotFoundError:
                if required:
                    raise ApiError("skill boards not built; run: py -3.12 -m stolenhours build-ui")
                return None
        return self._skilltree

    def api_skill_board(self, life_id: str) -> dict:
        with self.lock:
            return self._tree().state(self._need(), life_id)

    def api_skill_edit(self, life_id: str, action: str, no: int = -1, free: bool = False) -> dict:
        tree = self._tree()
        with self.lock:
            sf = self._need()
            if action == "learn":
                tree.learn(sf, life_id, int(no), free=bool(free))
            elif action == "remove":
                tree.remove(sf, life_id, int(no))
            elif action == "learn_all":
                tree.learn_all(sf, life_id)
            elif action == "reset":
                tree.reset(sf, life_id)
            else:
                raise ApiError(f"unknown skill action {action}")
            return {"board": tree.state(sf, life_id), "summary": self.api_summary()}

    def _events(self) -> mapevents.MapEvents:
        if getattr(self, "_mapevents", None) is None:
            try:
                self._mapevents = mapevents.MapEvents.load()
            except FileNotFoundError:
                raise ApiError("map events not built; run: py -3.12 -m stolenhours build-ui")
        return self._mapevents

    def api_events(self) -> dict:
        with self.lock:
            return self._events().state(self._need())

    def api_events_edit(self, action: str, ids: list | None = None, count: int = mapevents.MAP_SIZE,
                        rules: bool = True, cats: list | None = None, hour: int = 0, minute: int = 0,
                        period: int | None = None, weather: int = 1) -> dict:
        ev = self._events()
        note = None
        with self.lock:
            sf = self._need()
            if action == "emerge":
                removed = ev.emerge(sf, list(ids or []))
                note = removed and f"replaced {len(removed)} event(s) at the same place"
            elif action == "dismiss":
                ev.dismiss(sf, list(ids or []))
            elif action == "clear":
                ev.clear(sf)
            elif action == "draw":
                picked = ev.draw(sf, int(count), rules=bool(rules), cats=cats or None)
                note = f"drew {len(picked)} event(s)"
            elif action == "reset_progress":
                note = f"reset {ev.reset_progress(sf)} cleared event(s)"
            elif action == "time":
                ev.set_time(sf, int(hour), int(minute), None if period is None else int(period))
            elif action == "weather":
                ev.set_weather(sf, int(weather))
            else:
                raise ApiError(f"unknown events action {action}")
            return {"events": ev.state(sf), "note": note, "summary": self.api_summary()}

    def api_set_stock(self, category: str, index: int, stock: int) -> list:
        with self.lock:
            self._need().set_stock(category, int(index), int(stock))
        return self.api_items(category)

    def api_add_item(self, category: str, item_id: str, stock: int = 1) -> dict:
        info = self.item_info.get(item_id)
        if self.catalog and info is None:
            raise ApiError(f"{item_id} is not an item the game defines")
        if info and info["pocket"] != category:
            raise ApiError(f"{info['name']} belongs in {info['pocket'] or 'an unknown pocket'}, not {category}")
        try:
            title = self._forge().default_grade(item_id)
        except ApiError:
            title = None
        with self.lock:
            slot = self._need().add_item(category, item_id, int(stock), title=title)
        return {"slot": slot, "items": self.api_items(category)}

    def api_appearance(self) -> dict:
        with self.lock:
            return self._need().appearance()

    def api_held_items(self) -> dict:
        with self.lock:
            return self._need().held_items()

    def api_main_gear(self) -> dict:
        with self.lock:
            sf = self.sf
        return self.main_gear.get(sf)

    def api_skill_panels(self) -> dict:
        with self.lock:
            return self._need().skill_panels()

    def _avatar_options(self) -> dict[str, set[str]]:
        try:
            catalog = json.loads((paths.UI_ASSET_DIR / "avatar" / "catalog.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        return {f["field"]: {o["id"] for o in f["options"]} for f in catalog["fields"]}

    def api_set_appearance(self, values: dict) -> dict:
        allowed = self._avatar_options()
        with self.lock:
            sf = self._need()
            cur = sf.appearance()
            for k, v in values.items():
                if str(v) != str(cur.get(k)):
                    sf.set_appearance(k, v, allowed.get(k))
            return sf.appearance()

    def api_revert(self) -> dict:
        with self.lock:
            path = self._need().path
        return self.api_load(str(path))

    def api_save(self) -> dict:
        with self.lock:
            sf = self._need()
            res = sf.write()
        self._record_history(sf)
        return res

    # ---- backups ---------------------------------------------------------------
    def _save_on_disk(self) -> Path:
        with self.lock:
            path = self._need().path
        if not path.exists():
            raise ApiError(f"the save is not on disk anymore: {path}")
        return path

    def api_backups(self) -> dict:
        path = self._save_on_disk()
        return {"save": savefile.SaveFile.load(path).describe(), "folder": str(paths.BACKUP_ROOT),
                "backups": safety.list_backups()}

    def api_backup_now(self) -> dict:
        dest = safety.backup(self._save_on_disk(), "manual")
        return {"path": str(dest), "backups": safety.list_backups()}

    def api_open_backups(self) -> None:
        paths.BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        os.startfile(paths.BACKUP_ROOT)

    def api_pick(self, mode: str, name: str = "") -> dict:
        """Native Save As / Open dialog; {"path": None} if cancelled, {"manual": True} without a window."""
        if WINDOW is None:
            return {"manual": True}
        import webview
        kind = getattr(webview, "FileDialog", None)
        if mode == "save":
            dlg = kind.SAVE if kind else webview.SAVE_DIALOG
            got = WINDOW.create_file_dialog(dlg, save_filename=name, file_types=BIN_TYPES)
        elif mode == "open":
            dlg = kind.OPEN if kind else webview.OPEN_DIALOG
            got = WINDOW.create_file_dialog(dlg, allow_multiple=False, file_types=BIN_TYPES)
        else:
            raise ApiError("mode must be save or open")
        if isinstance(got, (list, tuple)):
            got = got[0] if got else None
        return {"path": got or None}

    def api_backup_to(self, path: str) -> dict:
        save = self._save_on_disk()
        dest = Path(path)
        if dest.is_dir():
            dest = dest / f"{time.strftime('%Y-%m-%d_%H%M%S')}_{save.name}"
        digest = safety.copy_verified(save, dest)
        return {"path": str(dest), "sha256": digest}

    def api_inspect(self, path: str) -> dict:
        info = savefile.SaveFile.load(Path(path)).describe()
        with self.lock:
            sf = self.sf
        info["same_adventure"] = bool(sf) and info["adventure"] == sf.describe()["adventure"]
        return info

    def api_restore(self, path: str) -> dict:
        target = self._save_on_disk()
        res = savefile.restore_save(Path(path), target)
        res["summary"] = self.api_load(str(target))
        res["backups"] = safety.list_backups()
        return res

    def api_records(self) -> dict:
        with self.lock:
            return records.records(self._need())

    def api_set_records(self, values: dict) -> dict:
        with self.lock:
            sf = self._need()
            for k, v in values.items():
                records.set_record(sf, k, v)
            return {"records": records.records(sf), "summary": self.api_summary()}

    # ---- recipes, library, gifts -------------------------------------------------
    def _collection(self) -> collection.Collection:
        if getattr(self, "_coll", None) is None:
            try:
                self._coll = collection.Collection.load()
            except FileNotFoundError:
                raise ApiError("collection data not built; run: py -3.12 -m stolenhours build-ui")
        return self._coll

    def _collection_state(self, sf: savefile.SaveFile) -> dict:
        c = self._collection()
        out = {"recipes": c.recipe_state(sf), "library": c.library_state(sf), "gifts": c.gift_state(sf),
               "lives": {l["id"]: l["name"] for l in sf.lives()}}
        ids = {r["item"] for r in out["recipes"]["recipes"]} | {e["id"] for e in out["library"]["items"]}
        ids |= {i["id"] for g in out["gifts"]["gifts"] + out["gifts"]["known"] for i in g["items"]}
        out["names"] = {i: self.item_names.get(i, i) for i in ids}
        out["icons"] = {i: self.item_info[i]["icon"] for i in ids if i in self.item_info}
        return out

    def api_collection(self) -> dict:
        with self.lock:
            return self._collection_state(self._need())

    def api_collection_edit(self, action: str, ids: list | None = None, codes: list | None = None) -> dict:
        c = self._collection()
        with self.lock:
            sf = self._need()
            if action == "recipes":
                note = f"learned {c.unlock_recipes(sf, list(ids or []))} recipe(s)"
            elif action == "library":
                note = f"filled in {c.unlock_library(sf, list(ids or []))} library entries"
            elif action == "reclaim":
                note = f"{c.reclaim(sf, list(ids or []), [int(i) for i in codes or []])} gift(s) can be claimed again"
            elif action == "grant":
                code = str((ids or [""])[0])
                note = f"added {c.grant(sf, code, self.item_info)} item(s) from {code} to your bag"
            else:
                raise ApiError(f"unknown collection action {action}")
            return {"collection": self._collection_state(sf), "note": note, "summary": self.api_summary()}

    # ---- Vulcan's Forge -----------------------------------------------------------
    def _forge(self) -> forge.Forge:
        if getattr(self, "_forge_data", None) is None:
            try:
                self._forge_data = forge.Forge.load()
            except FileNotFoundError:
                raise ApiError("forge data not built; run: py -3.12 -m stolenhours build-ui")
        return self._forge_data

    def api_forge(self) -> dict:
        f = self._forge()
        with self.lock:
            sf = self._need()
            lives = {l["id"]: l["name"] for l in sf.lives()}
        ids = set(f.items) | {e["plus"] for e in f.items.values() if "plus" in e}
        ids |= {m["id"] for e in f.items.values() for ms in e["mats"].values() for m in ms}
        return {**f.data, "lives": lives, "names": {i: self.item_names.get(i, i) for i in ids},
                "icons": {i: self.item_info[i]["icon"] for i in ids if i in self.item_info}}

    def api_forge_craft(self, item_id: str, count: int = 1, grade: int | None = None, bonus: bool = True,
                        skills: list | None = None, plus: bool = False, quality: int = 0) -> dict:
        f = self._forge()
        with self.lock:
            res = f.craft(self._need(), str(item_id), self.item_info, int(count), grade and int(grade), bool(bonus),
                          [str(s) for s in skills or []], bool(plus), int(quality or 0))
        res["name"] = self.item_names.get(res["item"], res["item"])
        res["summary"] = self.api_summary()
        return res

    def api_mod_status(self) -> dict:
        return modinstall.status()

    def api_mod_install(self) -> dict:
        return modinstall.install()

    def api_mapview_live(self) -> dict:
        """Read-only snapshot of the running game for the live map: events in play and the player's position."""
        out = {"game": bool(safety.running_game_processes()), "mod": self.bridge.mod_alive(), "events": None, "player": None,
               "notes": []}
        if not out["mod"]:
            return out
        r = self.bridge.events()
        if r.ok:
            count, _, rest = r.text.partition("|")
            ids, _, notes = rest.partition("|")
            out["events"] = [{"id": i, "phase": p} for i, _, p in (x.partition(":") for x in ids.split(",") if x)]
            if notes:
                out["notes"].append(notes)
        elif r.text.startswith("unknown command"):
            out["needs_update"] = True
            return out
        else:
            out["notes"].append(f"events: {r.text}")
        r = self.bridge.player()
        if r.ok:
            x, y, z, yaw, map_id = r.text.split(",")
            out["player"] = {"x": float(x), "y": float(y), "z": float(z), "yaw": float(yaw), "map": map_id,
                             **mapview.world_to_map(float(x), float(y))}
        else:
            out["notes"].append(f"player: {r.text}")
        return out

    def api_live(self, action: str, value: str = "") -> dict:
        b = self.bridge
        if action == "ping":
            r = b.ping()
        elif action == "get_dosh":
            r = b.get(*LIVE_DOSH)
        elif action == "set_dosh":
            r = b.set(*LIVE_DOSH, int(value))
        elif action == "dump":
            r = b.dump()
        elif action in ("probe", "map_keys"):
            target, _, path = value.partition(" ")
            r = b.send(action.upper(), target, path, timeout=20)
        elif action == "probe_events":
            lines = []
            for target, path in LIVE_EVENT_PATHS:
                for verb in ("PROBE", "MAP_KEYS"):
                    rr = b.send(verb, target, path, timeout=20)
                    lines.append(f"{verb} {path}: {'OK' if rr.ok else 'ERR'} {rr.text}")
            return {"ok": True, "text": "\n".join(lines)}
        elif action == "get_clock":
            parts = [b.get(*LIVE_CLOCK[k]) for k in ("time", "period", "weather")]
            if not all(p.ok for p in parts):
                return {"ok": False, "text": next(p.text for p in parts if not p.ok)}
            return {"ok": True, "text": " | ".join(p.text for p in parts),
                    "clock": {k: p.text for k, p in zip(("time", "period", "weather"), parts)}}
        elif action in ("set_time", "set_period", "set_weather"):
            key = action[4:]
            if key == "time":
                num = float(value)
                if not 0 <= num < 10 ** 7:
                    raise ApiError("game time out of range")
            else:
                num = int(value)
                if num not in ((0, 1) if key == "period" else (1, 2, 3)):
                    raise ApiError(f"bad {key} value {value}")
            r = b.set(*LIVE_CLOCK[key], num)
        else:
            raise ApiError(f"unknown live action {action}")
        return {"ok": r.ok, "text": r.text}


class Handler(BaseHTTPRequestHandler):
    backend: Backend
    token: str
    protocol_version = "HTTP/1.1"  # keep-alive: the Look tab loads hundreds of icons at once

    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str, cache: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        rel = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        if rel == "favicon.ico":
            self._send(204, b"", "image/x-icon", cache=True)
            return
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR not in target.parents or not target.is_file():
            self._send(404, b"not found", "text/plain")
            return
        body = target.read_bytes()
        if rel == "index.html":
            # WebView2 can keep stale scripts despite no-store; versioned URLs force a fresh fetch
            v = str(int(max((WEB_DIR / n).stat().st_mtime for n in ("app.js", "style.css", "look3d.js"))))
            body = body.replace(b"{{v}}", v.encode())
        self._send(200, body, mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                   cache=rel.startswith("game/"))

    def do_POST(self):
        if self.headers.get("X-Token") != self.token or not self.path.startswith("/api/"):
            self._send(403, b"forbidden", "text/plain")
            return
        fn = getattr(self.backend, "api_" + self.path[5:], None)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            args = json.loads(self.rfile.read(n) or b"{}")
            if fn is None:
                raise ApiError("unknown method")
            out = {"ok": True, "data": fn(**args)}
        except (ApiError, savefile.SaveFileError, safety.SafetyError, paths.NotFound, live.LiveError,
                ValueError, KeyError, OSError) as e:
            out = {"ok": False, "error": str(e) or type(e).__name__}
        except Exception as e:
            log = paths.USER_DATA / "editor_errors.log"
            try:
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("a", encoding="utf-8") as f:
                    f.write(f"--- {time.ctime()} {self.path}\n{traceback.format_exc()}\n")
            except OSError:
                pass
            out = {"ok": False, "error": f"{type(e).__name__}: {e} (details in {log})"}
        self._send(200, json.dumps(out).encode(), "application/json")


class _Server(ThreadingHTTPServer):
    allow_reuse_address = False  # on Windows reuse lets two editors share a port and answer each other's calls
    daemon_threads = True
    request_queue_size = 128  # the default 5 drops bursts of image requests (ERR_NO_BUFFER_SPACE / Failed to fetch)
    request_queue_size = 128


def start(save_path: Path | None = None, port: int = 0, token: str | None = None) -> tuple[ThreadingHTTPServer, str]:
    token = token or secrets.token_urlsafe(24)
    handler = type("BoundHandler", (Handler,), {"backend": Backend(save_path), "token": token})
    srv = _Server(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/?t={token}"


def ensure_assets(log=print) -> None:
    """Build the UI art from the extracted game files when possible; the UI still works without it."""
    if (paths.UI_ASSET_DIR / "wallpaper.jpg").exists():
        return
    try:
        if any(paths.EXTRACT_DIR.rglob("_tex_title_launcher.png")):
            uiassets.build(log=log)
    except Exception as e:  # cosmetic only
        log(f"UI art not built ({e}); run: py -3.12 -m stolenhours build-ui")
