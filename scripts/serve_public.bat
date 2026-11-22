@echo off
REM Bam dup file nay de bat server cong khai Hriam. Them tham so -Stop de tat: serve_public.bat -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve_public.ps1" %*
echo.
pause
