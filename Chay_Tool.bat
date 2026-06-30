@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ====================================================
echo   DANG TU DONG DONG BO VA KHOI CHAY PHAN MEM...
echo ====================================================
echo.

python launcher_git.py

if %errorlevel% neq 0 goto FAIL
goto END

:FAIL
echo.
echo ====================================================
echo   [LOI] Khong the khoi chay Tool.
echo   Vui long kiem tra:
echo   1. May tinh da cai dat Python (tick chon Add to PATH).
echo   2. May tinh da cai dat phan mem Git.
echo   3. Da chay file 'Cai_Dat_Thu_Vien.bat' truoc do.
echo ====================================================
echo.
pause

:END
