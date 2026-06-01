@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   ĐANG TỰ ĐỘNG ĐỒNG BỘ VÀ TẢI PHẦN MỀM MỚI TINH...
echo ====================================================
echo.

python launcher_git.py

if %errorlevel% neq 0 (
    echo.
    echo ====================================================
    echo   [LỖI] Không thể khởi chạy Tool.
    echo   Vui lòng kiểm tra:
    echo   1. Máy tính đã cài đặt Python (tích chọn Add to PATH) chưa.
    echo   2. Máy tính đã cài đặt phần mềm Git chưa.
    echo   3. Đã chạy file 'Cai_Dat_Thu_Vien.bat' trước đó chưa.
    echo ====================================================
    echo.
    pause
)
