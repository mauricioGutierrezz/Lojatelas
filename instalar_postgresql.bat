@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo =================================================================
echo       Instalador de PostgreSQL 16 - Urdimbre
echo =================================================================
echo.
echo Se intentará iniciar el instalador con permisos de Administrador.
echo.
echo Cuando Windows te pregunte:
echo "¿Quieres permitir que esta aplicación haga cambios en el dispositivo?"
echo haz clic en SÍ.
echo.
pause

echo Iniciando instalador con elevación...
powershell -NoProfile -Command "Start-Process '%~dp0instalador_postgres.exe' -Verb RunAs -Wait"

if exist "C:\Program Files\PostgreSQL\16\bin\psql.exe" (
    echo.
    echo =================================================================
    echo ¡PostgreSQL 16 quedó instalado con éxito!
    echo =================================================================
) else (
    echo.
    echo Si no viste la ventana o cancelaste, puedes ejecutar directamente:
    echo     instalador_postgres.exe
    echo haciéndole doble clic en esta carpeta.
)
pause
