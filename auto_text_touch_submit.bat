@echo off
REM auto_text_retouch_submit.bat
chcp 65001 >nul

if "%~1"=="" goto run_default
if "%~1"=="--no-pause" goto run_default
goto run_custom

:run_default
python "D:\Github\eworker\text_retouch_engine.py" --submit
goto check_pause

:run_custom
python "D:\Github\eworker\text_retouch_engine.py" --submit "%~1"
goto check_pause

:check_pause
if "%~1"=="--no-pause" goto end
if "%~2"=="--no-pause" goto end
pause
:end
