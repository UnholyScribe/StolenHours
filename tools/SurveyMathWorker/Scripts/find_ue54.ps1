# Locate Unreal Engine under E:\Unreal Engine; write ue_path.txt.
# Note: UnrealEditor.exe is often a ~500KB bootstrapper; real editor is UnrealEditor-*.dll.
$ErrorActionPreference = "Stop"
$out = Join-Path (Split-Path $PSScriptRoot -Parent) "ue_path.txt"
$candidates = @(
    "E:\Unreal Engine\UE_5.8",
    "E:\Unreal Engine\UE_5.5",
    "E:\Unreal Engine\UE_5.4",
    "C:\Program Files\Epic Games\UE_5.8",
    "C:\Program Files\Epic Games\UE_5.5"
)
if (Test-Path -LiteralPath "E:\Unreal Engine") {
    Get-ChildItem -LiteralPath "E:\Unreal Engine" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "UE_*" } |
        ForEach-Object { $candidates = @($_.FullName) + $candidates }
}
$found = $null
foreach ($c in $candidates) {
    $exe = Join-Path $c "Engine\Binaries\Win64\UnrealEditor.exe"
    $core = Join-Path $c "Engine\Binaries\Win64\UnrealEditor-Core.dll"
    if ((Test-Path -LiteralPath $exe) -and (Test-Path -LiteralPath $core)) {
        $found = $c
        break
    }
}
if (-not $found) {
    Write-Host "No UnrealEditor + UnrealEditor-Core.dll pair found."
    exit 1
}
Set-Content -Path $out -Value $found -Encoding utf8
Write-Host "Wrote $out"
Write-Host "UE = $found"
exit 0
