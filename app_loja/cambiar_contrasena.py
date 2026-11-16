"""Cambiar la contraseña de un rol de la tienda. Requiere la contraseña de postgres."""
import argparse

import psycopg2

from . import permisos
from .bootstrap_local import identifier, password, read_secret
from .bootstrap_windows import QUIET, destination


def change(admin_password, port, database, login, new_password):
    if not new_password or len(new_password.encode('utf-8')) > 72:
        raise ValueError('Contraseña inválida.')
    conn = psycopg2.connect(host='127.0.0.1', port=port, dbname='postgres', user='postgres',
                            password=admin_password, connect_timeout=5)
    try:
        conn.autocommit = True
        destination(conn, port)
    finally:
        conn.close()
    with psycopg2.connect(host='127.0.0.1', port=port, dbname=database, user='postgres',
                          password=admin_password, connect_timeout=5) as target, target.cursor() as cursor:
        # No registrar SQL que contiene la contraseña nueva.
        cursor.execute(QUIET)
        cursor.execute("UPDATE public.usuarios SET senha_hash=public.crypt(%s,public.gen_salt('bf',12)) "
                       'WHERE login=%s AND ativo', (new_password, login))
        if cursor.rowcount != 1:
            raise ValueError('No se encontró la cuenta de ese rol. No se cambió nada.')


def main():
    parser = argparse.ArgumentParser(description='Cambiar la contraseña de un rol de la tienda.')
    parser.add_argument('--port', type=int, default=5432)
    parser.add_argument('--database', default='urdimbre')
    args = parser.parse_args()
    try:
        identifier(args.database)
        for number, (_login, perfil) in enumerate(permisos.CUENTAS, 1):
            print(f'  {number}. {permisos.NOMBRES[perfil]}')
        choice = input('Número del rol: ').strip()
        if choice not in {str(n) for n in range(1, len(permisos.CUENTAS)+1)}:
            raise ValueError('Rol no reconocido. No se cambió nada.')
        login, perfil = permisos.CUENTAS[int(choice)-1]
        admin_password = read_secret('Contraseña de postgres definida al instalar PostgreSQL: ')
        new_password = password(f'Nueva contraseña del rol {permisos.NOMBRES[perfil]}: ', bcrypt=True)
        change(admin_password, args.port, args.database, login, new_password)
    except UnicodeDecodeError:
        parser.exit(1, 'Contraseña de postgres incorrecta o fallo de conexión.\n')
    except ValueError as error:
        parser.exit(1, str(error)+'\n')
    except (OSError, psycopg2.Error) as error:
        detail = str(error).splitlines()[0] if str(error) else 'error'
        parser.exit(1, f'No se pudo cambiar la contraseña: {detail}\n')
    print(f'Contraseña del rol {permisos.NOMBRES[perfil]} cambiada. Las sesiones abiertas siguen activas hasta salir.')


if __name__ == '__main__':
    main()
