@echo off
title Urdimbre - NO CERRAR (se puede minimizar)
cd /d "%~dp0"
echo ========================================================
echo        Iniciando Urdimbre (Windows)
echo ========================================================
echo.
.\.venv-windows\Scripts\python.exe -m app_loja.start_windows %*
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo Ocurrio un error al iniciar la aplicacion.
echo Si es la primera vez en este equipo, ejecuta instalar.bat.
pause
exit /b 1
