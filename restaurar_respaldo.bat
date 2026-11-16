@echo off
title Restaurar respaldo - Urdimbre
cd /d "%~dp0"
echo ========================================================
echo      Restaurar un respaldo de Urdimbre
echo ========================================================
echo.
echo Restaura el respaldo mas reciente en una base NUEVA.
echo La base actual no se modifica ni se borra.
echo Pide la contrasena de postgres.
echo.
.\.venv-windows\Scripts\python.exe -m app_loja.backup_windows --restaurar %*
if errorlevel 1 goto error
echo.
echo [OK] Restauracion terminada. Lee arriba como abrir la tienda con esa base.
pause
exit /b 0

:error
echo.
echo [ERROR] La restauracion no se completo. Revisa el mensaje anterior.
pause
exit /b 1
