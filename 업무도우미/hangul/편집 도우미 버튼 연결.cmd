@echo off
rem Register udesk-hangul: link so the web panel button can open the exam helper. Current user only.
set K=HKCU\Software\Classes\udesk-hangul
reg add "%K%" /ve /d "URL:udesk-hangul" /f >nul
reg add "%K%" /v "URL Protocol" /d "" /f >nul
reg add "%K%\shell\open\command" /ve /d "powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File \"%~dp0exam-helper.ps1\"" /f >nul
if errorlevel 1 (echo FAILED) else (echo OK - now the panel button opens the helper.)
pause
