import json

import pytest

from stolenhours import live, mapview, safety
from stolenhours.webgui import server

BUILT = mapview.OUT / "mapview.json"


def test_world_to_map_matches_the_minimap_bounds():
    assert mapview.world_to_map(0, 0) == {"u": 0.5, "v": 0.5}
    # map right is world -Y, map down is world +X
    assert mapview.world_to_map(120000, 0) == {"u": 0.5, "v": 1.0}
    assert mapview.world_to_map(0, -120000) == {"u": 1.0, "v": 0.5}


@pytest.mark.parametrize("title, etype, override, legendary, icon", [
    ("Take Down All Monsters!", 1, 0, False, 124),
    ("Hunt for the Legendary Monster", 1, 0, True, 130),
    ("Mining Mania!", 2, 0, False, 125),
    ("Hunt for the Legendary Tree", 2, 0, True, 132),
    ("Catch Every Fish!", 2, 0, False, 127),
    ("It's Harvest Time!", 2, 0, False, 128),
    ("I Need Iron Ore!", 3, 0, False, 129),
    ("Haniwa Festival", 4, 0, False, 219),
    ("Go see the race", 0, 124, False, 124),
])
def test_icon_rule(title, etype, override, legendary, icon):
    assert mapview.icon_type(title, etype, override, legendary) == icon


@pytest.mark.skipif(not BUILT.exists(), reason="map viewer not built")
def test_built_data_is_consistent():
    m = json.loads(BUILT.read_text(encoding="utf-8"))
    assert m["eventMap"] == "Map_200000"
    maps = {x["id"]: x for x in m["maps"]}
    assert set(mapview.WORLD_MAP_IDS) <= set(maps)
    cats = {c[0] for c in m["categories"]}
    for mid, x in maps.items():
        for k in x["markers"]:
            cat, icon, u, v, name = k[:5]
            assert cat in cats and name, (mid, k)
            assert -0.05 <= u <= 1.05 and -0.05 <= v <= 1.05, (mid, k)
            assert (mapview.OUT / "icons" / f"{icon}.png").exists(), (mid, k)
    world = maps["Map_200000"]["markers"]
    assert len([k for k in world if k[0] == "tower"]) == 15
    towns = {k[4] for k in world if k[0] == "town"}
    assert towns == {"Haniwa Hamlet", "Buffalo Base", "Tortortoise Town", "Simian Settlement", "Beetle Borough",
                     "Panther Preserve"}
    for eid, e in m["events"].items():
        assert 0 <= e["u"] <= 1 and 0 <= e["v"] <= 1, eid
        assert str(e["icon"]) in m["icons"] and str(e["glow"]) in m["icons"], eid
        assert (mapview.OUT / "icons" / f"{e['icon']}.png").exists()
    mat = m["activeEventMaterial"]
    assert mat["material"] == "mat_map_000012" and mat["parent"] == "basemat_ui_ripple_01"


class FakeBridge:
    def __init__(self, replies, alive=True):
        self.replies, self.alive = replies, alive

    def mod_alive(self):
        return self.alive

    def events(self):
        return self.replies["EVENTS"]

    def player(self):
        return self.replies["PLAYER"]


def _backend(bridge, monkeypatch):
    monkeypatch.setattr(safety, "running_game_processes", lambda: ["game.exe"])
    b = object.__new__(server.Backend)
    b.bridge = bridge
    return b


def test_live_snapshot_parses_mod_replies(monkeypatch):
    b = _backend(FakeBridge({"EVENTS": live.Reply(True, "2|qsf_active_event_001_01:1,abc:open"),
                             "PLAYER": live.Reply(True, "120000.0,0.0,5.0,90.0,Map_200000")}), monkeypatch)
    out = b.api_mapview_live()
    assert out["game"] and out["mod"]
    assert out["events"] == [{"id": "qsf_active_event_001_01", "phase": "1"}, {"id": "abc", "phase": "open"}]
    assert out["player"]["map"] == "Map_200000" and out["player"]["yaw"] == 90.0
    assert (out["player"]["u"], out["player"]["v"]) == (0.5, 1.0)
    assert out["notes"] == []


def test_live_snapshot_reports_partial_reads(monkeypatch):
    b = _backend(FakeBridge({"EVENTS": live.Reply(True, "0||open list: no ForEach"),
                             "PLAYER": live.Reply(False, "no player pawn")}), monkeypatch)
    out = b.api_mapview_live()
    assert out["events"] == [] and out["player"] is None
    assert out["notes"] == ["open list: no ForEach", "player: no player pawn"]


def test_live_snapshot_flags_an_old_mod(monkeypatch):
    b = _backend(FakeBridge({"EVENTS": live.Reply(False, "unknown command EVENTS")}), monkeypatch)
    out = b.api_mapview_live()
    assert out["needs_update"] and out["events"] is None


def test_live_snapshot_without_mod(monkeypatch):
    out = _backend(FakeBridge({}, alive=False), monkeypatch).api_mapview_live()
    assert out == {"game": True, "mod": False, "events": None, "player": None, "notes": []}
