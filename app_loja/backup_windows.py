"""Respaldo y restauración locales en Windows.

- El respaldo usa una role propia de solo lectura (``loja_backup``); su
  contraseña es aleatoria y queda cifrada por Windows, nunca en el proyecto.
- La restauración siempre crea una base NUEVA; nunca reemplaza ni borra una
  base existente.
"""
import argparse
from datetime import datetime, timedelta
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading

import psycopg2
from psycopg2 import sql

from . import windows_secret
from .bootstrap_local import identifier, read_secret

BACKUP_ROLE = 'loja_backup'
KEEP_RECENT_HOURS = 48
KEEP_DAYS = 30
HOURLY_MINUTES = 60
QUIET = ("SET log_statement='none'; SET log_min_error_statement='panic'; SET log_min_duration_statement=-1; "
         "SET log_min_duration_sample=-1; SET log_transaction_sample_rate=0")


class NotConfigured(ValueError):
    pass


def pg_tool(name):
    """Ruta de pg_dump/pg_restore: PATH primero, después la instalación estándar."""
    found = shutil.which(name)
    if found:
        return found
    root = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'PostgreSQL'
    candidates = []
    if root.is_dir():
        for version in root.iterdir():
            tool = version/'bin'/f'{name}.exe'
            if tool.is_file() and version.name.isdigit():
                candidates.append((int(version.name), tool))
    if not candidates:
        raise ValueError(f'No se encontró {name}. Instalá PostgreSQL con instalar_postgresql.bat.')
    return str(max(candidates)[1])


def default_dir():
    custom = os.environ.get('LOJA_BACKUP_DIR')
    if custom:
        return Path(custom)
    documents = Path.home()/'Documents'
    if os.name == 'nt':
        try:
            import ctypes
            buffer = ctypes.create_unicode_buffer(260)
            # 5 = CSIDL_PERSONAL: Documentos reales, aunque estén redirigidos.
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
                documents = Path(buffer.value)
        except (OSError, AttributeError):
            pass
    return documents/'Urdimbre - Respaldos'


def secret_name(database, port):
    return windows_secret.connection_name('backup', BACKUP_ROLE, database, port)


def configured(database, port):
    return windows_secret.load(secret_name(database, port)) is not None


def configure(conn, database, port):
    """Crea o renueva la role de respaldo. ``conn``: sesión administrativa local ya verificada."""
    identifier(database)
    password = secrets.token_urlsafe(32)
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,))
        if not cursor.fetchone():
            raise ValueError('La base todavía no existe. Preparala antes de configurar el respaldo.')
        cursor.execute(QUIET)
        cursor.execute("SET password_encryption='scram-sha-256'")
        cursor.execute('SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls '
                       'FROM pg_roles WHERE rolname=%s', (BACKUP_ROLE,))
        row = cursor.fetchone()
        role = sql.Identifier(BACKUP_ROLE)
        if row is None:
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE '
                                   'NOREPLICATION NOBYPASSRLS PASSWORD %s').format(role), (password,))
        elif row[0]:
            raise ValueError('La role de respaldo existente tiene privilegios inesperados; pedí revisión técnica.')
        else:
            cursor.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD %s').format(role), (password,))
        cursor.execute(sql.SQL('GRANT pg_read_all_data TO {}').format(role))
        cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database), role))
    windows_secret.save(secret_name(database, port), password)


def _environment(password):
    environment = {key: os.environ[key] for key in ('SystemRoot', 'PATH', 'TEMP', 'TMP') if key in os.environ}
    # La contraseña viaja solo por el entorno del proceso hijo, nunca por argumentos.
    environment.update(PGPASSWORD=password, PGCLIENTENCODING='UTF8', PGCONNECT_TIMEOUT='5')
    return environment


def _run(command, password, timeout):
    try:
        result = subprocess.run(command, env=_environment(password), capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError('La operación agotó el tiempo de espera.') from None
    if result.returncode:
        detail = (result.stderr.strip().splitlines() or ['sin detalle'])[0].replace(password, '[oculta]')
        raise ValueError(detail)
    return result.stdout


def existing(directory, database):
    pattern = re.compile(re.escape(database)+r'-\d{8}-\d{6}\.dump')
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.is_file() and pattern.fullmatch(path.name))


