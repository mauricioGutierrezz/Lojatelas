@echo off
title Pruebas - Urdimbre
cd /d "%~dp0"
echo ========================================================
echo   Pruebas de Urdimbre (PostgreSQL descartable)
echo ========================================================
echo.
echo Usa un PostgreSQL temporal en otro puerto. No toca la base
echo instalada. Tarda algunos minutos.
echo.
.\.venv-windows\Scripts\python.exe tests\run_windows.py
if errorlevel 1 goto error
pause
exit /b 0

:error
echo.
echo [ERROR] Hubo pruebas con fallas. Revisa el detalle anterior.
pause
exit /b 1
