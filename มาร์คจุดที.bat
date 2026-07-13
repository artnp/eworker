@echo off
title MarkPoints - Uploading...
if "%~1"=="" (
    echo [!] Drag and drop image/PDF onto this icon.
    pause
    exit
)
powershell -ExecutionPolicy Bypass -File "%~dp0MarkPoints.ps1" "%~1"
exit
