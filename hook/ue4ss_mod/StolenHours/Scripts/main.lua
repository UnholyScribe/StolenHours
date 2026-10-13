-- Stolen Hours live controller (UE4SS Lua mod).
-- Mailbox: %LOCALAPPDATA%\StolenHours\live\  (cmd.txt in, ack.txt out, heartbeat.txt)
-- Command line format: <id>\t<VERB>\t<arg>...   Reply: <id>\tOK|ERR\t<text>
-- All object access runs inside ExecuteInGameThread; the polling loop only touches files.

local LIVE_DIR = (os.getenv("LOCALAPPDATA") or ".") .. "\\StolenHours\\live\\"
local CMD = LIVE_DIR .. "cmd.txt"
local ACK = LIVE_DIR .. "ack.txt"
local HEARTBEAT = LIVE_DIR .. "heartbeat.txt"
local VERSION = "0.5.0"
local busy = false
local Dump = require("stolenhours_dump")

local function split_tabs(s)
    local out = {}
    for field in (s .. "\t"):gmatch("([^\t]*)\t") do out[#out + 1] = field end
    return out
end

local function write_file(path, text)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, "wb")
    if not f then return false end
    f:write(text)
    f:close()
    os.remove(path)
    return os.rename(tmp, path)
end

local function clean(s)
    return (tostring(s):gsub("[\t\r\n]", " "))
end

local function reply(id, ok, text)
    write_file(ACK, id .. "\t" .. (ok and "OK" or "ERR") .. "\t" .. clean(text or ""))
end

local function to_text(v)
    local t = type(v)
    if t == "number" or t == "boolean" or t == "string" or t == "nil" then return tostring(v) end
    if t == "userdata" or t == "table" then
        if v.ToString then
            local ok, s = pcall(function() return v:ToString() end)
            if ok then return s end
        end
        if v.GetFullName then
            local ok, s = pcall(function() return v:GetFullName() end)
            if ok then return s end
        end
    end
    return "<" .. t .. ">"
end

-- target: full object path (contains a space or '/') or a short class name for FindFirstOf
local function resolve(target)
    local obj
    if target:find("/", 1, true) then
        local path = target:match("^%S+%s+(.+)$") or target
        obj = StaticFindObject(path)
    else
        obj = FindFirstOf(target)
    end
    if obj and obj:IsValid() then return obj end
    return nil
end

local handlers = {}

handlers.PING = function()
    return true, "pong StolenHours " .. VERSION
end

