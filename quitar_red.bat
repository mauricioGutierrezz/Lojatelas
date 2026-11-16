@echo off
title Quitar red - Urdimbre
cd /d "%~dp0"
net session >nul 2>nul
if not errorlevel 1 goto admin
echo Este paso necesita permiso de administrador. Windows lo va a pedir.
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b 0

:admin
echo Quitando el acceso de otros equipos a Urdimbre...
netsh advfirewall firewall delete rule name="Urdimbre"
echo.
echo [OK] Los otros equipos ya no pueden conectarse a este equipo.
echo Para que la tienda tampoco los espere, ejecuta instalar.bat y
echo responde N en "Varios equipos".
pause
exit /b 0
