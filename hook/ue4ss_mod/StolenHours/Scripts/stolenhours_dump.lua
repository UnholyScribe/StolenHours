-- Dumps for Stolen Hours. Output goes to %LOCALAPPDATA%\StolenHours\dumps\ (the editor creates it).
--   values_<t>.txt : every live object whose class is game code (/Script/DP1Project.*) or a /Game/ Blueprint,
--                    with property values; plus GameInstance, PlayerController, Pawn, GameState incl. engine fields
--   schema_<t>.txt : every DP1Project class / struct / enum with property offsets and types
-- Value walks must run on the game thread; the caller wraps them in ExecuteInGameThread.

local M = {}

local MAX_ARRAY = 64
local MAX_DEPTH = 3
local GAME_MARKERS = { "/Script/DP1Project.", " /Game/" }

M.DIR = (os.getenv("LOCALAPPDATA") or ".") .. "\\StolenHours\\dumps\\"

local function is_game_path(path)
    for _, m in ipairs(GAME_MARKERS) do
        if path:find(m, 1, true) then return true end
    end
    return false
end

-- UI widgets and animation objects are skipped entirely: a widget (NumPrimitive.m_basePanel) held a garbage
-- object pointer and reading it crashed the game (2026-10-11). pcall cannot catch native access violations.
local UNSAFE_SUPERS = {
    "/Script/UMG.", "/Script/SlateCore.", "/Script/Slate.",
    "/Script/Engine.AnimInstance", "/Script/Engine.AnimNotify", "/Script/Engine.AnimNotifyState",
}

local unsafe_cache = {}
local function class_is_unsafe(cls)
    local key = cls:GetFullName()
    if unsafe_cache[key] ~= nil then return unsafe_cache[key] end
    local bad = false
    local c = cls
    while c and c:IsValid() do
        local p = c:GetFullName()
        for _, m in ipairs(UNSAFE_SUPERS) do
            if p:find(m, 1, true) then bad = true break end
        end
        if bad then break end
        c = c:GetSuperStruct()
    end
    unsafe_cache[key] = bad
    return bad
end
M.class_is_unsafe = class_is_unsafe

local function clean(s)
    return (tostring(s):gsub("[\r\n\t]", " "))
end

local function ptype(p)
    return p:GetClass():GetFName():ToString()
end

local NUMERIC = {
    Int8Property = true, Int16Property = true, IntProperty = true, Int64Property = true,
    UInt16Property = true, UInt32Property = true, UInt64Property = true, ByteProperty = true,
    FloatProperty = true, DoubleProperty = true, BoolProperty = true,
}

local fmt_raw

