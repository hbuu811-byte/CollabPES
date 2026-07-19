@echo off
chcp 65001 >nul
cd /d "%~dp0"
python apply_Collap_V1.13.3lv3.4.py
if errorlevel 1 (
  echo.
  echo Co loi. File cu da duoc giu nguyen hoac tu dong khoi phuc.
) else (
  echo.
  echo Da hoan thanh Collap_V1.13.3lv3.4.
)
pause