-- FIND_PROP <PropertyName> : classes that declare it, plus live instances and values (max 50 lines)
handlers.FIND_PROP = function(args)
    local want = args[1]
    if not want or want == "" then return false, "usage: FIND_PROP <name>" end
    local class_class = StaticFindObject("/Script/CoreUObject.Class")
    if not class_class or not class_class:IsValid() then return false, "engine not ready" end
    local struct_class = StaticFindObject("/Script/CoreUObject.ScriptStruct")
    local lines, classes = {}, {}
    ForEachUObject(function(obj)
        local is_class = obj:IsA(class_class)
        local is_struct = struct_class and struct_class:IsValid() and obj:IsA(struct_class)
        if is_class or is_struct then
            obj:ForEachProperty(function(prop)
                if prop:GetFName():ToString() == want then
                    if is_class then
                        classes[#classes + 1] = obj
                    else
                        lines[#lines + 1] = "struct " .. obj:GetFullName() .. " (values: use DUMP)"
                    end
                end
            end)
        end
    end)
    for _, cls in ipairs(classes) do
        local short = cls:GetFName():ToString()
        lines[#lines + 1] = "class " .. cls:GetFullName()
        local insts = FindAllOf(short) or {}
        for _, inst in ipairs(insts) do
            if #lines >= 50 then break end
            local name = inst:GetFullName()
            if not name:find("Default__", 1, true) then
                lines[#lines + 1] = "  " .. name .. " = " .. to_text(inst:GetPropertyValue(want))
            end
        end
    end
    if #lines == 0 then return false, "no reflected class declares " .. want end
    return true, table.concat(lines, " | ")
end

-- Property paths: "Money", "m_permanent.Money", "m_permanent.m_stAvatarP[0].m_name" (array indexes are 0-based)
local function parse_path(path)
    local segs = {}
    for seg in tostring(path):gmatch("[^%.]+") do
        local name, idx = seg:match("^([^%[]+)%[(%d+)%]$")
        if name then
            segs[#segs + 1] = { key = name }
            segs[#segs + 1] = { index = tonumber(idx) + 1 }
        else
            segs[#segs + 1] = { key = seg }
        end
    end
    return segs
end

local function step(container, seg)
    if seg.index then
        if container.GetArrayNum and seg.index > container:GetArrayNum() then error("index out of range") end
        local v = container[seg.index]
        if type(v) == "table" and v.get then v = v:get() end
        return v
    end
    return container[seg.key]
end

-- Returns the container holding the last segment, and that segment.
local function walk(obj, path)
    local segs = parse_path(path)
    if #segs == 0 then error("empty property path") end
    local cur = obj
    for i = 1, #segs - 1 do
        cur = step(cur, segs[i])
        if cur == nil then error("path breaks at segment " .. i) end
    end
    return cur, segs[#segs]
end

local function read_path(obj, path)
    local c, last = walk(obj, path)
    return step(c, last)
end

-- GET <target> <path>
handlers.GET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    return true, to_text(read_path(obj, args[2] or ""))
end

-- SET <target> <path> <number|true|false> : writes, then re-reads through a fresh walk to prove it stuck
handlers.SET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local raw = args[3]
    local value
    if raw == "true" then value = true elseif raw == "false" then value = false else value = tonumber(raw) end
    if value == nil then return false, "only numeric/bool values are supported" end
    local c, last = walk(obj, args[2] or "")
    if last.index then return false, "cannot assign a whole array element" end
    local before = to_text(c[last.key])
    c[last.key] = value
    local after = to_text(read_path(obj, args[2]))
    if after ~= to_text(value) then
        return false, "write did not stick: before " .. before .. ", wrote " .. tostring(value) .. ", now " .. after
    end
    return true, before .. " -> " .. after
end

-- PROBE <target> <path> : Lua type of the value and which container methods this UE4SS build offers on it
handlers.PROBE = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local v = read_path(obj, args[2] or "")
    local parts = { "type=" .. type(v) }
    if type(v) == "userdata" then
        local okt, tn = pcall(function() return v:type() end)
        if okt and tn then parts[#parts + 1] = "ue4ss=" .. tostring(tn) end
        for _, m in ipairs({ "ForEach", "Find", "Add", "Remove", "Contains", "Empty", "GetArrayNum", "IsValid" }) do
            local ok, f = pcall(function() return v[m] end)
            if ok and f ~= nil then parts[#parts + 1] = m end
        end
    else
        parts[#parts + 1] = "value=" .. to_text(v)
    end
    return true, table.concat(parts, " ")
end

-- MAP_KEYS <target> <path> : keys of a TMap / TSet (needs ForEach on this UE4SS build; max 400)
handlers.MAP_KEYS = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local v = read_path(obj, args[2] or "")
    if type(v) ~= "userdata" then return false, "not a container: " .. type(v) end
    local okf, each = pcall(function() return v.ForEach end)
    if not okf or each == nil then return false, "this UE4SS build has no ForEach on " .. (args[2] or "") end
    local keys = {}
    v:ForEach(function(k)
        if #keys < 400 then
            if type(k) == "userdata" and k.get then k = k:get() end
            keys[#keys + 1] = to_text(k)
        end
    end)
    return true, #keys .. ": " .. table.concat(keys, ",")
end

local function unwrap(v)
    if type(v) == "userdata" or type(v) == "table" then
        local ok, inner = pcall(function() return v:get() end)
        if ok and inner ~= nil then return inner end
    end
    return v
end

local function field(v, names)
    for _, n in ipairs(names) do
        local ok, x = pcall(function() return v[n] end)
        if ok and x ~= nil then return unwrap(x) end
    end
    return nil
end

-- EVENTS : map events in play. "<id>:<phase>,..." from m_permanent.Active (phase 1-3), then ids only listed in
-- m_volatile.ActiveEventStatusV.openActiveEventList as "<id>:open". Element layout of that list is UNVERIFIED,
-- so it tries the likely id fields and falls back to the element's text.
handlers.EVENTS = function()
    local qs = resolve("GDDQuestStatus")
    if not qs then return false, "GDDQuestStatus not found (is a save loaded?)" end
    local out, seen, notes = {}, {}, {}
    local function add(id, phase)
        if id and id ~= "" and id ~= "None" and not seen[id] then
            seen[id] = true
            out[#out + 1] = id .. ":" .. phase
        end
    end
    local ok, err = pcall(function()
        unwrap(read_path(qs, "m_permanent.Active")):ForEach(function(k, v)
            local phase = tonumber(to_text(field(unwrap(v), { "phase", "Phase" })))
            if phase and phase >= 1 and phase <= 3 then add(to_text(unwrap(k)), phase) end
        end)
    end)
    if not ok then notes[#notes + 1] = "Active: " .. tostring(err) end
    ok, err = pcall(function()
        unwrap(read_path(qs, "m_volatile.ActiveEventStatusV.openActiveEventList")):ForEach(function(_, e)
            e = unwrap(e)
            local boxed = type(e) == "userdata" or type(e) == "table"
            local id = boxed and field(e, { "activeEventId", "questId", "ID", "id", "eventId" }) or e
            add(to_text(id), "open")
        end)
    end)
    if not ok then notes[#notes + 1] = "open list: " .. tostring(err) end
    local text = #out .. "|" .. table.concat(out, ",")
    if #notes > 0 then text = text .. "|" .. table.concat(notes, "; ") end
    return true, text
end

-- PLAYER : "<X>,<Y>,<Z>,<yaw>,<map>" of the local player's pawn
handlers.PLAYER = function()
    local pc = FindFirstOf("PlayerController")
    if not pc or not pc:IsValid() then return false, "no player controller" end
    local pawn = pc.Pawn
    if not pawn or not pawn:IsValid() then pawn = pc.AcknowledgedPawn end
    if not pawn or not pawn:IsValid() then return false, "no player pawn (loading or in a menu?)" end
    local loc, rot = pawn:K2_GetActorLocation(), pawn:K2_GetActorRotation()
    local map = pawn:GetFullName():match("(Map_%d+)") or "?"
    return true, string.format("%.1f,%.1f,%.1f,%.1f,%s", loc.X, loc.Y, loc.Z, rot.Yaw, map)
end

-- LIST_PROPS <target> : property names and current values of one object
handlers.LIST_PROPS = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local lines = { obj:GetFullName() }
    obj:GetClass():ForEachProperty(function(prop)
        local n = prop:GetFName():ToString()
        lines[#lines + 1] = n .. "=" .. to_text(obj:GetPropertyValue(n))
    end)
    return true, table.concat(lines, " | ")
end

-- DUMP : values + schema files in %LOCALAPPDATA%\StolenHours\dumps\
handlers.DUMP = function()
    local stamp = os.date("%Y%m%d_%H%M%S")
    local ok1, r1 = Dump.values(stamp)
    local ok2, r2 = Dump.schema(stamp)
    return ok1 and ok2, "values " .. r1 .. " | schema " .. r2
end

-- Run outside the game thread (UE4SS's own dumpers manage their own threading).
local async_handlers = {
    DUMP_BUILTIN = function() return Dump.builtin() end,
}

local function dispatch(line)
    local f = split_tabs(line)
    local id, verb = f[1] or "?", f[2] or ""
    local args = {}
    for i = 3, #f do args[#args + 1] = f[i] end
    if async_handlers[verb] then
        local ok, res, text = pcall(async_handlers[verb], args)
        if ok then reply(id, res, text) else reply(id, false, res) end
        busy = false
        return
    end
    local h = handlers[verb]
    if not h then
        reply(id, false, "unknown command " .. verb)
        busy = false
        return
    end
    ExecuteInGameThread(function()
        local ok, res, text = pcall(h, args)
        if not ok then
            reply(id, false, res)
        else
            reply(id, res, text)
        end
        busy = false
    end)
end

-- The editor creates LIVE_DIR; until it exists every file operation here simply fails.
local beat = 0
LoopAsync(200, function()
    beat = beat + 1
    if beat % 5 == 0 then write_file(HEARTBEAT, tostring(os.time())) end
    if busy then return false end
    local f = io.open(CMD, "rb")
    if not f then return false end
    local line = f:read("l")
    f:close()
    os.remove(CMD)
    if line then line = line:gsub("\r+$", "") end
    if line and line ~= "" then
        busy = true
        dispatch(line)
    end
    return false
end)

-- Ctrl+F9 in game: same as the DUMP command, result goes to UE4SS.log.
RegisterKeyBind(Key.F9, { ModifierKey.CONTROL }, function()
    ExecuteInGameThread(function()
        local ok, res, text = pcall(handlers.DUMP)
        print("[StolenHours] Ctrl+F9 dump: " .. tostring(ok and text or res) .. "\n")
    end)
end)

print("[StolenHours] live controller " .. VERSION .. " polling " .. LIVE_DIR .. "\n")
