@echo off
title Demostracion
cd /d "%~dp0"
echo ========================================================
echo   Demostracion con datos ficticios (PostgreSQL temporal)
echo ========================================================
echo.
echo No usa ni modifica ninguna base instalada.
echo.
.\.venv-windows\Scripts\python.exe demo.py %*
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo [ERROR] La demostracion no pudo iniciar. Revisa el mensaje anterior.
pause
exit /b 1