def timestamp(path):
    """Momento del respaldo según su nombre; None si el nombre no tiene el formato esperado."""
    try:
        return datetime.strptime(path.stem[-15:], '%Y%m%d-%H%M%S')
    except ValueError:
        return None


def prune(directory, database, now=None):
    """Conserva todos los respaldos de las últimas 48 horas y el último de cada día hasta 30 días."""
    moment = now or datetime.now()
    files = existing(directory, database)
    keep, newest_of_day = set(), {}
    for path in files:
        made = timestamp(path)
        if made is None or moment - made <= timedelta(hours=KEEP_RECENT_HOURS):
            keep.add(path)
        elif moment - made <= timedelta(days=KEEP_DAYS):
            if made.date() not in newest_of_day or newest_of_day[made.date()][0] < made:
                newest_of_day[made.date()] = (made, path)
    keep.update(path for _made, path in newest_of_day.values())
    for path in files:
        if path not in keep:
            try:
                path.unlink()
            except OSError:
                pass


def run_backup(database, port, directory=None, *, min_minutes=None, timeout=600, now=None):
    """Crea un respaldo verificado. Devuelve la ruta, o None si ya hay uno más reciente que ``min_minutes``."""
    identifier(database)
    password = windows_secret.load(secret_name(database, port))
    if not password:
        raise NotConfigured('El respaldo todavía no está configurado en esta cuenta Windows.')
    directory = Path(directory) if directory else default_dir()
    moment = now or datetime.now()
    if min_minutes is not None:
        recent = [made for made in map(timestamp, existing(directory, database)) if made is not None]
        if recent and timedelta(0) <= moment - max(recent) < timedelta(minutes=min_minutes):
            return None
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/f'{database}-{moment:%Y%m%d-%H%M%S}.dump'
    pending = target.with_name(target.name+'.partial')
    try:
        _run([pg_tool('pg_dump'), '-h', '127.0.0.1', '-p', str(port), '-U', BACKUP_ROLE, '-d', database,
              '-Fc', '--no-password', '-f', str(pending)], password, timeout)
        # Un archivo que pg_restore no puede listar no cuenta como respaldo.
        if pending.stat().st_size == 0 or not _run([pg_tool('pg_restore'), '-l', str(pending)], password, timeout).strip():
            raise ValueError('El archivo generado no es un respaldo válido.')
        os.replace(pending, target)
    finally:
        try:
            pending.unlink()
        except OSError:
            pass
    prune(directory, database, moment)
    return target


def daily(database, port):
    """Para el inicio de la tienda: nunca impide abrir; devuelve un mensaje para mostrar."""
    try:
        created = run_backup(database, port, min_minutes=HOURLY_MINUTES, timeout=180)
    except NotConfigured:
        return 'AVISO: el respaldo automático no está configurado. Ejecutá respaldar.bat una vez.'
    except (ValueError, OSError) as error:
        return f'AVISO: no se pudo crear el respaldo ({error}). La tienda abre igual; ejecutá respaldar.bat.'
    if created is None:
        return 'Respaldo: ya hay uno de la última hora.'
    return f'Respaldo creado: {created}'


_running = threading.Lock()


def quiet_backup(database, port, min_minutes=None):
    """Respaldo sin interrumpir a nadie: si falla o ya hay uno en curso, no hace nada."""
    if not _running.acquire(blocking=False):
        return None
    try:
        return run_backup(database, port, min_minutes=min_minutes, timeout=300)
    except (ValueError, OSError):
        return None
    finally:
        _running.release()


def background(database, port):
    """Lanza un respaldo en segundo plano (por ejemplo, al confirmar un Cierre)."""
    thread = threading.Thread(target=quiet_backup, args=(database, port), daemon=True)
    thread.start()
    return thread


def hourly(database, port, stop=None, minutes=None):
    """Mientras la tienda esté abierta, un respaldo por hora en segundo plano."""
    minutes = HOURLY_MINUTES if minutes is None else minutes
    stop = stop or threading.Event()

    def loop():
        while not stop.wait(minutes*60):
            quiet_backup(database, port, min_minutes=minutes-1)

    threading.Thread(target=loop, daemon=True).start()
    return stop


def admin_connection(port, admin_password):
    from .bootstrap_windows import destination
    conn = psycopg2.connect(host='127.0.0.1', port=port, dbname='postgres', user='postgres',
                            password=admin_password, connect_timeout=5)
    conn.autocommit = True
    try:
        destination(conn, port)
    except Exception:
        conn.close()
        raise
    return conn


