-- Stolen Hours live controller (UE4SS Lua mod).
-- Mailbox: %LOCALAPPDATA%\StolenHours\live\  (cmd.txt in, ack.txt out, heartbeat.txt)
-- Command line format: <id>\t<VERB>\t<arg>...   Reply: <id>\tOK|ERR\t<text>
-- All object access runs inside ExecuteInGameThread; the polling loop only touches files.

local LIVE_DIR = (os.getenv("LOCALAPPDATA") or ".") .. "\\StolenHours\\live\\"
local CMD = LIVE_DIR .. "cmd.txt"
local ACK = LIVE_DIR .. "ack.txt"
local HEARTBEAT = LIVE_DIR .. "heartbeat.txt"
local VERSION = "0.8.1"
local busy = false
local Dump = require("stolenhours_dump")
local Camera = require("stolenhours_camera")
local Craft = require("stolenhours_craft")
local UEHelpers = require("UEHelpers")

local function make_fname(s)
    if not s or s == "" then return nil end
    return UEHelpers.FindOrAddFName(s)
end

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

-- SET <target> <path> <number|true|false|NAME:foo|string> : write + re-read proof
handlers.SET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local raw = args[3]
    local value
    if raw == "true" then value = true
    elseif raw == "false" then value = false
    elseif type(raw) == "string" and raw:sub(1, 5) == "NAME:" then
        value = make_fname(raw:sub(6))
        if not value then return false, "bad FName" end
    else
        local num = tonumber(raw)
        if num ~= nil then value = num
        elseif type(raw) == "string" and raw ~= "" then
            value = make_fname(raw)
            if not value then return false, "bad FName string" end
        end
    end
    if value == nil then return false, "usage: SET <target> <path> <num|bool|NAME:id|id>" end
    local c, last = walk(obj, args[2] or "")
    if last.index then return false, "cannot assign a whole array element" end
    local before = to_text(c[last.key])
    c[last.key] = value
    local after = to_text(read_path(obj, args[2]))
    local want = to_text(value)
    if after ~= want and not (type(raw) == "string" and after:find(raw, 1, true)) then
        return false, "write did not stick: before " .. before .. ", wrote " .. want .. ", now " .. after
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

-- TMap Find by FName only — never ForEach (Active map ForEach crashed live 2026-11-09).
local function map_find(map, want)
    if map == nil then return nil, "map nil" end
    if not map.Find then return nil, "no Find" end
    local key = make_fname(want)
    if not key then return nil, "bad FName" end
    local ok, v = pcall(function() return map:Find(key) end)
    if ok and v ~= nil then return v, want end
    ok, v = pcall(function() return map:Find(want) end)
    if ok and v ~= nil then return v, want end
    return nil, "key not found: " .. tostring(want)
end

-- MAP_GET <target> <mapPath> <key> [subPath] : Find-only (safe)
handlers.MAP_GET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local map = read_path(obj, args[2] or "")
    local val, key = map_find(map, args[3] or "")
    if val == nil then return false, tostring(key) end
    if args[4] and args[4] ~= "" then
        local ok, sub = pcall(function() return read_path(val, args[4]) end)
        if not ok then return false, "subPath: " .. tostring(sub) end
        return true, tostring(args[3]) .. "." .. args[4] .. "=" .. to_text(sub)
    end
    return true, tostring(args[3]) .. "=" .. to_text(val)
end

-- MAP_SET <target> <mapPath> <key> <subPath> <num|bool> : Find-only write on value
handlers.MAP_SET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local map = read_path(obj, args[2] or "")
    local val, err = map_find(map, args[3] or "")
    if val == nil then return false, tostring(err) end
    local raw = args[5]
    local value
    if raw == "true" then value = true elseif raw == "false" then value = false else value = tonumber(raw) end
    if value == nil then return false, "MAP_SET value must be num/bool" end
    local c, last = walk(val, args[4] or "")
    if last.index then return false, "cannot assign a whole array element" end
    local before = to_text(c[last.key])
    c[last.key] = value
    local after = to_text(read_path(val, args[4]))
    if after ~= to_text(value) then
        return false, "write did not stick: before " .. before .. ", wrote " .. tostring(value) .. ", now " .. after
    end
    return true, tostring(args[3]) .. "." .. args[4] .. " " .. before .. " -> " .. after
