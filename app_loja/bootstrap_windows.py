"""Instalación nueva en PostgreSQL local TCP; sin sudo ni secretos en archivos."""
import argparse
from datetime import datetime

import psycopg2
from psycopg2 import sql

from . import permisos
from .bootstrap_local import check_new, identifier, password, read_secret
from .install_schema import initialize

# Categorías de la tienda creadas por la instalación (un único nivel).
CATEGORIAS = ('Accesorios', 'Telas por peso', 'Telas de punto', 'Telas sintéticas')
QUIET = ("SET log_statement='none'; SET log_min_error_statement='panic'; SET log_min_duration_statement=-1; "
         "SET log_min_duration_sample=-1; SET log_transaction_sample_rate=0")


def destination(conn, port):
    with conn.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_setting('port'),host(inet_server_addr()),current_setting('is_superuser')")
        if cursor.fetchone() != ('postgres', str(port), '127.0.0.1', 'on'):
            raise ValueError('Destino técnico diferente del PostgreSQL local esperado.')


def create_database(conn, database):
    with conn.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'").format(sql.Identifier(database)))


def valid_passwords(passwords):
    roles = {perfil for _login, perfil in permisos.CUENTAS}
    return (isinstance(passwords, dict) and set(passwords) == roles
            and all(value and len(value.encode('utf-8')) <= 72 for value in passwords.values()))


def install(conn, *, port, database, user, admin_password, db_password, passwords,
            categories=CATEGORIAS, reuse_role=False):
    """Crea la base con las tres cuentas de rol.

    ``reuse_role``: actualización explícita desde una instalación anterior; la
    role LOGIN existente y su contraseña se conservan sin cambios.
    """
    if not categories or not all(c.strip() for c in categories):
        raise ValueError('Faltan las categorías de la tienda.')
    if not valid_passwords(passwords) or (not reuse_role and not db_password):
        raise ValueError('Contraseñas inválidas.')
    conn.autocommit = True
    destination(conn, port)
    with conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(hashtextextended('loja-bootstrap-local',0))")
    try:
        check_new(conn, database, user, reuse_role=reuse_role)
        create_database(conn, database)
        try:
            with psycopg2.connect(host='127.0.0.1', port=port, dbname=database,
                                  user=conn.get_dsn_parameters()['user'], password=admin_password,
                                  connect_timeout=5) as target:
                initialize(target, database=database, port=port, host='127.0.0.1')
                with target.cursor() as cursor:
                    # Solo la sesión técnica: no registrar SQL que contiene credenciales.
                    cursor.execute(QUIET)
                    for category in categories:
                        cursor.execute('INSERT INTO public.tipos_tela(nome) VALUES(%s) ON CONFLICT(nome) DO NOTHING', (category.strip(),))
                    for login, perfil in permisos.CUENTAS:
                        cursor.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) "
                                       "VALUES(%s,%s,public.crypt(%s,public.gen_salt('bf',12)),%s)",
                                       (permisos.NOMBRES[perfil], login, passwords[perfil], perfil))
                    if not reuse_role:
                        cursor.execute("SET LOCAL password_encryption='scram-sha-256'")
                        cursor.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s').format(sql.Identifier(user)), (db_password,))
                    cursor.execute(sql.SQL('GRANT loja_operador TO {}').format(sql.Identifier(user)))
                    cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database), sql.Identifier(user)))
        except Exception as e:
            raise ValueError(f'Instalación incompleta ({e}). La base creada se preservó. No la borres ni repitas la instalación; pedí revisión técnica.') from None
    finally:
        try:
            conn.rollback()
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(hashtextextended('loja-bootstrap-local',0))")
        except Exception:
            pass


