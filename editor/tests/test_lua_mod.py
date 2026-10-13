"""Runs the real StolenHours Lua mod in Lua 5.4 (lupa) against a mocked UE4SS API (lua_mock.lua)."""

from pathlib import Path

import pytest

lua54 = pytest.importorskip("lupa.lua54")

from stolenhours import dumpscan, paths  # noqa: E402

TESTS = Path(__file__).parent
SCRIPTS = paths.PROJECT_ROOT / "hook" / "ue4ss_mod" / "StolenHours" / "Scripts"

WORLD = r'''
local P = MOCK.prop
local lifeEnum = MOCK.class("Enum /Script/DP1Project.ELifeType", {}, nil, {{"Paladin", 1}, {"Miner", 5}})
local statusStruct = MOCK.class("ScriptStruct /Script/DP1Project.FLifeStatus",
    { P("Lv", "IntProperty", 0), P("Exp", "IntProperty", 4) })
local base = MOCK.class("Class /Script/Engine.GameInstance", { P("EngineThing", "IntProperty", 0x28) })
local giClass = MOCK.class("Class /Script/DP1Project.DP1GameInstance", {
    P("Money", "IntProperty", 0x310),
    P("PlayerName", "StrProperty", 0x318),
    P("CurrentLife", "EnumProperty", 0x328, { enum = lifeEnum }),
    P("Status", "StructProperty", 0x330, { struct = statusStruct }),
    P("Levels", "ArrayProperty", 0x340, { inner = P("Levels", "IntProperty", 0) }),
    P("Owner", "ObjectProperty", 0x350),
}, base)
local gi = MOCK.object("DP1GameInstance /Engine/Transient.DP1GameInstance_0", giClass, {
    Money = 14633, PlayerName = MOCK.fstring("N30Killer"), CurrentLife = 5,
    Status = MOCK.structval({ Lv = 11, Exp = 221 }), Levels = MOCK.array({ 11, 1, 0 }), EngineThing = 7,
})
gi._values.Owner = gi
MOCK.object("DP1GameInstance /Script/DP1Project.Default__DP1GameInstance", giClass, { Money = 0 })
local playStruct = MOCK.class("ScriptStruct /Script/DP1Project.PLAY_DATA_P", { P("Money", "IntProperty", 0x40) })
local gddPlay = MOCK.class("Class /Script/DP1Project.GDDPlayData",
    { P("m_permanent", "StructProperty", 0x30, { struct = playStruct }) })
MOCK.object("GDDPlayData /Engine/Transient.GDDPlayData_1", gddPlay,
    { m_permanent = MOCK.structval({ Money = 14633 }) })
local umgWidget = MOCK.class("Class /Script/UMG.Widget", { P("Visibility", "IntProperty", 0) })
local numPrim = MOCK.class("Class /Script/DP1Project.NumPrimitive", { P("m_basePanel", "ObjectProperty", 0x418) }, umgWidget)
MOCK.object("NumPrimitive /Engine/Transient.Menu.WidgetTree_1.NumPrimitive_Stock", numPrim, {})
local engineOnly = MOCK.class("Class /Script/Engine.Actor", { P("Secret", "IntProperty", 0) })
MOCK.object("Actor /Game/Maps/Island.Island:PersistentLevel.Actor_1", engineOnly, { Secret = 999 })
MOCK.game_instance = gi
'''


@pytest.fixture
def mod(tmp_path):
    rt = lua54.LuaRuntime(unpack_returned_tuples=True)
    local = str(tmp_path).replace("\\", "\\\\")
    rt.execute(f'os.getenv = function(k) if k == "LOCALAPPDATA" then return "{local}" end end')
    rt.execute((TESTS / "lua_mock.lua").read_text(encoding="utf-8"))
    rt.execute(WORLD)
    rt.execute(f'package.path = "{str(SCRIPTS).replace(chr(92), "/")}/?.lua;" .. package.path')
    rt.execute((SCRIPTS / "main.lua").read_text(encoding="utf-8"))
    live = tmp_path / "StolenHours" / "live"
    dumps = tmp_path / "StolenHours" / "dumps"
    live.mkdir(parents=True)
    dumps.mkdir(parents=True)
    tick = rt.eval("MOCK.loops[1]")

    def send(line):
        (live / "cmd.txt").write_text(line + "\n", encoding="utf-8")
        tick()
        return (live / "ack.txt").read_text(encoding="utf-8").split("\t", 2)

    return rt, send, dumps, tick, live


