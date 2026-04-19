@echo off
title PrivateSend - Processing...

:: ตั้งค่าไฟล์ที่ต้องการส่งคงที่
set "target_file=C:\Users\artwh\Desktop\render_xyz.png"

:: ตรวจสอบว่าไฟล์มีอยู่จริงหรือไม่
if not exist "%target_file%" (
    echo [!] ไม่พบไฟล์: %target_file%
    pause
    exit /b
)

:: ส่งไฟล์ที่กำหนดไปยัง PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0PrivateSend.ps1" "%target_file%"

exit /b