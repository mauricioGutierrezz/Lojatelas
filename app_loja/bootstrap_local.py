"""Primera instalación explícita; nunca reemplaza bases ni roles LOGIN existentes."""
import argparse
from getpass import GetPassWarning, getpass
from pathlib import Path
import re
import warnings
import subprocess

import psycopg2
from psycopg2 import sql

from .install_schema import initialize


def identifier(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', value) or value in ('postgres', 'template0', 'template1'):
        raise ValueError('Usá un nombre local explícito, de hasta 63 caracteres.')
    return value


def read_secret(prompt):
    # Nunca aceitar o fallback que ecoa a senha quando não há terminal seguro.
    with warnings.catch_warnings():
        warnings.simplefilter('error', GetPassWarning)
        try:
            return getpass(prompt)
        except GetPassWarning:
            raise ValueError('Se requiere un terminal interactivo que oculte la contraseña.') from None


def password(prompt, *, bcrypt=False):
    value = read_secret(prompt)
    if not value or (bcrypt and len(value.encode('utf-8')) > 72):
        raise ValueError('La contraseña no puede quedar vacía; la de operación admite hasta 72 bytes.')
    if value != read_secret('Repetir contraseña: '):
        raise ValueError('Las contraseñas no coinciden.')
    return value


def local_destination(conn, socket, port):
    if not Path(socket).is_absolute():
        raise ValueError('Se requiere un socket local absoluto; no se admiten servidores remotos.')
    with conn.cursor() as c:
        c.execute("SELECT current_database(),current_setting('port'),current_setting('unix_socket_directories'),inet_server_addr(),current_setting('is_superuser')")
        database, actual_port, sockets, address, superuser = c.fetchone()
        if database != 'postgres' or str(port) != actual_port or socket not in sockets.split(',') or address is not None or superuser != 'on':
            raise ValueError('Destino o permisos del instalador diferentes de los esperados.')


def check_new(conn, database, user, *, reuse_role=False):
    """``reuse_role``: actualización explícita que conserva la role LOGIN y su contraseña."""
    identifier(database); identifier(user)
    if user in ('loja_owner', 'loja_operador', 'loja_admin'):
        raise ValueError('La conexión operativa debe tener una role LOGIN propia.')
    with conn.cursor() as c:
        c.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,))
        if c.fetchone():
            raise ValueError('La base ya existe. No se modificó ni eliminó nada.')
        c.execute('SELECT rolcanlogin AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls) '
                  'FROM pg_roles WHERE rolname=%s', (user,))
        role = c.fetchone()
        if reuse_role:
            if role is None or not role[0]:
                raise ValueError('La role LOGIN de la instalación anterior no existe o tiene privilegios inesperados.')
        elif role:
            raise ValueError('La role LOGIN ya existe. No se modificó su contraseña ni sus permisos.')
        c.execute("SELECT 1 FROM pg_roles WHERE rolname IN ('loja_owner','loja_operador','loja_admin') AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)")
        if c.fetchone():
            raise ValueError('Roles existentes incompatibles; se requiere revisión técnica.')
        c.execute("SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname IN ('loja_owner','loja_operador','loja_admin')")
        if c.fetchone():
            raise ValueError('Membresías internas inesperadas; no se cambiaron permisos.')


