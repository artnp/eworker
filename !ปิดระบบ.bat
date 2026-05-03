@echo off
title Kill AI Hub Server
echo ========================================
echo Stopping AI Hub Watcher...
echo ========================================

:: 1. Kill python processes running auto_donate_watcher.py
:: Using 'name like %%python%%' catches python.exe, pythonw.exe, python3.10.exe, pythonw3.10.exe, etc.
wmic process where "name like '%%python%%' and commandline like '%%auto_donate_watcher.py%%'" call terminate >nul 2>&1

:: 2. Kill the ports explicitly
if exist "kill_ports.py" (
    python kill_ports.py
)

echo.
echo SUCCESS: Server has been terminated!
echo.
echo NOTE: If the tray icons are still visible, 
echo simply hover your mouse over them and they will disappear.
echo.
timeout /t 5 >nul