def has_roles(conn, database, admin_password, port):
    """True si la base ya usa los tres roles; False si es de la versión anterior."""
    with psycopg2.connect(host='127.0.0.1', port=port, dbname=database, user=conn.get_dsn_parameters()['user'],
                          password=admin_password, connect_timeout=5) as target, target.cursor() as cursor:
        cursor.execute("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                       "WHERE c.conrelid=to_regclass('public.usuarios') AND c.contype='c'")
        definitions = [row[0] for row in cursor.fetchall()]
    if not definitions:
        raise ValueError('La base existente no es una instalación reconocida de la tienda. No se modificó nada.')
    return any("'cajero'" in definition for definition in definitions)


def archive(conn, database, now=None):
    """Renombra la base anterior; no borra datos. Exige que la tienda esté cerrada."""
    identifier(database)
    archived = f'{database}_anterior_{(now or datetime.now()):%Y%m%d_%H%M%S}'
    identifier(archived)
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s', (database,))
        if cursor.fetchone()[0]:
            raise ValueError('La tienda está abierta. Cerrá su ventana (y pgAdmin, si está abierto) y volvé a intentar.')
        cursor.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(database), sql.Identifier(archived)))
    return archived


def ask_role_passwords():
    print('Elegí una contraseña para cada rol. Se usan al entrar a la tienda.')
    return {perfil: password(f'Nueva contraseña del rol {permisos.NOMBRES[perfil]}: ', bcrypt=True)
            for _login, perfil in permisos.CUENTAS}


def main(argv=None, admin_password=None, reuse_role=False):
    """Devuelve la contraseña de conexión elegida, solo para el asistente que la protege con Windows."""
    parser = argparse.ArgumentParser(description='Primera instalación Windows en PostgreSQL local. Nunca reemplaza una base existente.')
    parser.add_argument('--port', type=int, default=5432)
    parser.add_argument('--database', default='urdimbre')
    parser.add_argument('--db-user', default='loja_app')
    args = parser.parse_args(argv)
    db_password = None
    try:
        identifier(args.database); identifier(args.db_user)
        if not 1 <= args.port <= 65535:
            raise ValueError('Puerto inválido.')
        if admin_password is None:
            admin_password = read_secret('Contraseña de postgres definida al instalar PostgreSQL: ')
        if not admin_password:
            raise ValueError('La contraseña administrativa no puede quedar vacía.')
        conn = psycopg2.connect(host='127.0.0.1', port=args.port, dbname='postgres',
                                user='postgres', password=admin_password, connect_timeout=5)
        conn.autocommit = True
        try:
            destination(conn, args.port)
            check_new(conn, args.database, args.db_user, reuse_role=reuse_role)
            conn.rollback()
            print(f'Destino NUEVO: {args.database} · 127.0.0.1:{args.port}')
            confirmacion = input(f"Escribí exactamente '{args.database}' para confirmar: ").strip()
            if confirmacion != args.database:
                raise ValueError(f"Destino no confirmado (escribiste '{confirmacion}' en vez de '{args.database}'). No se creó nada.")
            if not reuse_role:
                db_password = password('Nueva contraseña de conexión de la aplicación: ')
            passwords = ask_role_passwords()
            install(conn, port=args.port, database=args.database, user=args.db_user,
                    admin_password=admin_password, db_password=db_password, passwords=passwords,
                    reuse_role=reuse_role)
        finally:
            conn.close()
    except UnicodeDecodeError:
        parser.exit(1, 'Contraseña de postgres incorrecta o fallo de conexión.\n')
    except ValueError as error:
        parser.exit(1, str(error)+'\n')
    except (OSError, psycopg2.Error) as error:
        parser.exit(1, f'Detalle del error en PostgreSQL: {error}\nNo se pudo conectar o preparar el PostgreSQL local. No se borró ninguna base.\n')
    print('Base de datos inicializada con los roles Administrador, Empleado y Cajero.')
    print('Categorías: ' + ', '.join(CATEGORIAS))
    print('Las contraseñas no se guardaron en archivos del proyecto.')
    return db_password


if __name__ == '__main__':
    main()