def install(conn, *, socket, port, database, user, db_password, name, login, app_password, categories, installer_password=""):
    """Conn es una conexión técnica a postgres; los secretos solo viven en memoria."""
    if not name.strip() or not login.strip() or not categories or not all(n.strip() for n in categories):
        raise ValueError('Informá nombre, login y las categorías existentes de la tienda.')
    if not db_password or not app_password or len(app_password.encode('utf-8')) > 72:
        raise ValueError('Contraseñas inválidas.')
    conn.autocommit = True
    local_destination(conn, socket, port)
    with conn.cursor() as c:
        # Serializa dos ejecuciones del mismo procedimiento, antes de crear nada.
        c.execute("SELECT pg_advisory_lock(hashtextextended('loja-bootstrap-local',0))")
    try:
        check_new(conn, database, user)
        with conn.cursor() as c:
            c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0 ENCODING %s').format(sql.Identifier(database)), ('UTF8',))
        try:
            params = conn.get_dsn_parameters()
            with psycopg2.connect(host=socket, port=port, dbname=database, user=params['user'], password=installer_password) as target:
                initialize(target, database=database, port=port, socket=socket)
                with target.cursor() as c:
                    c.execute("SET log_statement='none'; SET log_min_error_statement='panic'; SET log_min_duration_statement=-1; SET log_min_duration_sample=-1; SET log_transaction_sample_rate=0")
                    for category in categories:
                        c.execute('INSERT INTO public.tipos_tela(nome) VALUES (%s) ON CONFLICT(nome) DO NOTHING', (category.strip(),))
                    c.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES(%s,%s,public.crypt(%s,public.gen_salt('bf',12)),'admin')", (name.strip(), login.strip(), app_password))
                    c.execute("SET LOCAL password_encryption='scram-sha-256'")
                    c.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s').format(sql.Identifier(user)), (db_password,))
                    c.execute(sql.SQL('GRANT loja_operador TO {}').format(sql.Identifier(user)))
                    c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database), sql.Identifier(user)))
        except Exception:
            # No DROP ni limpieza automática: una base creada permanece para revisión.
            raise ValueError('Instalación incompleta. La base creada se preservó; no vuelvas a ejecutar ni borres nada sin revisión técnica.') from None
    finally:
        with conn.cursor() as c:
            c.execute("SELECT pg_advisory_unlock(hashtextextended('loja-bootstrap-local',0))")


def literal(value):
    if '\x00' in value:
        raise ValueError('El texto contiene un carácter no admitido.')
    return "'" + value.replace("'", "''") + "'"


def guard_sql(socket, port, database, user):
    identifier(database); identifier(user)
    if (user in ('loja_owner', 'loja_operador', 'loja_admin') or not Path(socket).is_absolute()
        or ',' in socket or not 1 <= port <= 65535):
        raise ValueError('Destino o role operativa inválidos.')
    tag = '$guard$'
    while tag in socket:
        tag = tag[:-1] + '_$'
    return f"""SET standard_conforming_strings=on;
DO {tag}
BEGIN
 IF current_database()<>'postgres' OR current_setting('port')<>{literal(str(port))}
 OR NOT {literal(socket)}=ANY(string_to_array(current_setting('unix_socket_directories'),','))
 OR inet_server_addr() IS NOT NULL OR current_setting('is_superuser')<>'on' THEN
  RAISE EXCEPTION 'Destino técnico diferente del esperado.';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_database WHERE datname={literal(database)})
 OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname={literal(user)}) THEN
  RAISE EXCEPTION 'La base o la role LOGIN ya existe.';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN ('loja_owner','loja_operador','loja_admin')
 AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
 OR EXISTS(SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
 WHERE r.rolname IN ('loja_owner','loja_operador','loja_admin')) THEN
  RAISE EXCEPTION 'Roles internas incompatibles.';
 END IF;
END; {tag};
"""


