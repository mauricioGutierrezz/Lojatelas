@echo off
title Permitir red - Urdimbre
cd /d "%~dp0"
net session >nul 2>nul
if not errorlevel 1 goto admin
echo Este paso necesita permiso de administrador. Windows lo va a pedir.
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b 0

:admin
echo =================================================================
echo   Permitir que otros equipos de la tienda abran Urdimbre
echo =================================================================
echo.
echo Abre el puerto 5000 de este equipo SOLO para la red privada local.
echo No abre nada hacia internet ni toca la base de datos.
echo.
netsh advfirewall firewall delete rule name="Urdimbre" >nul 2>nul
netsh advfirewall firewall add rule name="Urdimbre" dir=in action=allow protocol=TCP localport=5000 profile=private remoteip=localsubnet
if errorlevel 1 goto error
echo.
echo [OK] Puerto abierto para la red privada de la tienda.
echo Si los otros equipos no conectan, revisa que la red de este equipo
echo figure como "Privada" en Configuracion - Red e Internet.
echo Para deshacer este paso ejecuta quitar_red.bat.
pause
exit /b 0

:error
echo.
echo [ERROR] No se pudo crear la regla del firewall.
pause
exit /b 1
