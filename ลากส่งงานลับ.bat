@echo off
title PrivateSend - Processing...
:: ตรวจสอบว่ามีไฟล์ถูกลากมาวางหรือไม่
if "%~1"=="" (
    echo [!] Please drag and drop an image file onto this icon.
    pause
    exit
)

:: รัน PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0PrivateSend.ps1" "%~1"

exit