def test_ping_and_unknown(mod):
    _, send, *_ = mod
    assert send("a1\tPING") == ["a1", "OK", "pong StolenHours 0.5.0"]
    assert send("a2\tNOPE")[1] == "ERR"


def test_probe_and_map_keys(mod):
    _, send, *_ = mod
    assert send("p1\tPROBE\tGDDPlayData\tm_permanent.Money") == ["p1", "OK", "type=number value=14633"]
    r = send("p2\tMAP_KEYS\tGDDPlayData\tm_permanent.Money")
    assert r[1] == "ERR" and "not a container" in r[2]
    assert send("p3\tPROBE\tNoSuchThing\tx")[1] == "ERR"


def test_heartbeat(mod):
    _, _, _, tick, live = mod
    for _ in range(5):
        tick()
    assert (live / "heartbeat.txt").exists()


def test_find_get_set(mod):
    _, send, *_ = mod
    r = send("b1\tFIND_PROP\tMoney")
    assert r[1] == "OK" and "DP1GameInstance_0 = 14633" in r[2] and "Default__" not in r[2]
    path = "DP1GameInstance /Engine/Transient.DP1GameInstance_0"
    assert send(f"b2\tGET\t{path}\tMoney")[2] == "14633"
    assert send(f"b3\tSET\t{path}\tMoney\t500000")[2] == "14633 -> 500000"
    assert send("b4\tGET\tDP1GameInstance\tMoney")[2] == "500000"
    assert send(f"b5\tSET\t{path}\tMoney\tabc")[1] == "ERR"
    r = send("b6\tFIND_PROP\tLv")
    assert r[1] == "OK" and "struct ScriptStruct /Script/DP1Project.FLifeStatus" in r[2]


def test_nested_paths(mod):
    _, send, *_ = mod
    assert send("p1\tGET\tGDDPlayData\tm_permanent.Money")[2] == "14633"
    assert send("p2\tSET\tGDDPlayData\tm_permanent.Money\t99999")[2] == "14633 -> 99999"
    assert send("p3\tGET\tGDDPlayData\tm_permanent.Money")[2] == "99999"
    assert send("p4\tGET\tDP1GameInstance\tLevels[0]")[2] == "11"
    assert send("p5\tGET\tDP1GameInstance\tStatus.Exp")[2] == "221"
    assert send("p6\tGET\tDP1GameInstance\tLevels[9]")[1] == "ERR"
    assert send("p7\tGET\tGDDPlayData\tnope.Money")[1] == "ERR"


def test_set_reports_write_that_did_not_stick(mod):
    rt, send, *_ = mod
    # a struct accessor that hands out copies: the write is lost and SET must say so
    rt.execute('''
        local o = FindFirstOf("GDDPlayData")
        local store = { Money = 5 }
        o._values.m_permanent = nil
        setmetatable(o._values, { __index = function(_, k)
            if k == "m_permanent" then return { Money = store.Money } end end })
    ''')
    r = send("q1\tSET\tGDDPlayData\tm_permanent.Money\t7")
    assert r[1] == "ERR" and "did not stick" in r[2]