class AdminSQL:
    """Solo psql del sistema se eleva; no accede a archivos del proyecto."""
    def __init__(self, socket, port):
        self.socket, self.port = socket, port

    def execute(self, source):
        command = ['sudo', '-n', '-u', 'postgres', '--', '/usr/bin/psql', '-X',
                   '--no-password', '-q', '-v', 'ON_ERROR_STOP=1',
                   '-h', self.socket, '-p', str(self.port), '-U', 'postgres',
                   '-d', 'postgres', '-f', '-']
        # No heredar PG*, servicios ni opciones que cambien el destino técnico.
        result = subprocess.run(command, input=source, text=True, capture_output=True,
                                cwd='/', env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        if result.returncode:
            # stderr puede contener líneas SQL: nunca mostrarlo ni guardar secretos.
            raise ValueError('Operación rechazada: revisá sudo, destino, base nueva y role nueva. Cualquier base creada se preservó; no se borró nada.')


def install_elevated(admin, *, socket, port, database, user, db_password, name, login, app_password, categories):
    if not name.strip() or not login.strip() or not categories or not all(n.strip() for n in categories):
        raise ValueError('Informá nombre, login y categorías existentes.')
    if not db_password or not app_password or len(app_password.encode('utf-8'))>72:
        raise ValueError('Contraseñas inválidas.')
    from .install_schema import destination_source
    configuration = "BEGIN;\nSET LOCAL password_encryption='scram-sha-256';\n"
    for category in categories:
        configuration += f"INSERT INTO public.tipos_tela(nome) VALUES({literal(category.strip())}) ON CONFLICT(nome) DO NOTHING;\n"
    configuration += f"""INSERT INTO public.usuarios(nome,login,senha_hash,perfil)
VALUES({literal(name.strip())},{literal(login.strip())},public.crypt({literal(app_password)},public.gen_salt('bf',12)),'admin');
CREATE ROLE {user} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {literal(db_password)};
GRANT loja_operador TO {user};
GRANT CONNECT ON DATABASE {database} TO {user};
COMMIT;
"""
    source = "SELECT pg_advisory_lock(hashtextextended('loja-bootstrap-local',0));\n"
    source += guard_sql(socket, port, database, user)
    source += f"CREATE DATABASE {database} TEMPLATE template0 ENCODING 'UTF8';\n\\connect {database}\n"
    # \connect abre outra sessão. Desativar logging nesta sessão ANTES de
    # qualquer SQL com credenciais, inclusive o relatório de statements em falha.
    source += "SET log_statement='none'; SET log_min_error_statement='panic';\n"
    source += "SET log_min_duration_statement=-1; SET log_min_duration_sample=-1; SET log_transaction_sample_rate=0;\n"
    source += destination_source(database=database, port=port, socket=socket)
    source += configuration
    admin.execute(source)


def main():
    parser = argparse.ArgumentParser(description='Primera instalación local; Python sin elevación, solamente psql usa sudo.')
    parser.add_argument('--socket', required=True)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--database', required=True)
    parser.add_argument('--db-user', default='loja_app')
    args = parser.parse_args()
    try:
        preflight = guard_sql(args.socket,args.port,args.database,args.db_user)
        # sudo pide su propia contraseña en el terminal, nunca por el pipe SQL.
        subprocess.run(['sudo','-v'],cwd='/',check=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        admin = AdminSQL(args.socket,args.port)
        admin.execute(preflight)
        print(f'Destino NUEVO: {args.database} · puerto {args.port} · socket {args.socket}')
        if input('Escribí el nombre de la base para confirmar: ').strip()!=args.database:
            raise ValueError('Destino no confirmado; no se creó nada.')
        name = input('Nombre operativo: ').strip()
        login = input('Login operativo: ').strip()
        categories = input('Categorías existentes, separadas por coma: ').split(',')
        db_password = password('Nueva contraseña de conexión PostgreSQL: ')
        app_password = password('Nueva contraseña de operación: ',bcrypt=True)
        install_elevated(admin,socket=args.socket,port=args.port,database=args.database,user=args.db_user,
                         db_password=db_password,name=name,login=login,app_password=app_password,categories=categories)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1,(str(error) if isinstance(error,ValueError) else 'No se pudo ejecutar sudo/psql local.')+'\n')
    print('Instalación terminada. No se guardaron secretos en archivos.')
    print(f'DB_HOST=127.0.0.1\nDB_PORT={args.port}\nDB_NAME={args.database}\nDB_USER={args.db_user}')
    print('DB_PASSWORD: la contraseña de conexión ingresada; pedila sin eco al iniciar.')


if __name__ == '__main__':
    main()
