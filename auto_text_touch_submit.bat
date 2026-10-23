@echo off
chcp 65001 >nul
title Text-Touch: Submitting Point to Cloud...
echo ==============================================
echo   Text-Touch: กำลังพาดลายน้ำและส่งงานให้ลูกค้า
echo ==============================================

python "%~dp0text_touch_engine.py" --submit
if %errorlevel% neq 0 (
    echo [!] เกิดข้อผิดพลาดในการประมวลผล
    pause
) else (
    echo [OK] ส่งงานให้ลูกค้าเรียบร้อยแล้ว!
    timeout /t 3 >nul
)
exit /b
