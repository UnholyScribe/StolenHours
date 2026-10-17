-- Minimal stand-in for the UE4SS Lua API, enough to run the StolenHours mod outside the game.
-- Shapes follow the bundled UE4SS mods (dump_object.lua, Keybinds, UEHelpers); behaviour is simplified.

MOCK = { objects = {}, keybinds = {}, loops = {}, printed = {} }

local function fname(s) return { ToString = function() return s end } end
local function fstring(s) return { ToString = function() return s end } end
MOCK.fstring = fstring

Key = setmetatable({}, { __index = function(_, k) return k end })
ModifierKey = setmetatable({}, { __index = function(_, k) return k end })
function RegisterKeyBind(key, mods, fn) MOCK.keybinds[#MOCK.keybinds + 1] = { key = key, mods = mods, fn = fn } end
function LoopAsync(ms, fn) MOCK.loops[#MOCK.loops + 1] = fn end
function ExecuteInGameThread(fn) fn() end
print = function(s) MOCK.printed[#MOCK.printed + 1] = tostring(s) end

local Invalid = { IsValid = function() return false end }

function MOCK.prop(name, ptype, offset, extra)
    extra = extra or {}
    local p = {}
    p.GetFName = function() return fname(name) end
    p.GetClass = function() return { GetFName = function() return fname(ptype) end } end
    p.GetOffset_Internal = function() return offset end
    p.GetInner = function() return extra.inner end
    p.GetStruct = function() return extra.struct end
    p.GetEnum = function() return extra.enum end
    p.GetPropertyClass = function() return extra.pclass end
    return p
end

-- A UClass / UScriptStruct / UEnum
function MOCK.class(full, props, super, kind_names)
    local c = { props = props or {}, super = super }
    c.IsValid = function() return true end
    c.GetFullName = function() return full end
    c.GetFName = function() return fname(full:match("%.([^%.]+)$")) end
    c.GetSuperStruct = function() return c.super or Invalid end
    c.ForEachProperty = function(self, cb) for _, p in ipairs(c.props) do cb(p) end end
    c.ForEachName = function(self, cb) for _, nv in ipairs(kind_names or {}) do cb(fname(nv[1]), nv[2]) end end
    c.GetClass = function() return MOCK.ClassClass end
    c.IsA = function(self, other)
        return (other == MOCK.ClassClass and full:match("^Class ") ~= nil)
            or (other == MOCK.StructClass and full:match("^ScriptStruct ") ~= nil)
    end
    c.GetNameByValue = function(self, v)
        for _, nv in ipairs(kind_names or {}) do if nv[2] == v then return fname(nv[1]) end end
        return fname("?")
    end
    MOCK.objects[#MOCK.objects + 1] = c
    return c
end

MOCK.ClassClass = { IsValid = function() return true end, GetFullName = function() return "Class /Script/CoreUObject.Class" end }
MOCK.StructClass = { IsValid = function() return true end, GetFullName = function() return "Class /Script/CoreUObject.ScriptStruct" end }

-- A struct value: indexable by property name
function MOCK.structval(values) return values end

function MOCK.array(items)
    local a = {
        GetArrayNum = function() return #items end,
        ForEach = function(self, cb) for i, v in ipairs(items) do cb(i, { get = function() return v end }) end end,
    }
    return setmetatable(a, { __index = function(_, k) if type(k) == "number" then return items[k] end end })
end

-- A TMap: entries are {key, value}; ForEach hands out RemoteUnrealParam-like wrappers like UE4SS does
function MOCK.map(entries)
    return {
        ForEach = function(self, cb)
            for _, kv in ipairs(entries) do
                cb({ get = function() return kv[1] end }, { get = function() return kv[2] end })
            end
        end,
    }
end
MOCK.fname = fname

function MOCK.object(full, cls, values)
    local o = { _values = values or {} }
    local methods = {
        IsValid = function() return true end,
        GetFullName = function() return full end,
        GetClass = function() return cls end,
        IsA = function() return false end,
        GetPropertyValue = function(self, n) return self._values[n] end,
        SetPropertyValue = function(self, n, v) self._values[n] = v end,
    }
    setmetatable(o, { __index = function(t, k)
        if methods[k] then return methods[k] end
        return rawget(t, "_values")[k]
    end })
    MOCK.objects[#MOCK.objects + 1] = o
    return o
end

function ForEachUObject(cb)
    for i, o in ipairs(MOCK.objects) do cb(o, 0, i) end
end

function StaticFindObject(path)
    if path == "/Script/CoreUObject.Class" then return MOCK.ClassClass end
    if path == "/Script/CoreUObject.ScriptStruct" then return MOCK.StructClass end
    for _, o in ipairs(MOCK.objects) do
        local p = o:GetFullName():match("^%S+%s+(.+)$")
        if p == path then return o end
    end
    return Invalid
end

function FindAllOf(short)
    local out = {}
    for _, o in ipairs(MOCK.objects) do
        local cls = o.GetClass and o:GetClass()
        if cls and cls ~= MOCK.ClassClass and cls.GetFName and cls:GetFName():ToString() == short then
            out[#out + 1] = o
        end
    end
    return #out > 0 and out or nil
end

function FindFirstOf(short)
    local all = FindAllOf(short)
    return all and all[1] or Invalid
end

package.preload["UEHelpers"] = function()
    return {
        GetGameInstance = function() return MOCK.game_instance or Invalid end,
        GetPlayerController = function() return Invalid end,
        GetPlayer = function() return Invalid end,
        GetGameStateBase = function() return Invalid end,
        GetGameModeBase = function() return Invalid end,
    }
end