def test_dump_values_and_schema(mod):
    _, send, dumps, *_ = mod
    r = send("c1\tDUMP")
    assert r[1] == "OK", r
    values = next(dumps.glob("values_*.txt")).read_text(encoding="utf-8")
    schema = next(dumps.glob("schema_*.txt")).read_text(encoding="utf-8")
    # singleton dump includes engine supers, game-object scan does not
    assert "# singleton GetGameInstance" in values and "EngineThing = 7" in values
    assert "0x0310 IntProperty Money = 14633" in values
    assert 'PlayerName = "N30Killer"' in values
    assert "CurrentLife = Miner(5)" in values
    assert "Status = {Lv=11, Exp=221}" in values
    assert "Levels = [3][11, 1, 0]" in values
    assert "Owner = DP1GameInstance /Engine/Transient.DP1GameInstance_0" in values
    assert "Default__" not in values and "Secret" not in values
    assert "NumPrimitive" not in values and "skipped UI/anim 1" in values
    assert values.index("GDDPlayData_1") < values.rindex("=== DP1GameInstance /Engine/Transient.DP1GameInstance_0")
    assert "m_permanent = {Money=14633}" in values
    assert "=== Class /Script/DP1Project.DP1GameInstance : Class /Script/Engine.GameInstance" in schema
    assert "0x0330 StructProperty Status (ScriptStruct /Script/DP1Project.FLifeStatus)" in schema
    assert "Miner = 5" in schema

    targets = {"Money": 14633, "character name": "N30Killer"}
    rep = dumpscan.analyze(next(dumps.glob("values_*.txt")), targets)
    assert {p.name for p in rep.hits["Money"]} == {"Money", "m_permanent"}
    assert {p.name for p in rep.hits["character name"]} == {"PlayerName"}


def test_ctrl_f9_keybind(mod):
    rt, _, dumps, *_ = mod
    kb = rt.eval("MOCK.keybinds[1]")
    assert kb.key == "F9" and kb.mods[1] == "CONTROL"
    kb.fn()
    assert list(dumps.glob("values_*.txt"))
    assert any("Ctrl+F9 dump" in str(s) for s in rt.eval("MOCK.printed").values())


QUESTS = r'''
local F = MOCK.fname
local qs = MOCK.class("Class /Script/DP1Project.GDDQuestStatus", {})
MOCK.object("GDDQuestStatus /Engine/Transient.GDDQuestStatus_0", qs, {
    m_permanent = { Active = MOCK.map({
        { F("qsf_active_event_001_01"), { phase = 1 } },
        { F("qsf_active_event_002_01"), { phase = 0 } },
        { F("qsf_active_event_003_01"), { phase = 254 } },
        { F("qsf_active_event_004_01"), { phase = 3 } },
    }) },
    m_volatile = { ActiveEventStatusV = { openActiveEventList = MOCK.array({
        { activeEventId = F("qsf_active_event_001_01") },
        { activeEventId = F("qsf_active_event_009_01") },
    }) } },
})
local pcClass = MOCK.class("Class /Script/Engine.PlayerController", {})
local pawnClass = MOCK.class("Class /Script/DP1Project.DP1PlayerCharacter", {})
local pawn = MOCK.object("BP_Player_C /Game/Maps/Map_200000/Map_200000.Map_200000:PersistentLevel.BP_Player_C_0",
    pawnClass, {
        K2_GetActorLocation = function() return { X = 53982.0, Y = 38430.0, Z = 400.0 } end,
        K2_GetActorRotation = function() return { Pitch = 0.0, Yaw = -90.0, Roll = 0.0 } end,
    })
MOCK.object("PlayerController /Game/Maps/Map_200000/Map_200000.Map_200000:PersistentLevel.PC_0", pcClass, { Pawn = pawn })
'''


def test_events_and_player(mod):
    rt, send, *_ = mod
    assert send("e0\tEVENTS")[1] == "ERR"
    assert send("e0\tPLAYER")[1] == "ERR"
    rt.execute(QUESTS)
    r = send("e1\tEVENTS")
    assert r[1] == "OK", r
    assert r[2] == "3|qsf_active_event_001_01:1,qsf_active_event_004_01:3,qsf_active_event_009_01:open"
    assert send("e2\tPLAYER") == ["e2", "OK", "53982.0,38430.0,400.0,-90.0,Map_200000"]


def test_events_reports_unreadable_lists(mod):
    rt, send, *_ = mod
    rt.execute('MOCK.object("GDDQuestStatus /Engine/Transient.GDDQuestStatus_0", '
               'MOCK.class("Class /Script/DP1Project.GDDQuestStatus", {}), { m_permanent = {} })')
    r = send("e1\tEVENTS")
    assert r[1] == "OK" and r[2].startswith("0||Active: ") and "open list: " in r[2]


def test_builtin_dumpers_missing_is_reported(mod):
    _, send, *_ = mod
    r = send("d1\tDUMP_BUILTIN")
    assert r[1] == "OK" and "DumpAllObjects unavailable" in r[2]
