@echo off
title Kill Background Chrome (Facebook Bot)
echo [Info] Requesting Administrator privileges to close orphaned Chrome processes...
powershell -Command "Start-Process cmd -ArgumentList '/c taskkill /F /FI \"SESSION eq 0\" /IM chrome.exe' -Verb RunAs"
echo.
echo [Done] If the UAC popup appeared and you clicked 'Yes', the background Chrome has been terminated.
echo.
pause
