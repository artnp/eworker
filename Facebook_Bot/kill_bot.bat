@echo off
title Kill Facebook Bot
echo ==============================================
echo  Stopping Facebook Bot and all related processes
echo ==============================================
echo.

echo 1. Stopping Node.js processes (bot.js)...
taskkill /F /IM node.exe >nul 2>&1

echo 2. Stopping PowerShell processes (tray_gui.ps1 ^& tray.ps1)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'powershell.exe' or Name = 'pwsh.exe'\" | Where-Object { $_.CommandLine -like '*tray_gui*' -or $_.CommandLine -like '*notify*' -or $_.CommandLine -like '*tray.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo 3. Stopping Chrome processes associated with Facebook Bot...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe' or Name = 'msedge.exe' or Name = 'chromium.exe'\" | Where-Object { $_.CommandLine -like '*Facebook_Bot*user_data*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo 4. Stopping any orphaned Chrome instances...
taskkill /F /IM chrome.exe /FI "WINDOWTITLE eq *user_data*" >nul 2>&1

echo.
echo All Bot processes stopped successfully!
