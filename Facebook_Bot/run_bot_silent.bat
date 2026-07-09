@echo off
title Facebook Bot - Silent Mode
cd /d "D:\Github\eworker\Facebook_Bot"

echo ============================================
echo  Facebook Bot - Silent Background Mode
echo  Browser minimized, check status.json
echo ============================================
echo.

echo [Pre-launch] Killing any orphaned Chrome...
taskkill /F /IM chrome.exe /FI "WINDOWTITLE eq *user_data*" >nul 2>&1
powershell -NoProfile -Command "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*Facebook_Bot\user_data*' } | Stop-Process -Force" >nul 2>&1
timeout /t 2 /nobreak >nul

REM Run bot - browser will auto-minimize
start /B node bot.js --bot

echo.
echo Bot started in background. Check status.json for progress.
echo Close this window anytime (bot will continue running).
timeout /t 3 /nobreak >nul
