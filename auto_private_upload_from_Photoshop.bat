@echo off
title PrivateSend - Processing...

:: ตั้งค่าไฟล์ที่ต้องการส่งคงที่
set "target_file=%USERPROFILE%\Desktop\complete.png"

:: ตรวจสอบว่าไฟล์มีอยู่จริงหรือไม่
if not exist "%target_file%" (
    echo [!] ไม่พบไฟล์: %target_file%
    pause
    exit /b
)

:: มีห้องแชท local เปิดอยู่ให้ส่งเข้าห้อง มิฉะนั้นใช้ flow เดิมไป download.html
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0PrivateSend.ps1" "%target_file%"

exit /b