def restore(source, new_database, port, admin_password, *, app_roles=('loja_app', BACKUP_ROLE), timeout=1800):
    """Restaura en una base NUEVA. Si falla después de crearla, la base queda para revisión."""
    from .bootstrap_windows import create_database
    identifier(new_database)
    source = Path(source)
    if not source.is_file():
        raise ValueError('No se encontró el archivo de respaldo.')
    _run([pg_tool('pg_restore'), '-l', str(source)], admin_password, timeout)
    conn = admin_connection(port, admin_password)
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s', (new_database,))
            if cursor.fetchone():
                raise ValueError('Esa base ya existe. La restauración nunca reemplaza una base; elegí otro nombre.')
            for role in ('loja_owner', 'loja_operador', 'loja_admin'):
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                if not cursor.fetchone():
                    cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        create_database(conn, new_database)
        try:
            _run([pg_tool('pg_restore'), '-h', '127.0.0.1', '-p', str(port), '-U', 'postgres', '-d', new_database,
                  '--no-password', '--exit-on-error', str(source)], admin_password, timeout)
        except ValueError as error:
            raise ValueError(f'Restauración incompleta ({error}). La base nueva {new_database} se preservó para '
                             'revisión; la base original no fue modificada.') from None
        with conn.cursor() as cursor:
            for role in app_roles:
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                if cursor.fetchone():
                    cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(
                        sql.Identifier(new_database), sql.Identifier(role)))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Respaldar la base local o restaurar un respaldo en una base nueva.')
    parser.add_argument('--database', default='urdimbre')
    parser.add_argument('--port', type=int, default=5432)
    parser.add_argument('--destino', help='Carpeta de respaldos (por defecto, Documentos).')
    parser.add_argument('--restaurar', action='store_true', help='Restaurar en una base nueva.')
    parser.add_argument('--archivo', help='Respaldo a restaurar (por defecto, el más reciente).')
    parser.add_argument('--nueva-base', help='Nombre de la base nueva para restaurar.')
    args = parser.parse_args()
    directory = Path(args.destino) if args.destino else default_dir()
    try:
        identifier(args.database)
        if not 1 <= args.port <= 65535:
            raise ValueError('Puerto inválido.')
        if args.restaurar:
            files = existing(directory, args.database)
            source = Path(args.archivo) if args.archivo else (files[-1] if files else None)
            if source is None:
                raise ValueError(f'No hay respaldos en {directory}.')
            new_database = args.nueva_base or f'{args.database}_restaurada_{datetime.now():%Y%m%d_%H%M}'
            print(f'Respaldo: {source}')
            print(f'Base NUEVA a crear: {new_database} · 127.0.0.1:{args.port}')
            print('La base actual no se modifica ni se borra.')
            if input("Escribí 'restaurar' para continuar: ").strip() != 'restaurar':
                raise ValueError('Restauración no confirmada. No se creó nada.')
            admin_password = read_secret('Contraseña de postgres definida al instalar PostgreSQL: ')
            restore(source, new_database, args.port, admin_password)
            print(f'Restauración terminada en la base {new_database}.')
            print(f'Para abrir la tienda con esa base: iniciar.bat --database {new_database}')
            return
        if not configured(args.database, args.port):
            print('Primera vez: se crea un usuario de solo lectura para los respaldos.')
            admin_password = read_secret('Contraseña de postgres definida al instalar PostgreSQL: ')
            conn = admin_connection(args.port, admin_password)
            try:
                configure(conn, args.database, args.port)
            finally:
                conn.close()
            print('Respaldo automático configurado. No se volverá a pedir esta contraseña.')
        created = run_backup(args.database, args.port, directory)
    except UnicodeDecodeError:
        parser.exit(1, 'Contraseña de postgres incorrecta o fallo de conexión.\n')
    except (ValueError, OSError, psycopg2.Error) as error:
        parser.exit(1, f'{str(error).splitlines()[0] if str(error) else "Error"}\nNo se modificó ni borró ninguna base.\n')
    print(f'Respaldo creado: {created}')
    print(f'Se conservan todos los de las últimas {KEEP_RECENT_HOURS} horas y uno por día hasta {KEEP_DAYS} días.')
    print('Copiá esta carpeta también a un pendrive o a la nube.')


if __name__ == '__main__':
    main()
