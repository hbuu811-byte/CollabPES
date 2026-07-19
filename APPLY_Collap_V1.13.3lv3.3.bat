@echo off
chcp 65001 >nul
cd /d "%~dp0"
python apply_Collap_V1.13.3lv3.3.py
if errorlevel 1 (
  echo.
  echo Qua trinh sua khong thanh cong. File cu da duoc giu nguyen hoac tu khoi phuc.
  pause
  exit /b 1
)
echo.
echo Hoan tat. Hay commit 3 file app.py, templates\base.html va templates\room_detail.html.
pause
