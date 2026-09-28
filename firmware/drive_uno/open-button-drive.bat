@echo off
cd /d "%~dp0"
python -c "import serial" 2>nul || pip install pyserial
python bt_button_control.py
pause
