@echo off
rem Remove the udesk-hangul: link.
reg delete "HKCU\Software\Classes\udesk-hangul" /f
pause
