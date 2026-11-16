"""Inicio local sin .env ni contraseña en argumentos.

La contraseña de conexión se pide sin eco la primera vez y queda cifrada por
Windows (DPAPI) para la cuenta que inicia la tienda; ``--no-recordar`` conserva
el modo anterior, siempre interactivo.
"""
import argparse
import os
from urllib.request import urlopen
import webbrowser

from . import red, windows_secret
from .bootstrap_local import identifier, read_secret


def open_existing_store(port):
    url = f'http://127.0.0.1:{port}'
    try:
        with urlopen(f'{url}/login', timeout=1) as response:
            if response.status != 200 or b'<title>Urdimbre</title>' not in response.read(2048):
                return False
    except OSError:
        return False
    print('La tienda ya está abierta; abriendo el navegador.')
    webbrowser.open(url)
    return True


def main():
    parser = argparse.ArgumentParser(description='Iniciar la tienda en este equipo.')
    parser.add_argument('--database', default='urdimbre')
    parser.add_argument('--db-user', default='loja_app')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--no-recordar', action='store_true',
                        help='Pedir la contraseña de conexión y no guardarla en este equipo.')
    parser.add_argument('--olvidar', action='store_true',
                        help='Borrar la contraseña de conexión guardada y salir.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--red', action='store_true', help='Servir también a los otros equipos de la red local.')
    mode.add_argument('--local', action='store_true', help='Servir solo a este equipo, aunque esté configurado como servidor.')
    parser.add_argument('--sin-navegador', action='store_true', help='No abrir el navegador al iniciar.')
    args = parser.parse_args()
    try:
        identifier(args.database); identifier(args.db_user)
        if not all(1 <= port <= 65535 for port in (args.db_port, args.port)):
            raise ValueError('Puerto inválido.')
    except ValueError as error:
        parser.exit(1, str(error)+'\n')
    name = windows_secret.connection_name('db', args.db_user, args.database, args.db_port)
    if args.olvidar:
        windows_secret.forget(name)
        print('Contraseña de conexión olvidada. El próximo inicio la pedirá de nuevo.')
        return
    if open_existing_store(args.port):
        return
    remember = windows_secret.available() and not args.no_recordar
    saved = windows_secret.load(name) if remember else None

    def ask():
        try:
            value = read_secret('Contraseña de conexión de la aplicación (no la de postgres): ')
            if not value:
                raise ValueError('La contraseña no puede quedar vacía.')
        except ValueError as error:
            parser.exit(1, str(error)+'\n')
        return value

    secret = saved or ask()
    os.environ.update(DB_HOST='127.0.0.1', DB_PORT=str(args.db_port),
                      DB_NAME=args.database, DB_USER=args.db_user, DB_PASSWORD=secret)
    # Importar después de configurar DB_*; nunca heredar un destino remoto.
    from . import config
    from .db import fetchone
    from .run import create_app
    import psycopg2

    def diagnostic(error, value):
        detail = getattr(getattr(error, 'diag', None), 'message_primary', None) or str(error).splitlines()[0]
        detail = detail.replace(value, '[oculta]') if value else detail
        return f'No se pudo conectar a {args.database} en 127.0.0.1:{args.db_port} como {args.db_user}: {detail}\n'

    def use(value):
        os.environ['DB_PASSWORD'] = value
        config.DB_CONFIG.update(host='127.0.0.1', port=args.db_port, dbname=args.database,
                                user=args.db_user, password=value)

    use(secret)
    try:
        state = fetchone('SELECT current_database() AS database')
    except (psycopg2.Error, UnicodeDecodeError) as error:
        if not saved:
            parser.exit(1, diagnostic(error, secret))
        # La contraseña guardada dejó de servir (o el servidor no responde): pedirla una vez.
        print(diagnostic(error, secret).strip())
        print('La contraseña guardada no funcionó. Escribila de nuevo.')
        saved, secret = None, ask()
        use(secret)
        try:
            state = fetchone('SELECT current_database() AS database')
        except (psycopg2.Error, UnicodeDecodeError) as retry_error:
            parser.exit(1, diagnostic(retry_error, secret))
    if remember and not saved:
        try:
            windows_secret.save(name, secret)
            print('Contraseña de conexión guardada y protegida por Windows para esta cuenta. No se volverá a pedir.')
        except (OSError, ValueError):
            print('AVISO: no se pudo guardar la contraseña protegida; se pedirá en el próximo inicio.')
    print(f"Base: {state['database']} · PostgreSQL 127.0.0.1:{args.db_port}")
    if windows_secret.available():
        from . import backup_windows
        print(backup_windows.daily(args.database, args.db_port))
    network = args.red or (not args.local and red.network_mode())
    try:
        if network:
            # Servidor de producción para varios equipos; PostgreSQL sigue aceptando solo a este equipo.
            try:
                from waitress import create_server
            except ImportError:
                parser.exit(1, 'Falta el componente de red. Ejecutá instalar.bat una vez y volvé a abrir.\n')
            application = create_app({'REGISTRAR_ACCESOS': True})
            try:
                # IPv4 e IPv6: el nombre del equipo suele resolver primero a IPv6 en la red local.
                server = create_server(application, listen=f'0.0.0.0:{args.port} [::]:{args.port}',
                                       threads=8, ident=None)
            except OSError:
                server = create_server(application, listen=f'0.0.0.0:{args.port}', threads=8, ident=None)
            serve = server.run
            if red.keep_awake():
                print('Mientras la tienda esté abierta, este equipo no se suspende por inactividad.')
        else:
            from werkzeug.serving import make_server
            server = make_server('127.0.0.1', args.port, create_app(), threaded=True)
            serve = server.serve_forever
    except OSError as error:
        if open_existing_store(args.port):
            return
        parser.exit(1, f'No se pudo abrir la tienda en el puerto {args.port}: {error.strerror or "el puerto está ocupado"}.\n')
    url = f'http://127.0.0.1:{args.port}'
    print(f'Running on {url} · CTRL+C para cerrar.')
    if network:
        print('Modo servidor: los otros equipos de la tienda abren en su navegador:')
        for address in red.urls(args.port):
            print(f'  {address}')
        print('Si no conectan, ejecutá permitir_red.bat una vez en este equipo.')
        print(f'Registro de conexiones: {red.access_log_path()}')
    print('La tienda está abierta. Dejá esta ventana abierta (podés minimizarla); cerrarla apaga la tienda.')
    if not args.sin_navegador:
        webbrowser.open(url)
    try:
        serve()
    except KeyboardInterrupt:
        print('Servidor local encerrado.')


if __name__ == '__main__':
    main()
