# Installs (or removes) the Mode B live stack into the game folder:
#   1. GameBootstrapper.ini ApplicationPath -> shipping exe, so Steam launches without EAC (no multiplayer)
#   2. UE4SS (dwmapi.dll + ue4ss\) next to NFL1-Win64-Shipping.exe
#   3. The StolenHours Lua mod, enabled in ue4ss\Mods\mods.txt
# Every file it changes is first copied to backups\game_install\<timestamp>\ with SHA-256.
# Run only with the game closed. Undo: install_live.ps1 -Uninstall
param(
    [string]$GameDir = "",
    [switch]$Uninstall,
    [switch]$KeepEAC,
    [switch]$ModOnly
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $GameDir) {
    Push-Location (Join-Path $Root "editor")
    try { $GameDir = (& py -3.12 -m stolenhours where --game-dir 2>&1 | Select-Object -Last 1).ToString().Trim() }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "Could not detect the game folder ($GameDir). Pass -GameDir." }
    "Detected game folder: $GameDir"
}
$Win64 = Join-Path $GameDir "Game\Binaries\Win64"
$Ini = Join-Path $GameDir "GameBootstrapper.ini"
$Dist = Join-Path $Root "tools\ue4ss\dist"
$ModSrc = Join-Path $PSScriptRoot "ue4ss_mod\StolenHours"
$ShippingRel = "Game\Binaries\Win64\NFL1-Win64-Shipping.exe"

# Lua mod files are only read at startup (or on UE4SS hot reload, Ctrl+R), so -ModOnly is safe while the game runs.
if (-not $ModOnly -and (Get-Process -Name "NFL1-Win64-Shipping", "NFL1", "EACLauncher" -ErrorAction SilentlyContinue)) {
    throw "Game is running. Close it first."
}
if (-not (Test-Path (Join-Path $Win64 "NFL1-Win64-Shipping.exe"))) { throw "Game not found in $GameDir" }

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$BackupDir = Join-Path $Root "backups\game_install\$Stamp"
function Backup-File($Path) {
    if (-not (Test-Path $Path)) { return }
    New-Item -ItemType Directory -Force $BackupDir | Out-Null
    $dest = Join-Path $BackupDir (Split-Path -Leaf $Path)
    Copy-Item $Path $dest
    "{0}  {1}" -f (Get-FileHash $dest).Hash, $Path | Add-Content (Join-Path $BackupDir "SHA256.txt")
}

if ($Uninstall) {
    if (Test-Path $Ini) {
        $text = Get-Content $Ini -Raw
        if ($text -match [regex]::Escape("ApplicationPath=$ShippingRel")) {
            Backup-File $Ini
            Set-Content $Ini ($text -replace [regex]::Escape("ApplicationPath=$ShippingRel"), "ApplicationPath=EACLauncher.exe") -NoNewline
            "EAC launch restored in GameBootstrapper.ini"
        }
    }
    foreach ($p in @((Join-Path $Win64 "dwmapi.dll"), (Join-Path $Win64 "ue4ss"))) {
        if (Test-Path $p) { Remove-Item -Recurse -Force $p; "removed $p" }
    }
    "Uninstalled. Backups (if any): $BackupDir"
    return
}

New-Item -ItemType Directory -Force (Join-Path $env:LOCALAPPDATA "StolenHours\live"), (Join-Path $env:LOCALAPPDATA "StolenHours\dumps") | Out-Null

if ($ModOnly) {
    $ModsDir = Join-Path $Win64 "ue4ss\Mods"
    if (-not (Test-Path $ModsDir)) { throw "UE4SS is not installed; run without -ModOnly first" }
    $Dest = Join-Path $ModsDir "StolenHours"
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    Copy-Item $ModSrc $ModsDir -Recurse -Force
    "Updated StolenHours mod in $ModsDir"
    return
}

if (-not (Test-Path (Join-Path $Dist "dwmapi.dll"))) { throw "UE4SS not found in $Dist" }

if (-not $KeepEAC) {
    $text = Get-Content $Ini -Raw
    if ($text -notmatch "ApplicationPath=EACLauncher\.exe" -and $text -notmatch [regex]::Escape("ApplicationPath=$ShippingRel")) {
        throw "GameBootstrapper.ini has an unexpected ApplicationPath; not touching it:`n$text"
    }
    if ($text -match "ApplicationPath=EACLauncher\.exe") {
        Backup-File $Ini
        Set-Content $Ini ($text -replace "ApplicationPath=EACLauncher\.exe", "ApplicationPath=$ShippingRel") -NoNewline
        "GameBootstrapper.ini -> $ShippingRel (EAC skipped)"
    }
}

Backup-File (Join-Path $Win64 "dwmapi.dll")
Copy-Item (Join-Path $Dist "dwmapi.dll") $Win64 -Force
Copy-Item (Join-Path $Dist "ue4ss") $Win64 -Recurse -Force
$Settings = Join-Path $Win64 "ue4ss\UE4SS-settings.ini"
(Get-Content $Settings) -replace "^EnableHotReloadSystem = 0", "EnableHotReloadSystem = 1" | Set-Content $Settings
$ModsDir = Join-Path $Win64 "ue4ss\Mods"
Copy-Item $ModSrc $ModsDir -Recurse -Force
$ModsTxt = Join-Path $ModsDir "mods.txt"
$lines = Get-Content $ModsTxt | Where-Object { $_ -notmatch "^StolenHours\s*:" }
$idx = [array]::IndexOf($lines, ($lines | Where-Object { $_ -match "^; Built-in keybinds" } | Select-Object -First 1))
if ($idx -lt 0) { $lines += "StolenHours : 1" } else { $lines = $lines[0..($idx - 1)] + "StolenHours : 1" + $lines[$idx..($lines.Count - 1)] }
Set-Content $ModsTxt $lines
New-Item -ItemType Directory -Force (Join-Path $env:LOCALAPPDATA "StolenHours\live") | Out-Null
"Installed UE4SS + StolenHours mod into $Win64"
"Log: $Win64\ue4ss\UE4SS.log"
