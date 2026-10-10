@echo off
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if exist "sync_codes.py" (
    python sync_codes.py
) else (
    set "SRC=D:\Github\RedPacket_Code\codes_today.json"
    set "DST=d:\Github\eworker\shop\services\redPacket\codes_today.json"
    if exist "%SRC%" (
        copy /Y "%SRC%" "%DST%"
        echo [OK] Copied codes_today.json!
    )
)
