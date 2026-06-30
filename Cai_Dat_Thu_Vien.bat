@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG TU DONG CAI DAT CAC THU VIEN BAT BUOC...
echo ====================================================
echo.

pip install -r requirements.txt

echo.
if %errorlevel% equ 0 goto SUCCESS
goto FAIL

:SUCCESS
echo ====================================================
echo   CAI DAT THU VIEN THANH CONG!
echo   Bay gio ban co the mo file 'Chay_Tool.bat' de chay.
echo ====================================================
goto END

:FAIL
echo ====================================================
echo   [LOI] Cai dat thu vien that bai.
echo   Vui long kiem tra:
echo   1. May da cai dat Python va tick chon "Add Python to PATH"
echo   2. Co ket noi Internet.
echo ====================================================
goto END

:END
echo.
pause
