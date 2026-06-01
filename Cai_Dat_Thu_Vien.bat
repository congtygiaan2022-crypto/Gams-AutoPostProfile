@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   ĐANG TỰ ĐỘNG CÀI ĐẶT CÁC THƯ VIỆN BẮT BUỘC...
echo ====================================================
echo.

pip install -r requirements.txt

echo.
if %errorlevel% equ 0 (
    echo ====================================================
    echo   CÀI ĐẶT THƯ VIỆN THÀNH CÔNG!
    echo   Bây giờ bạn có thể mở file 'Chay_Tool.bat' để chạy ứng dụng.
    echo ====================================================
) else (
    echo ====================================================
    echo   [LỖI] Cài đặt thư viện thất bại.
    echo   Vui lòng kiểm tra xem bạn đã cài đặt Python (tích chọn Add to PATH) chưa.
    echo ====================================================
)

echo.
pause
