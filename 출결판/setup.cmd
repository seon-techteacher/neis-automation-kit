@echo off
title NEIS Attendance Widget Setup (offline)
cd /d "%~dp0"
if not exist "%~dp0files\install.ps1" (
  echo.
  echo  [!] Please EXTRACT the zip first: right-click the zip - "Extract All", then run setup.cmd in the extracted folder.
  echo.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0files\install.ps1"
