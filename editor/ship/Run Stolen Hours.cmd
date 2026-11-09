@echo off
REM Unblock GitHub-download MOTW, then start the editor.
REM Double-click this if StolenHours.exe crashes right after extract.
set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -LiteralPath '%ROOT%' -Recurse -Force -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue"
start "" "%ROOT%StolenHours.exe" %*
