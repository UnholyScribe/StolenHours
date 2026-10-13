"""Map events (the game's "Active Events"): dump the catalog for the editor and edit which ones are on the map.

Game data (GDSActiveEvent*, verified against the live schema dump):
- `GDSActiveEventConfig` row per event (title, place, reward tier), `GDSActiveEventTarget.ActiveEventType`
  (EActiveEventType: 1 Battle, 2 Pick, 3 Delivery, 4 PickThenBattle), `GDSActiveEventPlaceData` (place -> area).
- `GDSActiveEventLottery`: weighted draw tables. `lottery_qsf_common` is the solo overworld pool,
  `lottery_qsf_multi` the multiplayer one, `lottery_qsf_gauge_event` the `_multi` legendary gauge events. Each lot
  has a weight (`Rate`, `rateOnFar` when far from the player) and conditions; lots requiring
  `IsPlayingRoguelike_True` belong to the dream dungeon.
- Live game parameters (dump): 10 events on the map (`appearActiveEventNum`), one event per place
  (`excludeClearedActiveEventPlaceFromLottery`), at most one legendary in solo (`preventLegendEventMultipleEmergingOnSolo`).

Save side:
- `m_QuestStatus.Active[id]` = {phase, isNew, tmpFlagList}; phase is ETemplateActiveEventPhase: 0 None,
  1 Emerge (on the map), 2 Progress, 3 second phase, 254 Achieve, 255 End.
- `m_QuestStatus.ActiveEventInfo` = Map<id, {s8 timePeriodChangeCount}>.
- `m_PhaseInfo.envInfo`: `gameTime` (float), `gameTimePeriodType` (0 Day, 1 Night); `m_WeatherStatus.WeatherInfo[]`
  (EWeatherType 1 Sunny, 2 Rainy, 3 Cloudy).
UNVERIFIED (Unholy's save has no event on the map yet, every phase is 0 and ActiveEventInfo is empty):
- putting an event on the map = phase 1 + an ActiveEventInfo entry with count 0. Check: emerge one, load the save,
  look for its map icon; or let the game spawn one, save, and diff these two fields.
- `gameTime` is in game minutes (2110.58 -> day 1, 11:10, matches "Day"; the game's time-zone table uses
  hour/minute). Check: set a time, load, compare the in-game clock.
- AreaRankRelease_Greater is treated as releaseAreaRank >= n (like LicenseRank_Over).
"""
from __future__ import annotations

import json
import random
import struct
from pathlib import Path

from . import paths, uiassets
from .savefile import SaveFile, SaveFileError

GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"
EVENTS_FILE = paths.UI_ASSET_DIR / "events" / "events.json"
DATA_PATTERN = (r"^Game/Content/GameData/(Quest/GDS(ActiveEvent\w+|QuestTitleText)|"
                r"Map/GDS(AreaDef|MapText_Noun)|System/GDSGlobalBitFlag)\.uasset$")
TYPE_NAME = {0: "Other", 1: "Battle", 2: "Gathering", 3: "Delivery", 4: "Special"}
WEATHER = {1: "Sunny", 2: "Rainy", 3: "Cloudy"}
PERIOD = {0: "Day", 1: "Night"}
COMMON_BATTLE = "Take Down All Monsters!"
LIVE_PHASES = (1, 2, 3)
MAP_SIZE = 10
DAY_MINUTES = 1440


def extract(force: bool = False) -> None:
    if force or not (GAME_DATA / "Quest" / "GDSActiveEventLottery.json").exists() \
            or not (GAME_DATA / "Map" / "GDSAreaDef.json").exists():
        uiassets._run_extractor("json", DATA_PATTERN)


class _Table:
    def __init__(self, rel: str):
        props = json.loads((GAME_DATA / rel).read_text(encoding="utf-8"))[0]["Properties"]
        self.rows = {self._key(r["Key"]): r["Value"] for r in props["m_dataMap"]}
        self.bin = bytes(props.get("m_autoBin") or [])
        self.str = props.get("m_autoStr") or ""

    @staticmethod
    def _key(k):
        return k["Name"] if isinstance(k, dict) else k

    def arg(self, a: dict):
        at = 16 + a["m_offset"]
        tag, val = self.bin[at], struct.unpack_from("<i", self.bin, at + 1)[0]
        if tag == 0x34:
            return self.str[val:val + a["m_dataSize"]]
        return val if tag == 0x32 else {"tag": tag, "raw": val}


