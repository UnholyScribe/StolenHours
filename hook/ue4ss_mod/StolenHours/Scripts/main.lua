-- Stolen Hours live controller (UE4SS Lua mod).
-- Mailbox: %LOCALAPPDATA%\StolenHours\live\  (cmd.txt in, ack.txt out, heartbeat.txt)
-- Command line format: <id>\t<VERB>\t<arg>...   Reply: <id>\tOK|ERR\t<text>
-- All object access runs inside ExecuteInGameThread; the polling loop only touches files.

local LIVE_DIR = (os.getenv("LOCALAPPDATA") or ".") .. "\\StolenHours\\live\\"
local CMD = LIVE_DIR .. "cmd.txt"
local ACK = LIVE_DIR .. "ack.txt"
local HEARTBEAT = LIVE_DIR .. "heartbeat.txt"
local VERSION = "0.2.0"
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
    if t == "userdata" then
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

-- GET <target> <Property>
handlers.GET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    return true, to_text(obj:GetPropertyValue(args[2]))
end

-- SET <target> <Property> <number|true|false>
handlers.SET = function(args)
    local obj = resolve(args[1] or "")
    if not obj then return false, "object not found: " .. tostring(args[1]) end
    local raw = args[3]
    local value
    if raw == "true" then value = true elseif raw == "false" then value = false else value = tonumber(raw) end
    if value == nil then return false, "only numeric/bool values are supported" end
    obj:SetPropertyValue(args[2], value)
    return true, to_text(obj:GetPropertyValue(args[2]))
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
