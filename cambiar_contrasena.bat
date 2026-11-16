@echo off
title Cambiar contrasena - Urdimbre
cd /d "%~dp0"
echo ========================================================
echo     Cambiar la contrasena de un rol de la tienda
echo ========================================================
echo.
echo Pide la contrasena de postgres y la contrasena nueva del rol.
echo Las contrasenas no se ven al escribir.
echo.
.\.venv-windows\Scripts\python.exe -m app_loja.cambiar_contrasena %*
if errorlevel 1 goto error
echo.
echo [OK] Contrasena cambiada.
pause
exit /b 0

:error
echo.
echo [ERROR] La contrasena no se cambio. Revisa el mensaje anterior.
pause
exit /b 1
