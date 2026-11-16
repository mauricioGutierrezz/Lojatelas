"""Asistente único de instalación en Windows.

Recorre, en orden, solo los pasos que todavía faltan: base nueva con sus tres
roles, respaldo automático y acceso directo. Se puede ejecutar otra vez sin
riesgo: nunca borra una base ni reemplaza una contraseña existente. Una base
de la versión anterior (sin roles) se archiva con otro nombre, previa
confirmación.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess

import psycopg2

from . import backup_windows, bootstrap_windows, red, windows_secret
from .bootstrap_local import identifier, read_secret

REPOSITORY = Path(__file__).resolve().parents[1]
SHORTCUT = r'''
$ErrorActionPreference = 'Stop'
try {
    $folder = [Environment]::GetFolderPath($env:LOJA_SHORTCUT_FOLDER)
    $link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $folder ($env:LOJA_SHORTCUT_NAME + '.lnk')))
    $link.TargetPath = $env:LOJA_SHORTCUT_TARGET
    $link.Arguments = $env:LOJA_SHORTCUT_ARGUMENTS
    $link.WorkingDirectory = $env:LOJA_SHORTCUT_DIR
    $link.WindowStyle = [int]$env:LOJA_SHORTCUT_STYLE
    $link.Description = 'Abrir Urdimbre'
    $link.Save()
    exit 0
} catch { exit 1 }
'''


def postgres_listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2):
            return True
    except OSError:
        return False


ELEVATE = r'''
$ErrorActionPreference = 'Stop'
try { Start-Process -FilePath $env:LOJA_ELEVATE_TARGET -Verb RunAs -Wait; exit 0 } catch { exit 1 }
'''
URL_FILE = r'''
$ErrorActionPreference = 'Stop'
try {
    $path = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Urdimbre - otros equipos.url'
    Set-Content -LiteralPath $path -Encoding ASCII -Value @('[InternetShortcut]', ('URL=' + $env:LOJA_URL))
    exit 0
} catch { exit 1 }
'''


def powershell(script, **variables):
    executable = Path(os.environ['SystemRoot'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
    environment = {key: os.environ[key] for key in ('SystemRoot', 'PATH', 'TEMP', 'TMP', 'USERPROFILE',
                                                    'APPDATA', 'LOCALAPPDATA', 'OneDrive') if key in os.environ}
    environment.update({key: str(value) for key, value in variables.items()})
    try:
        result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-Command', script],
                                env=environment, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def create_shortcut(target, *, folder='Desktop', name='Urdimbre', arguments='', minimized=False):
    """``folder``: 'Desktop' o 'Startup' (inicio de sesión de esta cuenta Windows)."""
    return powershell(SHORTCUT, LOJA_SHORTCUT_TARGET=target, LOJA_SHORTCUT_DIR=target.parent,
                      LOJA_SHORTCUT_FOLDER=folder, LOJA_SHORTCUT_NAME=name,
                      LOJA_SHORTCUT_ARGUMENTS=arguments, LOJA_SHORTCUT_STYLE=7 if minimized else 1)


def yes(question):
    return input(f'{question} (S/N): ').strip().lower() in ('s', 'si', 'sí')


def configure_network(port=5000):
    """Pregunta si este equipo sirve a otros y deja todo listo para ese modo."""
    current = 'servidor para otros equipos' if red.network_mode() else 'solo este equipo'
    print(f'Modo actual: {current}.')
    if not yes('¿Otros equipos de la tienda van a usar la tienda desde este equipo?'):
        red.set_network_mode(False)
        print('La tienda queda disponible solo en este equipo.')
        return
    red.set_network_mode(True)
    addresses = red.urls(port)
    print('Este equipo es el servidor. En los otros equipos no se instala nada: abren en el navegador')
    for address in addresses:
        print(f'  {address}')
    if addresses and powershell(URL_FILE, LOJA_URL=addresses[0]+'/'):
        print('En el Escritorio quedó "Urdimbre - otros equipos": copialo a los otros equipos.')
    print('Windows bloquea las conexiones entrantes hasta abrir el puerto de la tienda en el firewall,')
    print('solo para la red privada de la tienda.')
    if yes('¿Abrir el puerto ahora? Windows pedirá permiso de administrador'):
        if powershell(ELEVATE, LOJA_ELEVATE_TARGET=REPOSITORY/'permitir_red.bat'):
            print('Listo. Si no se abrió ninguna ventana, ejecutá permitir_red.bat con doble clic.')
        else:
            print('AVISO: no se abrió el puerto. Ejecutá permitir_red.bat con doble clic.')
    else:
        print('Cuando quieras, ejecutá permitir_red.bat con doble clic.')
    if yes('¿Abrir la tienda sola cuando esta cuenta de Windows inicia sesión?'):
        if create_shortcut(REPOSITORY/'iniciar.bat', folder='Startup', arguments='--sin-navegador', minimized=True):
            print('Listo: la tienda se abre minimizada al iniciar sesión en este equipo.')
        else:
            print('AVISO: no se pudo configurar el inicio automático.')


def step(number, text):
    print(f'\n[{number}/4] {text}')


def prepare_database(args, admin_password):
    """Crea la base si falta; archiva la de la versión anterior. Devuelve True si hubo actualización."""
    target = ['--port', str(args.port), '--database', args.database, '--db-user', args.db_user]
    conn = backup_windows.admin_connection(args.port, admin_password)
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s', (args.database,))
            exists = cursor.fetchone() is not None
        if exists:
            if bootstrap_windows.has_roles(conn, args.database, admin_password, args.port):
                print(f'La base {args.database} ya existe: se conserva tal cual.')
                return False
            print(f'La base {args.database} es de la versión anterior, sin los roles')
            print('Administrador, Empleado y Cajero. Para usar la versión nueva se crea una base')
            print('vacía. La base anterior NO se borra: queda archivada con otro nombre.')
            if input("Escribí 'archivar' para continuar: ").strip() != 'archivar':
                raise ValueError('No confirmado. No se cambió nada.')
            print(f'Base anterior archivada como {bootstrap_windows.archive(conn, args.database)}.')
    finally:
        conn.close()
    if exists:
        # Actualización: la role de conexión y su contraseña se conservan sin cambios.
        bootstrap_windows.main(target, admin_password=admin_password, reuse_role=True)
        return True
    db_password = bootstrap_windows.main(target, admin_password=admin_password)
    try:
        windows_secret.save(windows_secret.connection_name('db', args.db_user, args.database, args.port), db_password)
        print('La contraseña de conexión quedó protegida por Windows: iniciar.bat no la pedirá.')
    except (OSError, ValueError):
        print('AVISO: no se pudo proteger la contraseña de conexión; iniciar.bat la pedirá una vez.')
    return False


def main():
    parser = argparse.ArgumentParser(description='Instalar o completar la instalación de la tienda en este equipo.')
    parser.add_argument('--port', type=int, default=5432)
    parser.add_argument('--database', default='urdimbre')
    parser.add_argument('--db-user', default='loja_app')
    args = parser.parse_args()
    try:
        identifier(args.database); identifier(args.db_user)
        if not 1 <= args.port <= 65535:
            raise ValueError('Puerto inválido.')
        if not postgres_listening(args.port):
            raise ValueError(
                f'PostgreSQL no responde en 127.0.0.1:{args.port}.\n'
                '- Si todavía no está instalado: ejecutá instalar_postgresql.bat y volvé a ejecutar instalar.bat.\n'
                '- Si ya está instalado: abrí "Servicios" de Windows e iniciá el servicio postgresql.')

        step(1, 'Base de datos y roles')
        print('Las contraseñas no se ven al escribir. Escribí y pulsá Enter.')
        admin_password = read_secret('Contraseña de postgres definida al instalar PostgreSQL: ')
        if not admin_password:
            raise ValueError('La contraseña administrativa no puede quedar vacía.')
        upgraded = prepare_database(args, admin_password)

        step(2, 'Respaldo automático')
        if backup_windows.configured(args.database, args.port) and not upgraded:
            print('Ya está configurado.')
        else:
            conn = backup_windows.admin_connection(args.port, admin_password)
            try:
                backup_windows.configure(conn, args.database, args.port)
            finally:
                conn.close()
            print(f'Configurado. Cada día, al abrir la tienda, se guarda un respaldo en:\n  {backup_windows.default_dir()}')

        step(3, 'Acceso directo en el Escritorio')
        if create_shortcut(REPOSITORY/'iniciar.bat'):
            print('Listo: "Urdimbre" en el Escritorio abre la tienda.')
        else:
            print('AVISO: no se pudo crear el acceso directo. Abrí la tienda con iniciar.bat.')

        step(4, 'Varios equipos en la red de la tienda')
        configure_network()
    except UnicodeDecodeError:
        parser.exit(1, 'Contraseña de postgres incorrecta o fallo de conexión.\n')
    except ValueError as error:
        parser.exit(1, str(error)+'\n')
    except (OSError, psycopg2.Error) as error:
        detail = str(error).splitlines()[0] if str(error) else 'error'
        parser.exit(1, f'No se pudo conectar o preparar el PostgreSQL local: {detail}\nNo se borró ninguna base.\n')
    print('\nInstalación completa. Entrá a la tienda eligiendo el rol y su contraseña.')


if __name__ == '__main__':
    main()
