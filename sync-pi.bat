@echo off
setlocal EnableDelayedExpansion
title MineVision — copy to Raspberry Pi
cd /d "%~dp0"

set "PI_USER=darshan"
set "PI_HOST=darshan.local"
set "PI_ROOT=/home/darshan/MineTruck/MineTruck Project"

echo.
echo ============================================
echo  MineVision copy to Pi
echo  %PI_USER%@%PI_HOST%
echo  %PI_ROOT%
echo ============================================
echo  You will be asked for the Pi password
echo  once per file. Window stays open at the end.
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo ERROR: scp was not found on this PC.
    echo.
    echo Fix: Settings - Apps - Optional features - Add
    echo      OpenSSH Client
    echo Or in Admin PowerShell:
    echo   Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
    echo.
    goto done_fail
)

where ssh >nul 2>&1
if errorlevel 1 (
    echo ERROR: ssh was not found on this PC. Install OpenSSH Client.
    echo.
    goto done_fail
)

set OK=0
set FAIL=0
set "LASTERR="

echo --- create folders on the Pi
ssh %PI_USER%@%PI_HOST% "mkdir -p '%PI_ROOT%/raspberry_pi/scripts' '%PI_ROOT%/raspberry_pi/minevision/vision' '%PI_ROOT%/raspberry_pi/minevision/thermal' '%PI_ROOT%/raspberry_pi/minevision/fusion' '%PI_ROOT%/dashboard/static/js' '%PI_ROOT%/dashboard/static/css'"
if errorlevel 1 (
    echo [FAIL] could not create folders on the Pi.
    echo        Check password, IP, and that this path exists:
    echo        %PI_ROOT%
    set /a FAIL+=1
    set "LASTERR=ssh mkdir failed"
    goto done_fail
)
echo [OK]   remote folders ready
echo.

call :send "raspberry_pi\minevision\config.py"                        "raspberry_pi/minevision/config.py"
call :send "raspberry_pi\run.py"                                      "raspberry_pi/run.py"
call :send "raspberry_pi\minevision\netinfo.py"                       "raspberry_pi/minevision/netinfo.py"
call :send "raspberry_pi\minevision\fusion\distance.py"               "raspberry_pi/minevision/fusion/distance.py"
call :send "raspberry_pi\minevision\fusion\engine.py"                 "raspberry_pi/minevision/fusion/engine.py"
call :send "raspberry_pi\minevision\safety\__init__.py"               "raspberry_pi/minevision/safety/__init__.py"
call :send "raspberry_pi\minevision\api\__init__.py"                  "raspberry_pi/minevision/api/__init__.py"
call :send "raspberry_pi\minevision\thermal\mlx.py"                   "raspberry_pi/minevision/thermal/mlx.py"
call :send "raspberry_pi\minevision\thermal\__init__.py"              "raspberry_pi/minevision/thermal/__init__.py"
call :send "raspberry_pi\minevision\vision\__init__.py"               "raspberry_pi/minevision/vision/__init__.py"
call :send "raspberry_pi\minevision\vision\ov7670.py"                 "raspberry_pi/minevision/vision/ov7670.py"
call :send "raspberry_pi\minevision\vision\ov7670_grab.c"             "raspberry_pi/minevision/vision/ov7670_grab.c"
call :send "raspberry_pi\minevision\vision\gc9a01_blit.c"             "raspberry_pi/minevision/vision/gc9a01_blit.c"
call :send "raspberry_pi\minevision\vision\st7735.py"                 "raspberry_pi/minevision/vision/st7735.py"
call :send "raspberry_pi\scripts\probe_pi_cameras.py"                 "raspberry_pi/scripts/probe_pi_cameras.py"
call :send "raspberry_pi\scripts\enable_lan_name.sh"                  "raspberry_pi/scripts/enable_lan_name.sh"
call :send "raspberry_pi\scripts\join-wifi.sh"                        "raspberry_pi/scripts/join-wifi.sh"
call :send "raspberry_pi\scripts\setup-dashboard-autostart.sh"        "raspberry_pi/scripts/setup-dashboard-autostart.sh"
call :send "scripts\minevision.service"                               "scripts/minevision.service"
call :send "open-dashboard.ps1"                                       "open-dashboard.ps1"
call :send "open-dashboard.bat"                                       "open-dashboard.bat"
call :send "raspberry_pi\minevision\ingest\__init__.py"               "raspberry_pi/minevision/ingest/__init__.py"
call :send "dashboard\index.html"                                     "dashboard/index.html"
call :send "dashboard\static\js\app.js"                               "dashboard/static/js/app.js"
call :send "dashboard\static\css\app.css"                             "dashboard/static/css/app.css"

echo.
echo --------------------------------------------
if !FAIL! NEQ 0 goto done_fail

echo SUCCESS: !OK! file(s) copied to the Pi.
echo.
echo Next, on the Pi:
echo   cd "%PI_ROOT%"
echo   source .venv/bin/activate
echo   python raspberry_pi/scripts/probe_pi_cameras.py
echo.
pause
exit /b 0

:done_fail
echo FAILED: !OK! copied, !FAIL! failed.
if defined LASTERR echo Last error: !LASTERR!
echo.
echo Typical causes:
echo   - Wrong Pi password
echo   - Pi offline or IP is not %PI_HOST%
echo   - Folder missing on Pi: %PI_ROOT%
echo   - scp / OpenSSH not installed
echo   - A subfolder like raspberry_pi/scripts did not exist yet
echo.
pause
exit /b 1

:send
set "SRC=%~1"
set "REL=%~2"
echo.
echo --- %SRC%
if not exist "%SRC%" (
    echo [FAIL] not on this PC: "%CD%\%SRC%"
    set /a FAIL+=1
    set "LASTERR=Local file missing: %SRC%"
    goto :eof
)
scp "%SRC%" %PI_USER%@%PI_HOST%:"%PI_ROOT%/%REL%"
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
    echo [FAIL] scp exit code !EC!  %SRC%
    if "!EC!"=="255" echo        Connection failed: Pi off, wrong IP, or SSH refused.
    if "!EC!"=="1"   echo        Remote folder missing or permission/password problem.
    set /a FAIL+=1
    set "LASTERR=scp exit !EC! for %SRC%"
    goto :eof
)
echo [OK]   %SRC%
set /a OK+=1
goto :eof
