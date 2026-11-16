"""Recuperar la tienda en otro equipo (o en este, tras perder la base) en un solo paso.

Restaura el respaldo más reciente en una base NUEVA con el nombre de siempre,
crea la conexión de la aplicación, deja configurado el respaldo automático y el
acceso directo. Nunca reemplaza una base existente.
"""
import argparse
from datetime import datetime
from pathlib import Path
import secrets

import psycopg2

from . import backup_windows, bootstrap_windows, instalar_windows, windows_secret
from .bootstrap_local import identifier, read_secret


def newest_backup(location, database):
    """Acepta un archivo de respaldo o una carpeta; de la carpeta toma el más reciente."""
    location = Path(location)
    if location.is_file():
        return location
    files = backup_windows.existing(location, database)
    if not files:
        raise ValueError(f'No hay respaldos de {database} en {location}.')
    return files[-1]


def recover(source, port, admin_password, database='urdimbre', user='loja_app'):
    """Restaura y deja la base lista para iniciar.bat. Devuelve True si la base ya usa roles."""
    identifier(database); identifier(user)
    backup_windows.restore(source, database, port, admin_password, app_roles=())
    app_password = secrets.token_urlsafe(32)
    conn = backup_windows.admin_connection(port, admin_password)
    try:
        bootstrap_windows.ensure_app_role(conn, database, user, app_password)
        backup_windows.configure(conn, database, port)
        with_roles = bootstrap_windows.has_roles(conn, database, admin_password, port)
    finally:
        conn.close()
    # La contraseña de conexión es técnica: se genera aquí y queda protegida por Windows.
    windows_secret.save(windows_secret.connection_name('db', user, database, port), app_password)
    return with_roles


def main():
    parser = argparse.ArgumentParser(description='Recuperar la tienda desde un respaldo en este equipo.')
    parser.add_argument('--port', type=int, default=5432)
    parser.add_argument('--database', default='urdimbre')
    parser.add_argument('--db-user', default='loja_app')
    parser.add_argument('--respaldo', help='Archivo de respaldo o carpeta que los contiene (por defecto, Documentos).')
    args = parser.parse_args()
    try:
        identifier(args.database); identifier(args.db_user)
        if not 1 <= args.port <= 65535:
            raise ValueError('Puerto inválido.')
        if not windows_secret.available():
            raise ValueError('La recuperación automática solo existe en Windows.')
        if not instalar_windows.postgres_listening(args.port):
            raise ValueError(f'PostgreSQL no responde en 127.0.0.1:{args.port}. Instalalo con instalar_postgresql.bat '
                             'y volvé a ejecutar recuperar_en_otro_equipo.bat.')
        location = args.respaldo or backup_windows.default_dir()
        if not args.respaldo and not backup_windows.existing(Path(location), args.database):
            print(f'No hay respaldos en {location}.')
            location = input('Escribí la carpeta o el archivo del respaldo (por ejemplo, del pendrive): ').strip().strip('"')
        source = newest_backup(location, args.database)
        made = backup_windows.timestamp(source)
        print(f'Respaldo: {source}')
        if made:
            print(f'Fecha del respaldo: {made:%d/%m/%Y %H:%M}. Lo registrado después de esa hora no está incluido.')
        print(f'Se crea la base {args.database} en este equipo. Si ya existe, no se toca y la recuperación se detiene.')
        if input("Escribí 'recuperar' para continuar: ").strip() != 'recuperar':
            raise ValueError('No confirmado. No se cambió nada.')
        print('Las contraseñas no se ven al escribir.')
        admin_password = read_secret('Contraseña de postgres definida al instalar PostgreSQL: ')
        if not admin_password:
            raise ValueError('La contraseña administrativa no puede quedar vacía.')
        with_roles = recover(source, args.port, admin_password, args.database, args.db_user)
        print(f'\nBase {args.database} recuperada. Respaldo automático configurado en este equipo.')
        if not with_roles:
            print('AVISO: el respaldo es de la versión anterior, sin roles. Ejecutá instalar.bat para actualizar.')
        if instalar_windows.create_shortcut(instalar_windows.REPOSITORY/'iniciar.bat'):
            print('Acceso directo "Urdimbre" creado en el Escritorio.')
        print('\nVarios equipos en la red de la tienda')
        instalar_windows.configure_network()
    except UnicodeDecodeError:
        parser.exit(1, 'Contraseña de postgres incorrecta o fallo de conexión.\n')
    except ValueError as error:
        parser.exit(1, str(error)+'\nNo se modificó ni borró ninguna base existente.\n')
    except (OSError, psycopg2.Error) as error:
        detail = str(error).splitlines()[0] if str(error) else 'error'
        parser.exit(1, f'No se pudo recuperar: {detail}\nNo se borró ninguna base.\n')
    print('\nRecuperación completa. Las contraseñas de Administrador, Empleado y Cajero son las mismas de antes.')
    print(f'Recuperado el {datetime.now():%d/%m/%Y %H:%M}. Abrí la tienda con el acceso directo o iniciar.bat.')


if __name__ == '__main__':
    main()
