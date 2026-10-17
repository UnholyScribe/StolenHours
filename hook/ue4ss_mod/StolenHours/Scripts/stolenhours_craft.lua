-- Live craft helpers: list / teleport placed CraftObj actors while Customization (or world) is up.
-- Persistence: teleport only moves the live actor — save in-game (or quit + offline save edit) to keep it.

local M = {}

local function valid(o)
    return o and o:IsValid()
end

local function handle_of(actor)
    local ok, h = pcall(function()
        local info = actor.m_craftObjHdlInfo
        if not info then return nil end
        if info.handle ~= nil then return tonumber(info.handle) end
        if info.Handle ~= nil then
            local H = info.Handle
            if type(H) == "number" then return H end
            if H.handle ~= nil then return tonumber(H.handle) end
        end
        return nil
    end)
    return ok and h or nil
end

local function craft_id_of(actor)
    local ok, id = pcall(function()
        local v = actor.m_craftObjId or actor.craftObjId
        if v == nil then return nil end
        if type(v) == "string" then return v end
        if v.ToString then return v:ToString() end
        return tostring(v)
    end)
    return (ok and id and id ~= "" and id ~= "None") and id or "?"
end

local function each_craft_actor(fn)
    local mgr = FindFirstOf("CraftObjManagerSubsystem")
    if valid(mgr) then
        local lists = { mgr.m_craftObjActorBaseList, mgr.m_instCraftObjActorBaseList }
        for _, arr in ipairs(lists) do
            if arr and arr.ForEach then
                pcall(function()
                    arr:ForEach(function(_, a)
                        a = a and (a.Get and a:Get() or a) or a
                        if valid(a) then fn(a) end
                    end)
                end)
            end
        end
    end
    local all = FindAllOf("CraftObjActorBase") or {}
    for _, a in ipairs(all) do
        if valid(a) then
            local name = a:GetFullName() or ""
            if not name:find("Default__", 1, true) then fn(a) end
        end
    end
end

function M.status()
    local layout = FindFirstOf("CraftObjLayoutManagerSubsystem")
    local area = FindFirstOf("CraftAreaManagerSubsystem")
    local n = 0
    each_craft_actor(function() n = n + 1 end)
    local state, mode = "?", "?"
    if valid(layout) then
        pcall(function()
            state = tostring(layout.m_State)
            mode = tostring(layout.m_layoutMode)
        end)
    end
    local cam = FindFirstOf("BP_CraftObjMapLayout_ChaseCameraActor_C")
        or FindFirstOf("BP_CraftObjLayout_ChaseCameraActor_C")
    local in_layout = valid(cam) and "yes" or "no"
    return true, string.format(
        "actors=%d|layout=%s|mode=%s|craftCam=%s|areaMgr=%s",
        n, state, mode, in_layout, valid(area) and "yes" or "no")
end

-- CRAFT_LIST → "N|handle:x,y,z,yaw,id;..."
function M.list()
    local seen, rows = {}, {}
    each_craft_actor(function(a)
        local h = handle_of(a)
        local key = h or a:GetFullName()
        if seen[key] then return end
        seen[key] = true
        local loc = a:K2_GetActorLocation()
        local rot = a:K2_GetActorRotation()
        local id = craft_id_of(a)
        rows[#rows + 1] = string.format("%s:%.1f,%.1f,%.1f,%.1f,%s",
            tostring(h or -1), loc.X, loc.Y, loc.Z, rot.Yaw, id:gsub("[,;|]", "_"))
    end)
    return true, tostring(#rows) .. "|" .. table.concat(rows, ";")
end

local function find_by_handle(want)
    want = tonumber(want)
    if not want then return nil end
    local hit
    each_craft_actor(function(a)
        if hit then return end
        if handle_of(a) == want then hit = a end
    end)
    return hit
end

-- CRAFT_TELEPORT <handle> <x> <y> <z> [yaw]
function M.teleport(args)
    local h, x, y, z, yaw = args[1], tonumber(args[2]), tonumber(args[3]), tonumber(args[4]), tonumber(args[5] or "0")
    if not h or not x or not y or not z then
        return false, "usage: CRAFT_TELEPORT <handle> <x> <y> <z> [yaw]"
    end
    local a = find_by_handle(h)
    if not a then return false, "no craft actor for handle " .. tostring(h) end
    local ok1 = pcall(function()
        a:K2_SetActorLocation({ X = x, Y = y, Z = z }, false, {}, true)
    end)
    if not ok1 then
        ok1 = pcall(function()
            a:K2_SetActorLocation(x, y, z, false)
        end)
    end
    local ok2 = pcall(function()
        a:K2_SetActorRotation({ Pitch = 0, Yaw = yaw, Roll = 0 }, true)
    end)
    if not ok1 then return false, "SetActorLocation failed" end
    local loc = a:K2_GetActorLocation()
    return true, string.format("moved %s -> %.1f,%.1f,%.1f yaw=%s rotOk=%s",
        tostring(h), loc.X, loc.Y, loc.Z, tostring(yaw), ok2 and "1" or "0")
end

return M
