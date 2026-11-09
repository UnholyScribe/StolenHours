# Run smw_capture_orbit.py via UnrealEditor-Cmd (requires UE 5.4 + find_ue54.ps1).
$ErrorActionPreference = "Stop"
$projRoot = Split-Path $PSScriptRoot -Parent
$uePathFile = Join-Path $projRoot "ue_path.txt"
if (-not (Test-Path $uePathFile)) {
    & (Join-Path $PSScriptRoot "find_ue54.ps1")
}
$ueRoot = (Get-Content $uePathFile -Raw).Trim()
$editor = Join-Path $ueRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
if (-not (Test-Path $editor)) {
    $editor = Join-Path $ueRoot "Engine\Binaries\Win64\UnrealEditor.exe"
}
# Short junction avoids spaces + \t-in-\tools eating the Python path.
$smw = "E:\SMW"
if (-not (Test-Path $smw)) {
    cmd /c "mklink /J `"$smw`" `"$projRoot`"" | Out-Null
}
$uproject = "$smw/SurveyMathWorker.uproject" -replace '\\','/'
$py = "$smw/Content/Python/smw_run_all.py" -replace '\\','/'
if (-not (Test-Path $editor)) { throw "UnrealEditor not found under $ueRoot" }
# Ensure truth tables exist
Push-Location "E:\Fantasy Life i - Stolen Hours\editor"
py -3.12 -m stolenhours.survey_math export
Pop-Location
& $editor $uproject "-ExecutePythonScript=$py" -unattended -nop4 -nosplash -log -AllowCommandletRendering
Write-Host "Orbit capture finished. Check G:\Stolen Hours\survey\Map_000100\"