end

handlers.MAP_SAMPLE = function()
    return false, "disabled (use MAP_GET Find-only; ForEach unsafe on Active)"
end
-- MAP_KEYS <target> <path> : keys of a TMap / TSet (ForEach). Blocked on huge Active map.
handlers.MAP_KEYS = function(args)
    local path = args[2] or ""
    if path:find("%.Active$") or path:find("%.Active%.") or path == "m_permanent.Active" then
        return false, "MAP_KEYS on Active disabled (crash suspect); use MAP_GET Find-only"
    end
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local v = read_path(obj, path)
    if type(v) ~= "userdata" then return false, "not a container: " .. type(v) end
    local okf, each = pcall(function() return v.ForEach end)
    if not okf or each == nil then return false, "this UE4SS build has no ForEach on " .. path end
    local keys = {}
    v:ForEach(function(k)
        if #keys < 80 then
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

-- EVENTS : what's on the map right now.
-- Prefer ActiveEventInfo (Loom: small ~25 open board) then openActiveEventList.
-- Do NOT dump every m_permanent.Active phase 1-3 — lottery WithReset leaves stale Emerge
-- rows and stacks multiple icons on the same EventPoint (tree + horn, etc.).
handlers.EVENTS = function()
    local qs = resolve("GDDQuestStatus")
    if not qs then return false, "GDDQuestStatus not found (is a save loaded?)" end
    local out, seen, notes = {}, {}, {}
    local function add(id, phase)
        if id and id ~= "" and id ~= "None" and id ~= "nil" and not seen[id] then
            seen[id] = true
            out[#out + 1] = id .. ":" .. phase
        end
    end
    local ok, err = pcall(function()
        local info = read_path(qs, "m_permanent.ActiveEventInfo")
        if info == nil or not info.ForEach then error("ActiveEventInfo missing") end
        info:ForEach(function(k)
            if type(k) == "userdata" and k.get then k = k:get() end
            add(to_text(k), "1")
        end)
    end)
    if not ok then notes[#notes + 1] = "ActiveEventInfo: " .. tostring(err) end
    ok, err = pcall(function()
        unwrap(read_path(qs, "m_volatile.ActiveEventStatusV.openActiveEventList")):ForEach(function(_, e)
            e = unwrap(e)
            local boxed = type(e) == "userdata" or type(e) == "table"
            local id = boxed and field(e, { "activeEventId", "questId", "ID", "id", "eventId" }) or e
            add(to_text(id), "open")
        end)
    end)
    if not ok then notes[#notes + 1] = "open list: " .. tostring(err) end
    -- Fallback only if both maps above failed: Active phase 1-3 (may include stale emerges).
    if #out == 0 then
        ok, err = pcall(function()
            unwrap(read_path(qs, "m_permanent.Active")):ForEach(function(k, v)
                local phase = tonumber(to_text(field(unwrap(v), { "phase", "Phase" })))
                if phase and phase >= 1 and phase <= 3 then add(to_text(unwrap(k)), phase) end
            end)
        end)
        if not ok then notes[#notes + 1] = "Active: " .. tostring(err) end
        if #out > 0 then notes[#notes + 1] = "fallback Active phases (may stack places)" end
    end
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
        local okv, val = pcall(function() return to_text(obj:GetPropertyValue(n)) end)
        lines[#lines + 1] = n .. "=" .. (okv and val or "<err>")
    end)
    return true, table.concat(lines, " | ")
end

-- LIST_FUNCS <target> [substr] : UFunctions on the object's class (and optionally name filter).
-- ExeCommandSubsystem has no reflected properties; this finds the native/BP call doors.
handlers.LIST_FUNCS = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local want = args[2] or ""
    local cls = obj:GetClass()
    local short = cls:GetFName():ToString()
    local lines = { cls:GetFullName() }
    local seen = {}
    local function add(name)
        if not name or name == "" or seen[name] then return end
        if want ~= "" and not name:lower():find(want:lower(), 1, true) then return end
        seen[name] = true
        if #lines < 120 then lines[#lines + 1] = name end
    end
    -- Prefer class-local iteration when this UE4SS build exposes it.
    if cls.ForEachFunction then
        pcall(function()
            cls:ForEachFunction(function(fn)
                add(fn:GetFName():ToString())
            end)
        end)
    end
    -- Fallback / supplement: walk all UFunctions whose full name mentions the class.
    local func_class = StaticFindObject("/Script/CoreUObject.Function")
    if func_class and func_class:IsValid() then
        ForEachUObject(function(u)
            if #lines >= 120 then return end
            if u:IsA(func_class) then
                local full = u:GetFullName() or ""
                if full:find(short, 1, true) or full:find("." .. short .. ":", 1, true) then
                    add(u:GetFName():ToString())
                end
            end
        end)
    end
    if #lines <= 1 then
        return false, "no functions found for " .. short .. (want ~= "" and (" filter=" .. want) or "")
    end
    return true, (#lines - 1) .. "|" .. table.concat(lines, " | ")
end

-- Parse one CALL_FN arg. Table literals: "{}" / "OUT" / "{Key=val,Key2=val2}"
-- Special: "ARGS:a,b,c" -> ExeCommandParam-shaped {State=0,args={a,b,c}} for TargetId cmds.
local function parse_call_arg(raw)
    if raw == "OUT" or raw == "{}" then return {} end
    if type(raw) == "string" and raw:sub(1, 5) == "ARGS:" then
        local t = { State = 0, DeltaTime = 0.0, args = {}, Params = {} }
        local body = raw:sub(6)
        if body ~= "" then
            for piece in (body .. ","):gmatch("([^,]*),") do
                local s = piece:match("^%s*(.-)%s*$")
                if s and s ~= "" then t.args[#t.args + 1] = s end
            end
        end
        return t
    end
    if type(raw) == "string" and raw:sub(1, 1) == "{" and raw:sub(-1) == "}" then
        local t = {}
        local body = raw:sub(2, -2)
        if body ~= "" then
            for pair in (body .. ","):gmatch("([^,]*),") do
                local k, v = pair:match("^%s*([^=]+)%s*=%s*(.-)%s*$")
                if k and k ~= "" then
                    if v == "true" then t[k] = true
                    elseif v == "false" then t[k] = false
                    else
                        local num = tonumber(v)
                        t[k] = num ~= nil and num or v
                    end
                end
            end
        end
        return t
    end
    if raw == "true" then return true end
    if raw == "false" then return false end
    local num = tonumber(raw)
    if num ~= nil then return num end
    return raw
end

local function dump_val(v, depth)
    depth = depth or 0
    local t = type(v)
    if t == "number" or t == "boolean" or t == "string" or t == "nil" then return tostring(v) end
    if t == "table" and depth < 2 then
        local parts = {}
        local n = #v
        if n > 0 then
            for i = 1, math.min(n, 8) do parts[#parts + 1] = dump_val(v[i], depth + 1) end
            return "[" .. table.concat(parts, ";") .. "]"
        end
        for k, val in pairs(v) do
            parts[#parts + 1] = tostring(k) .. "=" .. dump_val(val, depth + 1)
            if #parts >= 12 then break end
        end
        return "{" .. table.concat(parts, ",") .. "}"
    end
    return to_text(v)
end

-- FN_INFO <target> <FunctionName> : list UFunction parm names (for Out-table field guesses).
handlers.FN_INFO = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local fname = args[2]
    if not fname or fname == "" then return false, "usage: FN_INFO <target> <FunctionName>" end
    local cls = obj:GetClass()
    local short = cls:GetFName():ToString()
    local func_class = StaticFindObject("/Script/CoreUObject.Function")
    if not func_class or not func_class:IsValid() then return false, "Function class missing" end
    local found, parms = nil, {}
    ForEachUObject(function(u)
        if found or not u:IsA(func_class) then return end
        local full = u:GetFullName() or ""
        if u:GetFName():ToString() == fname and (full:find(short, 1, true) or full:find("." .. short .. ":", 1, true)) then
            found = u
            if u.ForEachProperty then
                u:ForEachProperty(function(prop)
                    parms[#parms + 1] = prop:GetFName():ToString()
                end)
            end
        end
    end)
    if not found then return false, "UFunction not found: " .. fname end
    return true, found:GetFullName() .. " | parms=" .. (#parms > 0 and table.concat(parms, ",") or "(none)")
end

-- CALL_FN <target> <FunctionName> [arg...] : call a UFunction / Lua-bound method.
-- Args: number/bool/string, or table literal "{Key=val}" / "{}" / OUT for Out params.
-- Use only after LIST_FUNCS. Prefer ExeCmd runners over raw state pokes for map events.
handlers.CALL_FN = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local fname = args[2]
    if not fname or fname == "" then return false, "usage: CALL_FN <target> <FunctionName> [args...]" end
    local call_args = {}
    for i = 3, #args do
        call_args[#call_args + 1] = parse_call_arg(args[i])
    end
    local fn = obj[fname]
    if fn == nil then
        return false, "no method " .. fname .. " on " .. to_text(obj)
    end
    local n = #call_args
    -- Many DP1 ExeCmd_* UFunctions take a single Out param (empty table). If caller
    -- passed no args, try that shape first — zero-arg calls fail with "expected 1".
    local ok, a, b, c, d = pcall(function()
        if n == 0 then return fn(obj, {})
        elseif n == 1 then return fn(obj, call_args[1])
        elseif n == 2 then return fn(obj, call_args[1], call_args[2])
        elseif n == 3 then return fn(obj, call_args[1], call_args[2], call_args[3])
        elseif n == 4 then return fn(obj, call_args[1], call_args[2], call_args[3], call_args[4])
        else return fn(obj, call_args[1], call_args[2], call_args[3], call_args[4], call_args[5])
        end
    end)
    if not ok then return false, tostring(a) end
    local parts = {}
    for _, v in ipairs({ a, b, c, d }) do
        if v ~= nil then parts[#parts + 1] = to_text(v) end
    end
    -- Also dump Out-table fields after the call (ExeCommandParam State/args/Params).
    if n >= 1 and type(call_args[1]) == "table" then
        parts[#parts + 1] = "out" .. dump_val(call_args[1], 0)
    end
    return true, (#parts > 0 and table.concat(parts, " | ") or "called " .. fname)
end

local function push_args(param, values)
    local arr = param.args
    if arr == nil then return "args nil" end
    -- Prefer TArray:Add when UE4SS bound a real container; else Lua array.
    if type(arr) == "userdata" or (type(arr) == "table" and arr.Add) then
        if arr.Empty then pcall(function() arr:Empty() end) end
        for _, v in ipairs(values) do
            local ok, err = pcall(function() arr:Add(v) end)
            if not ok then
                -- try FName-like table
                ok, err = pcall(function() arr:Add({ Name = v }) end)
                if not ok then return "Add failed: " .. tostring(err) end
            end
        end
        return "Add x" .. tostring(#values)
    end
    if type(arr) ~= "table" then param.args = {} ; arr = param.args end
    for i = 1, #arr do arr[i] = nil end
    for i, v in ipairs(values) do arr[i] = v end
    return "lua x" .. tostring(#values)
end

local function call_exe(fname)
    local obj = resolve("ExeCommandSubsystem")
    if not obj then return false, "ExeCommandSubsystem not found" end
    local fn = obj[fname]
    if fn == nil then return false, "no method " .. fname end
    local param = {}
    local ok, err = pcall(function() return fn(obj, param) end)
    if not ok then return false, tostring(err) end
    return true, "out" .. dump_val(param, 0)
end

-- EVENT_END <activeEventId> : aim via progressActiveEventId, then EndNotifyOnly (no TargetId args).
-- Bypasses broken ExeCommandParam.args TArray marshaling for *_TargetId.
handlers.EVENT_END = function(args)
    local eid = args[1]
    if not eid or eid == "" then return false, "usage: EVENT_END <qsf_active_event_...>" end
    local qs = resolve("GDDQuestStatus")
    if not qs then return false, "GDDQuestStatus not found" end
    local path = "m_volatile.ActiveEventStatusV.progressActiveEventId"
    local before = to_text(read_path(qs, path))
    local fn = make_fname(eid)
    if not fn then return false, "bad FName " .. eid end
    local c, last = walk(qs, path)
    c[last.key] = fn
    local mid = to_text(read_path(qs, path))
    local ok, msg = call_exe("ExeCmd_ActiveEventEndNotifyOnly")
    if not ok then return false, "set " .. before .. "->" .. mid .. " but End failed: " .. tostring(msg) end
    -- Also try phase End on Active map entry (Find-only).
    local phase_note = ""
    local active = read_path(qs, "m_permanent.Active")
    local row = select(1, map_find(active, eid))
    if row ~= nil then
        local okp, errp = pcall(function()
            row.phase = 255
        end)
        phase_note = okp and " phase->255" or (" phaseFail=" .. tostring(errp))
    else
        phase_note = " (no Active row Find)"
    end
    return true, "progress " .. before .. "->" .. mid .. " | " .. msg .. phase_note
end

local PHASE_ALIASES = {
    [0] = { "0", "None" },
    [1] = { "1", "Emerge" },
    [2] = { "2", "Progress" },
    [3] = { "3", "ProgressSecond" },
    [254] = { "254", "Achieve" },
    [255] = { "255", "End" },
}

local function phase_matches(after, ph)
    if after == tostring(ph) then return true end
    local aliases = PHASE_ALIASES[ph]
    if not aliases then return false end
    for _, a in ipairs(aliases) do
        if after:find(a, 1, true) then return true end
    end
    return false
end

-- EVENT_PHASE <id> <phaseByte> : Find-only set Active[id].phase (0/1/2/3/254/255)
handlers.EVENT_PHASE = function(args)
    local eid, ph = args[1], tonumber(args[2] or "")
    if not eid or ph == nil then return false, "usage: EVENT_PHASE <id> <0|1|2|3|254|255>" end
    local qs = resolve("GDDQuestStatus")
    if not qs then return false, "GDDQuestStatus not found" end
    local active = read_path(qs, "m_permanent.Active")
    local row, err = map_find(active, eid)
    if row == nil then return false, tostring(err) end
    local before = to_text(row.phase)
    row.phase = ph
    local after = to_text(row.phase)
    if not phase_matches(after, ph) then
        return false, "phase did not stick: " .. before .. " -> " .. after
    end
    return true, eid .. ".phase " .. before .. " -> " .. after
end

-- Snapshot open event ids from ActiveEventInfo (small ~25 map; safer than Active).
local function open_info_ids()
    local qs = resolve("GDDQuestStatus")
    if not qs then return nil, "GDDQuestStatus not found" end
    local info = read_path(qs, "m_permanent.ActiveEventInfo")
    if info == nil then return nil, "ActiveEventInfo nil" end
    local ids, ok, err = {}, true, nil
    if info.ForEach then
        ok, err = pcall(function()
            info:ForEach(function(k)
                if type(k) == "userdata" and k.get then k = k:get() end
                local s = to_text(k)
                if s and s ~= "" and s ~= "None" then ids[#ids + 1] = s end
            end)
        end)
        if not ok then return nil, tostring(err) end
    else
        return nil, "ActiveEventInfo has no ForEach"
    end
    return ids, nil
end

local function set_has(ids, want)
    for _, id in ipairs(ids) do
        if id == want or id:find(want, 1, true) then return true end
    end
    return false
end

-- EVENT_SWAP <fromId> <toId> : end `from`, try emerge `to`, LotteryToLimit refill.
handlers.EVENT_SWAP = function(args)
    local from_id, to_id = args[1], args[2]
    if not from_id or not to_id then return false, "usage: EVENT_SWAP <fromId> <toId>" end
    local log = {}
    local ok, msg = handlers.EVENT_END({ from_id })
    log[#log + 1] = "end:" .. tostring(msg)
    if not ok then return false, table.concat(log, " | ") end
    ok, msg = handlers.EVENT_PHASE({ to_id, "1" })
    log[#log + 1] = (ok and "emerge:" or "emergeFail:") .. tostring(msg)
    local qs = resolve("GDDQuestStatus")
    local info = read_path(qs, "m_permanent.ActiveEventInfo")
    if info then
        local row = select(1, map_find(info, to_id))
        if row == nil and info.Add then
            local key = make_fname(to_id)
            local okadd, erradd = pcall(function()
                info:Add(key, { timePeriodChangeCount = 0 })
            end)
            log[#log + 1] = okadd and "info:Add" or ("infoAddFail=" .. tostring(erradd))
        else
            log[#log + 1] = row and "info:exists" or "info:noAdd"
        end
    end
    ok, msg = call_exe("ExeCmd_LotteryActiveEventToLimit")
    log[#log + 1] = "lottery:" .. tostring(msg)
    return true, table.concat(log, " || ")
end

-- EVENT_DRAW_UNTIL <keepId[,keep2...]> <wantId> [maxTries]
-- WithReset redraws until ActiveEventInfo contains every keep + want. Full reshuffle each try.
-- Practical path when surgical emerge is unavailable (proven Lottery WRITE).
handlers.EVENT_DRAW_UNTIL = function(args)
    local keep_raw, want, max_tries = args[1], args[2], tonumber(args[3] or "40") or 40
    if not keep_raw or not want then
        return false, "usage: EVENT_DRAW_UNTIL <keepId[,keep2]> <wantId> [maxTries]"
    end
    local keeps = {}
    for part in (keep_raw .. ","):gmatch("([^,]*),") do
        if part ~= "" then keeps[#keeps + 1] = part end
    end
    if #keeps == 0 then return false, "need at least one keep id" end
    if max_tries < 1 then max_tries = 1 end
    if max_tries > 80 then max_tries = 80 end
    local last_ids = {}
    for try = 1, max_tries do
        local ok, msg = call_exe("ExeCmd_LotteryActiveEventToLimitWithReset")
        if not ok then return false, "try " .. try .. " WithReset failed: " .. tostring(msg) end
        local ids, err = open_info_ids()
        if not ids then return false, "try " .. try .. " list failed: " .. tostring(err) end
        last_ids = ids
        local good = set_has(ids, want)
        if good then
            for _, k in ipairs(keeps) do
                if not set_has(ids, k) then good = false break end
            end
        end
        if good then
            return true, "ok try=" .. try .. " n=" .. #ids .. " has keep+want"
        end
    end
    return false, "miss after " .. max_tries .. " tries; last n=" .. #last_ids
        .. " hasWant=" .. tostring(set_has(last_ids, want))
end

-- EXE_CMD <ExeCmd_Name> : empty-Out only (Lottery* / EndNotifyOnly). No arg marshaling.
handlers.EXE_CMD = function(args)
    local fname = args[1]
    if not fname or fname == "" then return false, "usage: EXE_CMD <ExeCmd_Name>  (empty-Out only)" end
    if fname:sub(1, 7) ~= "ExeCmd_" then fname = "ExeCmd_" .. fname end
    if fname:find("TargetId", 1, true) then
        return false, "TargetId cmds blocked — use EVENT_END / EVENT_SWAP (args TArray does not marshal)"
    end
    return call_exe(fname)
end

-- DUMP : values + schema files in %LOCALAPPDATA%\StolenHours\dumps\
handlers.DUMP = function()
    local stamp = os.date("%Y%m%d_%H%M%S")
    local ok1, r1 = Dump.values(stamp)
    local ok2, r2 = Dump.schema(stamp)
    return ok1 and ok2, "values " .. r1 .. " | schema " .. r2
end

-- CAM_UNLOCK [far_cm] : free zoom-out (patches ChaseCamera CameraLenMax/Base). Default 200000 cm.
handlers.CAM_UNLOCK = function(args)
    return Camera.enable(args[1])
end

-- CAM_LOCK : stop re-patching; soft-reset lengths toward craft default (2000).
handlers.CAM_LOCK = function()
    return Camera.disable()
end

-- CAM_LEN <cm> : set length (also enables).
handlers.CAM_LEN = function(args)
    local cm = tonumber(args[1] or "")
    if not cm or cm < 100 then return false, "usage: CAM_LEN <cm>  (e.g. 12000)" end
    return Camera.enable(cm)
end

-- CAM_IN / CAM_OUT [big] : step zoom while unlocked
handlers.CAM_IN = function(args)
    return Camera.zoom_in(args[1] == "big")
end
handlers.CAM_OUT = function(args)
    return Camera.zoom_out(args[1] == "big")
end

-- CAM_STATUS : unlocked? last patch report
handlers.CAM_STATUS = function()
    return Camera.status()
end

-- CRAFT_STATUS : layout subsystem + craft-actor count (Customization cam present?)
handlers.CRAFT_STATUS = function()
    return Craft.status()
end

-- CRAFT_LIST : live placed craft actors (handle + UE cm pose + craftObjId)
handlers.CRAFT_LIST = function()
    return Craft.list()
end

-- CRAFT_TELEPORT <handle> <x> <y> <z> [yaw] : move a live craft actor (save in-game to persist)
handlers.CRAFT_TELEPORT = function(args)
    return Craft.teleport(args)
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
    -- Re-clamp Max only every ~3s (never force live distance — that caused flicker).
    if Camera.enabled and beat % 15 == 0 then
        ExecuteInGameThread(function()
            pcall(Camera.tick)
        end)
    end
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

local function cam_print(label, ok, res, text)
    print("[StolenHours] " .. label .. ": " .. tostring(ok and (text or res) or res) .. "\n")
end

local function toggle_camera()
    ExecuteInGameThread(function()
        local ok, res, text
        if Camera.enabled then
            ok, res, text = pcall(Camera.disable)
        else
            ok, res, text = pcall(Camera.enable)
        end
        cam_print("F8", ok, res, text)
    end)
end

local function zoom_in(big)
    ExecuteInGameThread(function()
        local ok, res, text = pcall(Camera.zoom_in, big)
        cam_print(big and "F6++" or "F6", ok, res, text)
    end)
end

local function zoom_out(big)
    ExecuteInGameThread(function()
        local ok, res, text = pcall(Camera.zoom_out, big)
        cam_print(big and "F7++" or "F7", ok, res, text)
    end)
end

-- F8 on/off · F6 zoom in · F7 zoom out (Ctrl = bigger step)
RegisterKeyBind(Key.F8, toggle_camera)
RegisterKeyBind(Key.F8, { ModifierKey.CONTROL }, toggle_camera)
RegisterKeyBind(Key.F6, function() zoom_in(false) end)
RegisterKeyBind(Key.F7, function() zoom_out(false) end)
RegisterKeyBind(Key.F6, { ModifierKey.CONTROL }, function() zoom_in(true) end)
RegisterKeyBind(Key.F7, { ModifierKey.CONTROL }, function() zoom_out(true) end)

print("[StolenHours] live controller " .. VERSION .. " polling " .. LIVE_DIR .. "\n")
print("[StolenHours] F8=cam on/off  F6=zoom in  F7=zoom out  (Ctrl+F6/F7 = big step)\n")
print("[StolenHours] CRAFT_STATUS / CRAFT_LIST / CRAFT_TELEPORT (live Customization actors)\n")
