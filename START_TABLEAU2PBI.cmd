@echo off
cd /d "%~dp0"
echo Starting TABLEAU2PBI Enterprise Migration Workbench...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_tableau2pbi.ps1"
if errorlevel 1 pause
