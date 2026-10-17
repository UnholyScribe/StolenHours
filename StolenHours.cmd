@echo off
rem Starts the desktop editor. Any arguments go to the CLI instead (e.g. StolenHours.cmd info).
cd /d "%~dp0editor"
if "%~1"=="" (
    start "" pyw -3.12 -m stolenhours gui
) else (
    py -3.12 -m stolenhours %*
)
