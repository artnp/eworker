@echo off
title Facebook Bot - DEBUG Process
cd /d "D:\Github\eworker\Facebook_Bot"
echo ============================================
echo  Facebook Bot - DEBUG Mode (--debug-pause)
echo  Browser will open. Login to Gemini if needed.
echo  Press Enter in this window to start scanning.
echo ============================================
echo.

echo [Pre-launch] Killing any orphaned Chrome using this user_data...
taskkill /F /IM chrome.exe /FI "WINDOWTITLE eq *user_data*" >nul 2>&1
powershell -NoProfile -Command "Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*Facebook_Bot\user_data*' } | Stop-Process -Force" >nul 2>&1
timeout /t 2 /nobreak >nul

node bot.js --debug-pause --bot
echo.
echo ============================================
echo  Bot process ended. Check output above.
echo ============================================
pause