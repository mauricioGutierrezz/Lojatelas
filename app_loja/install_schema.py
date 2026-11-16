"""Inicialização explícita e preservadora de uma base nova; não converte dados."""
import argparse
from pathlib import Path
import psycopg2


def destination_source(*, database, port, socket):
    """Mismo inicializador preservador, transmitido por stdin al psql elevado."""
    def quoted(value):
        # Valores técnicos ASCII/UTF-8 escapados sin conexión ni contraseña.
        return "'" + str(value).replace("'", "''") + "'"
    tag = '$destination$'
    while any(tag in str(value) for value in (database, port, socket)):
        tag = tag[:-1] + '_$'
    return f"""SET standard_conforming_strings=on;
DO {tag}
BEGIN
 IF current_database()<>{quoted(database)} OR current_setting('port')<>{quoted(port)}
 OR NOT {quoted(socket)}=ANY(string_to_array(current_setting('unix_socket_directories'),','))
 OR inet_server_addr() IS NOT NULL THEN
  RAISE EXCEPTION 'Destino diferente del esperado.';
 END IF;
END; {tag};
""" + (Path(__file__).resolve().parents[1]/'schema.sql').read_text(encoding='utf-8') + '\n'


def initialize(conn, *, database, port, socket=None, host=None, source=None):
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_setting('port'),current_setting('unix_socket_directories', true),host(inet_server_addr())")
            actual_database,actual_port,actual_sockets,address=cursor.fetchone()
            local = (host == '127.0.0.1' and socket is None and address == host) if host is not None else (
                socket is not None and actual_sockets is not None and socket in actual_sockets.split(',') and address is None)
            if (actual_database!=database or actual_port!=str(port) or not local
                or database in ('postgres','template0','template1')):
                raise ValueError('Destino diferente del esperado; no se inicializó la base.')
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f'))")
            if cursor.fetchone()[0]:
                raise ValueError('La base ya tiene estructura; no se inicializó ni convirtió ningún registro.')
            print(f'Destino confirmado: {database} · puerto {port} · destino {host or socket}')
            conn.rollback()
            cursor.execute(source if source is not None else (Path(__file__).resolve().parents[1]/'schema.sql').read_text(encoding='utf-8'))
    except Exception:
        conn.rollback()
        raise


def main():
    parser=argparse.ArgumentParser(description='Inicializar solamente una base nueva y vacía.')
    parser.add_argument('--database',required=True)
    parser.add_argument('--port',required=True,type=int)
    parser.add_argument('--socket',required=True)
    parser.add_argument('--user',required=True)
    args=parser.parse_args()
    try:
        with psycopg2.connect(host=args.socket,port=args.port,dbname=args.database,user=args.user) as conn:
            initialize(conn,database=args.database,port=args.port,socket=args.socket)
    except (ValueError,psycopg2.Error):
        parser.exit(1,'Inicialización rechazada. Revisá el destino y la ausencia de estructura existente. No se realizó ninguna conversión.\n')


if __name__=='__main__':
    main()
