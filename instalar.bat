@echo off
title Instalar - Urdimbre
cd /d "%~dp0"
echo =================================================================
echo            Instalar Urdimbre en este equipo
echo =================================================================
echo.
echo Este asistente hace solo los pasos que falten. Se puede volver a
echo ejecutar sin riesgo: nunca borra una base ni reemplaza una
echo contrasena existente.
echo.

if exist ".venv-windows\Scripts\python.exe" goto dependencies

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto create_venv
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto create_venv
echo [ERROR] No se encontro Python.
echo Instala Python 3.13 desde https://www.python.org/downloads/ marcando
echo "Add python.exe to PATH" y vuelve a ejecutar instalar.bat.
goto error

:create_venv
echo Creando el entorno de Python de la tienda...
%PY% -m venv .venv-windows
if errorlevel 1 goto error

:dependencies
.\.venv-windows\Scripts\python.exe -c "import flask, psycopg2, PIL, waitress" >nul 2>nul
if not errorlevel 1 goto wizard
echo Instalando dependencias (requiere internet solo esta vez)...
.\.venv-windows\Scripts\python.exe -m pip install --disable-pip-version-check -r app_loja\requirements.txt
if errorlevel 1 goto error

:wizard
.\.venv-windows\Scripts\python.exe -m app_loja.instalar_windows %*
if errorlevel 1 goto error
echo.
echo =================================================================
echo [OK] Todo listo. Para abrir la tienda usa el acceso directo
echo "Urdimbre" del Escritorio, o iniciar.bat.
echo =================================================================
echo.
set "ABRIR="
set /p "ABRIR=Abrir la tienda ahora? (S/N): "
if /i "%ABRIR%"=="S" call "%~dp0iniciar.bat"
exit /b 0

:error
echo.
echo =================================================================
echo [ERROR] La instalacion no se completo. Revisa el mensaje anterior.
echo No se borro nada. Corregi el problema y ejecuta instalar.bat otra vez.
echo Si el mensaje dice que una base creada fue preservada, pedi revision
echo tecnica antes de repetir.
echo =================================================================
echo.
pause
exit /b 1
