"""Configuración técnica inicial; no es una interfaz administrativa."""
import argparse
from getpass import getpass

import psycopg2


def main():
    parser = argparse.ArgumentParser(description='Preparar una base local ya inicializada.')
    parser.add_argument('--categoria', action='append', required=True)
    parser.add_argument('--nombre', required=True)
    parser.add_argument('--login', required=True)
    args = parser.parse_args()
    categories = [name.strip() for name in args.categoria]
    if not all(categories) or not args.nombre.strip() or not args.login.strip():
        parser.error('Los nombres y el usuario no pueden quedar vacíos.')
    password = getpass('Contraseña de la atendente: ')
    if not password or len(password.encode('utf-8')) > 72:
        parser.error('Ingresá una contraseña de hasta 72 bytes, límite técnico de bcrypt.')
    if password != getpass('Repetir contraseña: '):
        parser.error('Las contraseñas no coinciden.')
    # Usa PGHOST/PGPORT/PGDATABASE/PGUSER del instalador, nunca la conexión operativa.
    conn = None
    try:
        conn = psycopg2.connect('')
        conn.set_client_encoding('UTF8')
        with conn, conn.cursor() as cursor:
            for name in categories:
                cursor.execute('INSERT INTO public.tipos_tela (nome) VALUES (%s) '
                               'ON CONFLICT (nome) DO NOTHING', (name,))
            cursor.execute('INSERT INTO public.usuarios (nome,login,senha_hash,perfil) '
                           "VALUES (%s,%s,public.crypt(%s,public.gen_salt('bf',12)),'admin')",
                           (args.nombre.strip(), args.login.strip(), password))
    except psycopg2.Error:
        parser.exit(1, 'No se pudo completar la configuración. Verificá la base, los permisos '
                    'y que el usuario no exista. No se guardaron cambios parciales.\n')
    finally:
        if conn:
            conn.close()
    print('Configuración inicial guardada. Ya podés iniciar la aplicación local.')


if __name__ == '__main__':
    main()
