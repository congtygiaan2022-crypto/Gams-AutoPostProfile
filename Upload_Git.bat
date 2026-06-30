@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG KHOI CHAY CONG CU UPLOAD MA NGUON LEN GIT...
echo ====================================================
echo.

python Git_Uploader.py

if %errorlevel% neq 0 (
    echo.
    echo [LOI] Có lỗi xảy ra trong quá trình upload.
    pause
)