local function fmt_struct(v, struct, depth)
    if depth >= MAX_DEPTH then return "{...}" end
    local parts = {}
    local s = struct
    while s and s:IsValid() do
        s:ForEachProperty(function(sp)
            local n = sp:GetFName():ToString()
            local ok, sv = pcall(function() return v[n] end)
            parts[#parts + 1] = n .. "=" .. (ok and fmt_raw(sv, sp, depth + 1) or "<err>")
        end)
        s = s:GetSuperStruct()
    end
    return "{" .. table.concat(parts, ", ") .. "}"
end

fmt_raw = function(v, p, depth)
    local ok, out = pcall(function()
        local t = ptype(p)
        if v == nil then return "nil" end
        if NUMERIC[t] then return tostring(v) end
        if t == "StrProperty" or t == "NameProperty" or t == "TextProperty" then
            return '"' .. clean(v:ToString()) .. '"'
        end
        if t == "EnumProperty" then
            local okn, name = pcall(function() return p:GetEnum():GetNameByValue(v):ToString() end)
            return (okn and name or "?") .. "(" .. tostring(v) .. ")"
        end
        if t == "ObjectProperty" or t == "ClassProperty" or t == "WeakObjectProperty"
            or t == "SoftObjectProperty" or t == "LazyObjectProperty" or t == "InterfaceProperty" then
            if (type(v) == "userdata" or type(v) == "table") and v.IsValid and v:IsValid() then
                return v:GetFullName()
            end
            return "None"
        end
        if t == "StructProperty" then
            return fmt_struct(v, p:GetStruct(), depth)
        end
        if t == "ArrayProperty" then
            local inner = p:GetInner()
            local n = v:GetArrayNum()
            local parts = {}
            v:ForEach(function(i, elem)
                if i <= MAX_ARRAY then
                    parts[#parts + 1] = fmt_raw(elem:get(), inner, depth + 1)
                end
            end)
            local more = n > MAX_ARRAY and (", ... +" .. (n - MAX_ARRAY)) or ""
            return "[" .. n .. "][" .. table.concat(parts, ", ") .. more .. "]"
        end
        return "<" .. t .. ">"
    end)
    return ok and out or "<err>"
end

local Writer = {}
Writer.__index = Writer

function Writer.open(path)
    local f = io.open(path, "wb")
    if not f then return nil end
    return setmetatable({ f = f, buf = {}, path = path }, Writer)
end

function Writer:line(s)
    self.buf[#self.buf + 1] = s
    if #self.buf >= 2000 then self:flush() end
end

function Writer:flush()
    if #self.buf > 0 then
        self.f:write(table.concat(self.buf, "\n"), "\n")
        self.buf = {}
    end
end

function Writer:close()
    self:flush()
    self.f:close()
end

local function dump_object(w, obj, full, include_engine)
    w:line("=== " .. full)
    local c = obj:GetClass()
    while c and c:IsValid() do
        local cpath = c:GetFullName()
        if not include_engine and not is_game_path(cpath) then break end
        w:line("  -- " .. cpath)
        c:ForEachProperty(function(p)
            local okl, line = pcall(function()
                local n = p:GetFName():ToString()
                local okv, v = pcall(function() return obj[n] end)
                return string.format("  0x%04X %s %s = %s", p:GetOffset_Internal(), ptype(p), n,
                    okv and fmt_raw(v, p, 0) or "<err>")
            end)
            w:line(okl and line or "  <property error>")
        end)
        c = c:GetSuperStruct()
    end
end

function M.values(stamp)
    local path = M.DIR .. "values_" .. stamp .. ".txt"
    local w = Writer.open(path)
    if not w then return false, "cannot write " .. path .. " (does the dumps folder exist?)" end
    w:line("# StolenHours value dump " .. os.date("%Y-%m-%d %H:%M:%S"))

    local count, errors = 0, 0
    local okh, UEHelpers = pcall(require, "UEHelpers")
    if okh then
        for _, getter in ipairs({ "GetGameInstance", "GetPlayerController", "GetPlayer", "GetGameStateBase",
                                  "GetGameModeBase" }) do
            local okg, obj = pcall(function() return UEHelpers[getter]() end)
            if okg and obj and obj:IsValid() then
                w:line("# singleton " .. getter)
                dump_object(w, obj, obj:GetFullName(), true)
                count = count + 1
            end
        end
    end

    -- Pass 1: the GDD* game-data objects (the live copy of the save), flushed right away.
    -- Pass 2: other game-code objects, minus UI and animation.
    local skipped = 0
    for pass = 1, 2 do
        w:line("# pass " .. pass .. (pass == 1 and " game data (GDD*)" or " other game objects"))
        ForEachUObject(function(obj)
            local ok = pcall(function()
                local cls = obj:GetClass()
                if not cls or not cls:IsValid() then return end
                local cpath = cls:GetFullName()
                if not is_game_path(cpath) then return end
                local is_gdd = cpath:find("/Script/DP1Project.GDD", 1, true) ~= nil
                if (pass == 1) ~= is_gdd then return end
                local full = obj:GetFullName()
                if full:find("Default__", 1, true) or full:find("REINST_", 1, true) then return end
                if not is_gdd and (full:find("WidgetTree", 1, true) or class_is_unsafe(cls)) then
                    skipped = skipped + 1
                    return
                end
                dump_object(w, obj, full, false)
                count = count + 1
                if is_gdd then w:flush() end
            end)
            if not ok then errors = errors + 1 end
        end)
        w:flush()
    end
    w:line("# objects " .. count .. ", errors " .. errors .. ", skipped UI/anim " .. skipped)
    w:close()
    return true, path .. " (" .. count .. " objects, " .. errors .. " errors)"
end

function M.schema(stamp)
    local path = M.DIR .. "schema_" .. stamp .. ".txt"
    local w = Writer.open(path)
    if not w then return false, "cannot write " .. path end
    local n = 0
    ForEachUObject(function(obj)
        pcall(function()
            local full = obj:GetFullName()
            if not full:find(" /Script/DP1Project.", 1, true) then return end
            local kind = full:match("^(%S+)")
            if kind == "Class" or kind == "ScriptStruct" then
                local super = obj:GetSuperStruct()
                w:line("=== " .. full .. ((super and super:IsValid()) and (" : " .. super:GetFullName()) or ""))
                obj:ForEachProperty(function(p)
                    local extra = ""
                    local t = ptype(p)
                    pcall(function()
                        if t == "StructProperty" then extra = " (" .. p:GetStruct():GetFullName() .. ")"
                        elseif t == "ObjectProperty" then extra = " (" .. p:GetPropertyClass():GetFullName() .. ")"
                        elseif t == "ArrayProperty" then extra = " (of " .. ptype(p:GetInner()) .. ")"
                        elseif t == "EnumProperty" then extra = " (" .. p:GetEnum():GetFullName() .. ")" end
                    end)
                    w:line(string.format("  0x%04X %s %s%s", p:GetOffset_Internal(), t, p:GetFName():ToString(), extra))
                end)
                n = n + 1
            elseif kind == "Enum" then
                w:line("=== " .. full)
                obj:ForEachName(function(name, value)
                    w:line("  " .. name:ToString() .. " = " .. tostring(value))
                end)
                n = n + 1
            end
        end)
    end)
    w:close()
    return true, path .. " (" .. n .. " types)"
end

-- UE4SS built-in dumpers; they write into the ue4ss folder next to the game exe. Not on the game thread.
function M.builtin()
    local done = {}
    for _, fn in ipairs({ "DumpAllObjects", "GenerateSDK", "DumpUSMAP" }) do
        local f = _G[fn]
        if type(f) == "function" then
            local ok, err = pcall(f)
            done[#done + 1] = fn .. (ok and " ok" or (" failed: " .. clean(err)))
        else
            done[#done + 1] = fn .. " unavailable"
        end
    end
    return true, table.concat(done, "; ") .. " (output in Game\\Binaries\\Win64\\ue4ss\\)"
end

return M
