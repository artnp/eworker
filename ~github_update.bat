@echo off
chcp 65001 >nul
title GitHub Uploader - artnp/eworker
echo.
echo ========================================
echo   Uploading to artnp/eworker (main)
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Github\github_upload.ps1" -Root "%~dp0." -Repo "artnp/eworker" -ExtraExcludePathsCsv "token.ps1,token.txt,.env,kbank_token.txt,secure_config.enc"

if %ERRORLEVEL% equ 0 (
    echo.
    echo Upload complete!
) else (
    echo.
    echo Upload had errors.
)
echo.
pause
