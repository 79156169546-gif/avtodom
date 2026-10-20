@echo off
setlocal
rem === Останавливаем API (8000) и витрину (5173) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 8000
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 5173
echo [autodom] Stopped.
echo.
pause
endlocal
