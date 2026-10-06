@echo off
chcp 65001 >nul
echo กำลังเปิดระบบหลังบ้าน (PrivateSend Admin Dashboard) ใน Google Chrome...

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "%~dp0admin-payment.html"
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    start "" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" "%~dp0admin-payment.html"
) else (
    start chrome "%~dp0admin-payment.html"
)
exit
