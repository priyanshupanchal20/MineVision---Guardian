@echo off
title MineVision dashboard
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open-dashboard.ps1"
if errorlevel 1 pause
