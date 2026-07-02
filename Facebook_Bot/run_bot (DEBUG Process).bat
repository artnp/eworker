@echo off
title Facebook Bot - DEBUG Process
cd /d "D:\Github\eworker\Facebook_Bot"
echo ============================================
echo  Facebook Bot - DEBUG Mode (--debug-pause)
echo  Browser will open. Login to Gemini if needed.
echo  Press Enter in this window to start scanning.
echo ============================================
echo.
node bot.js --debug-pause --bot
echo.
echo ============================================
echo  Bot process ended. Check output above.
echo ============================================
pause