@echo off
title Preparar Base de Datos - Urdimbre
cd /d "%~dp0"
echo =================================================================
echo       Preparar Base de Datos Urdimbre (Windows)
echo =================================================================
echo.
echo NOTA: Al escribir contrasenas, por seguridad NO se veran letras
echo ni asteriscos en pantalla. Simplemente escribe y pulsa Enter.
echo.
.\.venv-windows\Scripts\python.exe -m app_loja.bootstrap_windows
if errorlevel 1 goto error
echo.
echo =================================================================
echo [OK] Base de datos creada e inicializada.
echo =================================================================
echo.
echo SIGUIENTE PASO: ejecuta iniciar.bat.
echo No vuelvas a ejecutar este bootstrap.
echo.
pause
exit /b 0

:error
echo.
echo =================================================================
echo [ERROR] No se pudo completar el bootstrap de la base de datos.
echo Revisa el mensaje de error que aparecio arriba antes de cerrar.
echo Si indica que la base creada fue preservada, no repitas el bootstrap.
echo Solicita revision tecnica para continuar sin borrar esa base.
echo =================================================================
echo.
echo No ejecutes "iniciar.bat" hasta resolver el error.
echo.
pause
exit /b 1
