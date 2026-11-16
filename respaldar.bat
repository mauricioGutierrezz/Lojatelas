@echo off
title Respaldar - Urdimbre
cd /d "%~dp0"
echo ========================================================
echo        Respaldar la base de Urdimbre
echo ========================================================
echo.
echo Crea ahora una copia de seguridad de la base. La tienda puede
echo seguir abierta. La primera vez pide la contrasena de postgres.
echo.
.\.venv-windows\Scripts\python.exe -m app_loja.backup_windows %*
if errorlevel 1 goto error
echo.
echo [OK] Respaldo terminado.
pause
exit /b 0

:error
echo.
echo [ERROR] No se pudo crear el respaldo. Revisa el mensaje anterior.
pause
exit /b 1