def _noun(row: dict, key: str) -> str | None:
    info = row.get(key) or []
    return info[0].get("nounSingularForm_en") if info else None


def _condition(table: _Table, c: dict) -> dict:
    args = [table.arg(a) for a in c["arg"]]
    cmd = c["Cmd"].removeprefix("CondCmd_")
    if cmd == "GameTimePeriod_IsNight":
        return {"type": "period", "period": 1}
    if cmd == "GameTimePeriod_IsDay":
        return {"type": "period", "period": 0}
    if cmd == "AreaRankRelease_Greater":
        return {"type": "area", "area": args[0], "rank": args[1]}
    if cmd == "LicenseRank_Over":
        return {"type": "rank", "life": args[1], "rank": args[2]}
    if cmd == "IsWeatherType":
        return {"type": "weather", "weather": args[0]}
    if cmd == "GetGlobalBitFlag_True":
        return {"type": "flag", "flag": args[0]}
    return {"type": cmd, "args": args}


def build(out: Path | None = None, log=print) -> dict:
    out = out or EVENTS_FILE.parent
    if not (GAME_DATA / "Quest" / "GDSActiveEventLottery.json").exists():
        log("map events: no exported event data; run extract first")
        return {"missing": ["event data"]}
    config, target = _Table("Quest/GDSActiveEventConfig.json"), _Table("Quest/GDSActiveEventTarget.json")
    place, reward = _Table("Quest/GDSActiveEventPlaceData.json"), _Table("Quest/GDSActiveEventRewardData.json")
    lottery = _Table("Quest/GDSActiveEventLottery.json")
    titles = {k: (v["Text"][0].get("nounSingularForm_en") if v.get("Text") else None)
              for k, v in _Table("Quest/GDSQuestTitleText.json").rows.items()}
    map_noun = _Table("Map/GDSMapText_Noun.json").rows
    areas = {}
    for aid, a in _Table("Map/GDSAreaDef.json").rows.items():
        name = _noun(map_noun.get(a["m_areaNameId"], {}), "nounInfo")
        if name:
            areas[aid] = name
    flags = {k: v["idx"] for k, v in _Table("System/GDSGlobalBitFlag.json").rows.items()}
    try:
        items = {i["id"]: i["name"] for i in json.loads((paths.UI_ASSET_DIR / "items" / "catalog.json")
                                                        .read_text(encoding="utf-8"))}
    except FileNotFoundError:
        items = {}

    pools: dict[str, dict] = {}
    for key, row in lottery.rows.items():
        pool = key.removeprefix("lottery_qsf_")
        for lot in row["lot"]:
            conds = [_condition(lottery, c) for c in lot["cond"]]
            if any(c["type"] == "IsPlayingRoguelike_True" for c in conds):
                continue
            pools.setdefault(lot["activeEventId"], {})[pool] = {"rate": lot["Rate"], "far": lot["rateOnFar"],
                                                               "conds": conds}
    common_total = sum(p["common"]["rate"] for p in pools.values() if "common" in p)

    events = []
    for eid, lots in pools.items():
        if "common" not in lots or eid not in config.rows:
            continue
        c, t = config.rows[eid], target.rows.get(eid, {})
        pl = place.rows.get(c["EventPointId"], {})
        etype = t.get("ActiveEventType", 0)
        title = titles.get(c["TitleId"]) or eid
        item = c["ReportData"].get("ItemId")
        if "<ITEM_NAME>" in title:
            title = title.replace("<ITEM_NAME>", items.get(item, item or "?"))
        tier = (c.get("GoldRewardId") or "").removeprefix("qsf_reward_").removesuffix("_gold")
        gold = reward.rows.get(c.get("GoldRewardId"), {}).get("RewardInfo", {})
        rate = lots["common"]["rate"]
        if "Legendary" in title:
            cat = "legendary"
        elif etype == 4:
            cat = "boss" if rate < 100 else "special"
        elif etype == 1 and title != COMMON_BATTLE:
            cat = "monster"
        else:
            cat = TYPE_NAME.get(etype, "Other").lower()
        events.append({
            "id": eid, "title": title, "type": TYPE_NAME.get(etype, str(etype)), "cat": cat,
            "place": c["EventPointId"], "area": pl.get("AreaID"), "map": pl.get("mapId"),
            "rate": rate, "far": lots["common"]["far"], "share": round(100 * rate / common_total, 3),
            "conds": lots["common"]["conds"], "multi": "multi" in lots, "tier": tier,
            "reward": {"dosh": gold.get("rich", 0), "chestnut": gold.get("chestnut", 0),
                       "areaPoint": gold.get("AreaPoint", 0)},
            "goldTime": c.get("GoldRankTime"), "silverTime": c.get("SilverRankTime"),
        })
    events.sort(key=lambda e: (e["area"] or "", e["id"]))
    out.mkdir(parents=True, exist_ok=True)
    (out / "events.json").write_text(json.dumps({"events": events, "areas": areas, "flags": {
        f: flags[f] for e in events for c in e["conds"] if c["type"] == "flag" for f in [c["flag"]] if f in flags}},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"map events: {len(events)} events in {len(areas)} areas -> {out}")
    return {"events": len(events), "areas": len(areas)}


class MapEvents:
    def __init__(self, data: dict):
        self.events: dict[str, dict] = {e["id"]: e for e in data["events"]}
        self.areas: dict[str, str] = data["areas"]
        self.flags: dict[str, int] = data.get("flags") or {}

    @classmethod
    def load(cls, path: Path = EVENTS_FILE) -> "MapEvents":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---- save access -----------------------------------------------------------
    @staticmethod
    def _quest(sf: SaveFile) -> dict:
        return sf.sd["m_QuestStatus"]

    def _active(self, sf: SaveFile) -> dict[str, dict]:
        return {e["key"]: e["value"] for e in self._quest(sf)["Active"]}

    def _info(self, sf: SaveFile) -> list[dict]:
        return self._quest(sf)["ActiveEventInfo"]

    @staticmethod
    def _env(sf: SaveFile) -> dict:
        return sf.sd["m_PhaseInfo"]["envInfo"]

    def live_ids(self, sf: SaveFile) -> list[str]:
        ids = [k for k, v in self._active(sf).items() if v["phase"] in LIVE_PHASES]
        ids += [e["key"] for e in self._info(sf) if e["key"] not in ids]
        return ids

    def _area_ranks(self, sf: SaveFile) -> dict[str, int]:
        return {a["key"]: a["value"]["releaseAreaRank"] for a in sf.sd["m_HugeMapStatusP"]["areaStatus"]}

    def _unmet(self, sf: SaveFile, ev: dict, ctx: dict) -> list[str]:
        out = []
        for c in ev["conds"]:
            t = c["type"]
            if t == "period" and ctx["period"] != c["period"]:
                out.append(f"{PERIOD[c['period']]} only")
            elif t == "area" and ctx["areas"].get(c["area"], 0) < c["rank"]:
                out.append(f"{self.areas.get(c['area'], c['area'])} rank {c['rank']}")
            elif t == "rank" and ctx["ranks"].get(c["life"], 0) < c["rank"]:
                out.append(f"{c['life']} license rank {c['rank']}")
            elif t == "weather" and c["weather"] not in ctx["weather"]:
                out.append(f"{WEATHER.get(c['weather'], c['weather'])} weather")
            elif t == "flag":
                idx = self.flags.get(c["flag"])
                if idx is None or not ctx["gflags"][idx]:
                    out.append(f"story flag {c['flag']}")
            elif t not in ("period", "area", "rank", "weather", "flag"):
                out.append(t)
        return out

    def _ctx(self, sf: SaveFile, period: int | None = None) -> dict:
        return {"period": self._env(sf)["gameTimePeriodType"] if period is None else period,
                "areas": self._area_ranks(sf), "ranks": {l["id"]: l["rank"] for l in sf.lives()},
                "weather": {w["weatherType"] for w in sf.sd["m_WeatherStatus"]["WeatherInfo"]},
                "gflags": sf.sd["m_FlagStatus"]["GlobalBitFlag"]}

    def time(self, sf: SaveFile) -> dict:
        env = self._env(sf)
        gt = env["gameTime"]
        minute = int(gt) % DAY_MINUTES
        return {"gameTime": gt, "day": int(gt // DAY_MINUTES) + 1, "hour": minute // 60, "minute": minute % 60,
                "period": env["gameTimePeriodType"],
                "weather": [w["weatherType"] for w in sf.sd["m_WeatherStatus"]["WeatherInfo"]]}

    def state(self, sf: SaveFile) -> dict:
        active = self._active(sf)
        info = {e["key"]: e["value"]["timePeriodChangeCount"] for e in self._info(sf)}
        ctx = self._ctx(sf)
        live = [{"id": i, "phase": active.get(i, {}).get("phase", 0), "count": info.get(i)}
                for i in self.live_ids(sf)]
        cleared = sorted(k for k, v in active.items() if v["phase"] in (254, 255))
        unmet = {eid: u for eid, ev in self.events.items() if (u := self._unmet(sf, ev, ctx))}
        areas = [{"id": a, "name": self.areas.get(a, a), "rank": r} for a, r in ctx["areas"].items()]
        return {"live": live, "cleared": cleared, "unmet": unmet, "time": self.time(sf), "areas": areas,
                "mapSize": MAP_SIZE}

    # ---- edits -----------------------------------------------------------------
    def _set_phase(self, sf: SaveFile, eid: str, phase: int) -> None:
        for e in self._quest(sf)["Active"]:
            if e["key"] == eid:
                e["value"]["phase"] = phase
                e["value"]["tmpFlagList"] = []
                if phase == 1:
                    e["value"]["isNew"] = 1
                return
        raise SaveFileError(f"{eid} is not in the save's event list")

    def dismiss(self, sf: SaveFile, ids: list[str]) -> None:
        ids = set(ids)
        for eid in ids:
            if eid in self._active(sf):
                self._set_phase(sf, eid, 0)
        q = self._quest(sf)
        q["ActiveEventInfo"] = [e for e in q["ActiveEventInfo"] if e["key"] not in ids]
        sf.dirty = True

    def emerge(self, sf: SaveFile, ids: list[str]) -> list[str]:
        """Put events on the map; an event already live at the same place is taken off. Returns removed ids."""
        removed = []
        for eid in ids:
            ev = self.events.get(eid)
            if ev is None:
                raise SaveFileError(f"unknown map event {eid}")
            clash = [i for i in self.live_ids(sf) if i != eid and self.events.get(i, {}).get("place") == ev["place"]]
            if clash:
                self.dismiss(sf, clash)
                removed += clash
            self._set_phase(sf, eid, 1)
            info = self._info(sf)
            if not any(e["key"] == eid for e in info):
                info.append({"key": eid, "value": {"timePeriodChangeCount": 0}})
        sf.dirty = True
        return removed

    def clear(self, sf: SaveFile) -> None:
        self.dismiss(sf, self.live_ids(sf))

    def reset_progress(self, sf: SaveFile) -> int:
        """Cleared events (phase 254/255) back to 0 so the draw can pick their places again."""
        n = 0
        for e in self._quest(sf)["Active"]:
            if e["value"]["phase"] in (254, 255):
                e["value"]["phase"], e["value"]["tmpFlagList"] = 0, []
                n += 1
        if n:
            sf.dirty = True
        return n

    def draw(self, sf: SaveFile, count: int = MAP_SIZE, rules: bool = True, cats: list[str] | None = None,
             seed: int | None = None) -> list[str]:
        """Clear the map and draw `count` events with the game's weights: one per place, one legendary at most.

        rules=False ignores conditions (time of day, area rank, weather, story flags). `cats` limits the pool.
        """
        rng = random.Random(seed)
        ctx = self._ctx(sf)
        known = self._active(sf)
        pool = [ev for ev in self.events.values() if ev["id"] in known and known[ev["id"]]["phase"] not in (254, 255)
                and (not cats or ev["cat"] in cats) and (not rules or not self._unmet(sf, ev, ctx))]
        picked, legendary = [], False
        while pool and len(picked) < count:
            ev = rng.choices(pool, weights=[e["rate"] for e in pool])[0]
            pool = [e for e in pool if e["place"] != ev["place"]]
            if ev["cat"] == "legendary":
                if legendary:
                    continue
                legendary = True
            picked.append(ev["id"])
        self.clear(sf)
        self.emerge(sf, picked)
        return picked

    def set_time(self, sf: SaveFile, hour: int, minute: int, period: int | None = None) -> None:
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise SaveFileError("time must be 00:00-23:59")
        env = self._env(sf)
        day = int(env["gameTime"] // DAY_MINUTES)
        env["gameTime"] = float(day * DAY_MINUTES + hour * 60 + minute)
        if period is not None:
            if period not in PERIOD:
                raise SaveFileError("period must be 0 (Day) or 1 (Night)")
            env["gameTimePeriodType"] = period
        sf.dirty = True

    def set_weather(self, sf: SaveFile, weather: int) -> None:
        if weather not in WEATHER:
            raise SaveFileError("weather must be 1 Sunny, 2 Rainy or 3 Cloudy")
        for w in sf.sd["m_WeatherStatus"]["WeatherInfo"]:
            w["weatherType"] = weather
        sf.dirty = True
