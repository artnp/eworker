@echo off
chcp 65001 > nul
echo ==================================================
echo       เปิดการตั้งเวลาทำงานบอททุก 3 ชั่วโมง
echo ==================================================
echo.

:: กำหนดพาธแบบ Dynamic จากตำแหน่งของไฟล์ bat
set "scriptDir=%~dp0"
set "vbsPath=%scriptDir%Facebook_Bot.vbs"

echo กำลังลงทะเบียนงานใน Windows Task Scheduler...
echo พาธสคริปต์: %vbsPath%
echo.

schtasks /create /tn "FacebookBot" /tr "wscript.exe \"%vbsPath%\"" /sc hourly /mo 3 /f

if %errorlevel% equ 0 (
    echo.
    echo [สำเร็จ] ตั้งเวลาให้บอทรันทุก 3 ชั่วโมงเรียบร้อยแล้ว!
    echo บอทจะเริ่มทำงานโดยอัตโนมัติแบบซ่อนหน้าต่าง
) else (
    echo.
    echo [ล้มเหลว] ไม่สามารถตั้งเวลางานได้ กรุณารันไฟล์นี้ในฐานะผู้ดูแลระบบ (Run as Administrator)
)
echo.
pause