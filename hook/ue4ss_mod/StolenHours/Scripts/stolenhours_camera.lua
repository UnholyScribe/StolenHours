-- Free zoom for Stolen Hours.
-- Craft Customization cameras use CameraLenBase/LookUp/LookDown (often no Max).
-- F8: toggle unlock (sets a mid survey distance). While unlocked:
--   F6 zoom in (−step), F7 zoom out (+step), Ctrl+F6/F7 = bigger step.
-- Tick only re-raises Max when present — never rewrites Base (no flicker).

local M = {}

local SURVEY_DEFAULT = 12000.0 -- ~120 m start when unlocking
local STEP_SMALL = 1500.0
local STEP_BIG = 5000.0
local LEN_MIN = 400.0
local LEN_MAX = 120000.0
local STOCK_LEN = 2000.0

M.enabled = false
M.far_cm = SURVEY_DEFAULT
M.last_report = "off"
M.patched = 0

local function set_num(obj, key, value)
    local ok = pcall(function()
        obj[key] = value
    end)
    return ok
end

local function get_num(obj, key)
    local ok, v = pcall(function() return obj[key] end)
    if not ok or v == nil then return nil end
    return tonumber(v)
end

local function clamp(v, lo, hi)
    if v < lo then return lo end
    if v > hi then return hi end
    return v
end

local function patch_len_distance(len, far)
    if not len then return 0 end
    local n = 0
    for _, k in ipairs({
        "CameraLenBase", "CameraLenLookUp", "CameraLenLookDown",
        "CameraLenDefault", "CameraLength",
    }) do
        if set_num(len, k, far) then n = n + 1 end
    end
    -- Keep Max above current so anything that clamps still allows this length.
    local mx = get_num(len, "CameraLenMax")
    if mx == nil or mx < far then
        if set_num(len, "CameraLenMax", math.max(far, LEN_MAX)) then n = n + 1 end
    end
    local mn = get_num(len, "CameraLenMin")
    if mn == nil or mn > LEN_MIN then
        if set_num(len, "CameraLenMin", LEN_MIN) then n = n + 1 end
    end
    return n
end

local function patch_actor_distance(cam, far)
    if not cam or not cam:IsValid() then return 0 end
    local n = 0
    local ok, len = pcall(function() return cam.m_chaseCameraLen end)
    if ok and len then
        n = n + patch_len_distance(len, far)
    end
    local oh = get_num(cam, "m_overheadViewCameraLenMax")
    if oh == nil or oh < far then
        if set_num(cam, "m_overheadViewCameraLenMax", math.max(far, LEN_MAX)) then n = n + 1 end
    end
    return n
end

-- Clamp-only (tick): raise Max if present, leave Base alone.
local function patch_actor_clamps(cam, far)
    if not cam or not cam:IsValid() then return 0 end
    local n = 0
    local ok, len = pcall(function() return cam.m_chaseCameraLen end)
    if ok and len then
        local mx = get_num(len, "CameraLenMax")
        if mx ~= nil and mx < far then
            if set_num(len, "CameraLenMax", far) then n = n + 1 end
        end
    end
    return n
end

local CAMERA_CLASSES = {
    "ChaseCameraActor",
    "BP_CraftObjMapLayout_ChaseCameraActor_C",
    "BP_CraftObjLayout_ChaseCameraActor_C",
    "BP_CraftObjWallLayout_ChaseCameraActor_C",
    "BP_CraftAreaChaseCameraActor_C",
    "BP_CraftEvent_ChaseCameraActor_C",
    "BP_ChaseCameraActor_C",
    "BP_ChaseCameraActor_Far_C",
    "BP_ChaseCameraActor_Normal_C",
    "BP_ChaseOffsetCameraActor_C",
    "BP_BaseCamp_ChaseCameraActor_Far_C",
    "BP_BaseCamp_ChaseCameraActor_Normal_C",
    "BP_HugeMapChaseCameraActor_C",
    "BP_HugeMapChaseCameraActor_Far_C",
    "BP_HugeMapChaseCameraActor_Normal_C",
    "BP_HugeMapChaseCameraActorWide_C",
    "BP_HugeMapChaseCameraActorMap000200_C",
    "BP_DebugChaseCameraActor_C",
    "BP_IndoorChaseCameraActor_C",
}

local function each_camera(fn)
    local seen = {}
    for _, cls in ipairs(CAMERA_CLASSES) do
        local ok, list = pcall(function() return FindAllOf(cls) end)
        if ok and list then
            for _, cam in pairs(list) do
                if cam and cam:IsValid() then
                    local name = cam:GetFullName()
                    if not seen[name] and not name:find("Default__", 1, true) then
                        seen[name] = true
                        fn(cam, name)
                    end
                end
            end
        end
    end
end

function M.apply_distance(far)
    far = clamp(tonumber(far) or M.far_cm, LEN_MIN, LEN_MAX)
    M.far_cm = far
    local total, count = 0, 0
    each_camera(function(cam)
        count = count + 1
        total = total + patch_actor_distance(cam, far)
    end)
    M.patched = count
    M.last_report = string.format("cameras=%d writes=%d len=%.0fcm", count, total, far)
    return count, total, far
end

function M.enable(far)
    M.enabled = true
    local target = tonumber(far) or SURVEY_DEFAULT
    local c, w, f = M.apply_distance(target)
    print(string.format("[StolenHours] camera ON len=%.0fcm (%s)  F6=in F7=out\n", f, M.last_report))
    return true, string.format("on %s", M.last_report)
end

function M.disable()
    M.enabled = false
    local c, w, f = M.apply_distance(STOCK_LEN)
    print(string.format("[StolenHours] camera OFF → %.0fcm (%s)\n", STOCK_LEN, M.last_report))
    return true, string.format("off %s", M.last_report)
end

function M.nudge(delta)
    if not M.enabled then
        M.enabled = true
    end
    local next = clamp(M.far_cm + delta, LEN_MIN, LEN_MAX)
    local c, w, f = M.apply_distance(next)
    print(string.format("[StolenHours] camera len=%.0fcm (Δ%+.0f)\n", f, delta))
    return true, string.format("len=%.0fcm", f)
end

function M.zoom_in(big)
    return M.nudge(-(big and STEP_BIG or STEP_SMALL))
end

function M.zoom_out(big)
    return M.nudge(big and STEP_BIG or STEP_SMALL)
end

function M.status()
    return true, string.format("enabled=%s len=%.0f %s", tostring(M.enabled), M.far_cm, M.last_report)
end

function M.tick()
    if not M.enabled then return end
    local total, count = 0, 0
    each_camera(function(cam)
        count = count + 1
        total = total + patch_actor_clamps(cam, math.max(M.far_cm, LEN_MAX))
    end)
end

return M
