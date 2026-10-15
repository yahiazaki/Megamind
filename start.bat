@echo off
rem Double-click to start Megamind (runs start.ps1 without changing the system's PowerShell execution policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
