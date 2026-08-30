@echo off
title Kill AI Hub Watcher
echo ========================================
echo Stopping AI Hub Watcher and Server...
echo ========================================

python "%~dp0kill_system.py"

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo SUCCESS: Server has been terminated!
echo.
ping 127.0.0.1 -n 3 >nul
