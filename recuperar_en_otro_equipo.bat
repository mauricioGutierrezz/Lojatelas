@echo off
title Recuperar - Urdimbre
cd /d "%~dp0"
echo =================================================================
echo     Recuperar Urdimbre desde un respaldo en este equipo
echo =================================================================
echo.
echo Para un equipo nuevo o tras perder la base. Restaura el respaldo
echo mas reciente. Nunca reemplaza ni borra una base existente.
echo Antes: instalar Python y PostgreSQL (instalar_postgresql.bat) y
echo tener a mano la carpeta de respaldos.
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
echo "Add python.exe to PATH" y vuelve a ejecutar recuperar_en_otro_equipo.bat.
goto error

:create_venv
echo Creando el entorno de Python de la tienda...
%PY% -m venv .venv-windows
if errorlevel 1 goto error

:dependencies
.\.venv-windows\Scripts\python.exe -c "import flask, psycopg2, PIL, waitress" >nul 2>nul
if not errorlevel 1 goto recover
echo Instalando dependencias (requiere internet solo esta vez)...
.\.venv-windows\Scripts\python.exe -m pip install --disable-pip-version-check -r app_loja\requirements.txt
if errorlevel 1 goto error

:recover
.\.venv-windows\Scripts\python.exe -m app_loja.recuperar_windows %*
if errorlevel 1 goto error
echo.
echo [OK] Tienda recuperada.
pause
exit /b 0

:error
echo.
echo [ERROR] La recuperacion no se completo. Revisa el mensaje anterior.
echo No se borro nada.
pause
exit /b 1
