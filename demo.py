"""Demostración con datos ficticios en un PostgreSQL temporal.

Crea un cluster PostgreSQL NUEVO en una carpeta temporal, carga el esquema y
datos de ejemplo, abre la aplicación en http://127.0.0.1:5050 y, al cerrar con
Ctrl+C, detiene y borra todo. No usa ni modifica ninguna base instalada.

Requiere PostgreSQL 16 instalado (solo sus programas). Uso: demo.bat
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import webbrowser
from uuid import uuid4

REPO = Path(__file__).resolve().parent
ADMIN = 'demo_runner'
# Exclusivas de la demostración: el cluster temporal solo escucha en este equipo y se borra al salir.
DEMO_PASSWORD = 'demo'
APP_PORT = 5050


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def seed(connection_settings):
    """Cuentas, categorías, productos, stock y un ticket pendiente, todo por las funciones del núcleo."""
    import psycopg2
    from app_loja import db, permisos
    from app_loja.bootstrap_windows import CATEGORIAS
    conn = psycopg2.connect(**connection_settings)
    try:
        with conn, conn.cursor() as cursor:
            cursor.execute('CREATE ROLE demo_app LOGIN')
            cursor.execute('GRANT loja_operador TO demo_app')
            for category in CATEGORIAS:
                cursor.execute('INSERT INTO public.tipos_tela(nome) VALUES(%s)', (category,))
            users = {}
            for login, perfil in permisos.CUENTAS:
                cursor.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES"
                               "(%s,%s,public.crypt(%s,public.gen_salt('bf')),%s) RETURNING id",
                               (permisos.NOMBRES[perfil], login, DEMO_PASSWORD, perfil))
                users[perfil] = cursor.fetchone()[0]
            cursor.execute('SELECT nome,id FROM public.tipos_tela')
            categories = dict(cursor.fetchall())
    finally:
        conn.close()
    db.DB_CONFIG.clear()
    db.DB_CONFIG.update({**connection_settings, 'user': 'demo_app'})
    admin, empleado = users['admin'], users['empleado']

    def product(category, name, unit, price, width=None, standard=None):
        return db.cadastrar_produto({'tipo_id': categories[category], 'nome': name, 'unidade': unit,
                                     'preco': price, 'largura': width, 'padrao': standard}, empleado)

    lino = product('Telas sintéticas', 'Lino arena', 'm', '8500.00', '1.50', '30')
    jersey = product('Telas de punto', 'Jersey algodón azul', 'm', '6200.00', '1.80', '25')
    retazo = product('Telas por peso', 'Friselina por kilo', 'kg', '12000.00')
    cierre = product('Accesorios', 'Cierre metálico 20 cm', 'un', '950.00')
    db.confirmar_ingresso(str(uuid4()), [{'produto_id': lino, 'rolos': 4, 'quantidade': '30'},
                                         {'produto_id': lino, 'rolos': 1, 'quantidade': '45'}], empleado)
    db.confirmar_ingresso(str(uuid4()), [{'produto_id': jersey, 'rolos': 2, 'quantidade': '25'}], empleado)
    db.confirmar_ingresso(str(uuid4()), [{'produto_id': retazo, 'pecas': 3, 'quantidade': '12.5'}], empleado)
    db.confirmar_ingresso(str(uuid4()), [{'produto_id': cierre, 'quantidade': '120'}], admin)
    ticket = db.iniciar_ticket(str(uuid4()), empleado)
    lot = db.fetchone('SELECT id FROM public.estoque_lotes WHERE produto_id=%s ORDER BY id LIMIT 1', (lino,))['id']
    # Vendido 2,5 m; cortado 2,6 m: ambas cantidades quedan registradas por separado.
    db.registrar_corte({'ticket_id': ticket, 'produto_id': lino, 'quantidade_vendida': '2.5',
                        'quantidade_cortada': '2.6', 'chave': str(uuid4()),
                        'alocacoes': [{'lote_id': lot, 'quantidade': '2.6'}]}, empleado)
    db.registrar_corte({'ticket_id': ticket, 'produto_id': cierre, 'quantidade_vendida': '3',
                        'quantidade_cortada': '3', 'chave': str(uuid4()), 'alocacoes': []}, empleado)


def main():
    sys.path.insert(0, str(REPO))
    from app_loja.backup_windows import pg_tool
    bindir = Path(pg_tool('pg_dump')).parent
    cluster = Path(tempfile.mkdtemp(prefix='demo-tienda-pg-'))
    data, port = cluster/'data', free_port()
    environment = {**os.environ, 'PGCLIENTENCODING': 'UTF8'}
    for key in ('PGPASSWORD', 'PGSERVICE', 'PGPASSFILE', 'PGHOST', 'PGPORT', 'PGUSER', 'PGDATABASE'):
        environment.pop(key, None)

    def tool(name, *args):
        # Sin tuberías: pg_ctl deja al servidor heredando la salida y bloquearía la espera.
        return subprocess.run([str(bindir/f'{name}.exe'), *map(str, args)], env=environment,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=REPO).returncode

    def must(label, code):
        if code:
            raise SystemExit(f'No se pudo completar: {label}.')

    settings = dict(host='127.0.0.1', port=port, dbname='demo_tienda', user=ADMIN)
    try:
        print('Preparando la demostración (PostgreSQL temporal, datos ficticios)...', flush=True)
        must('initdb', tool('initdb', '-A', 'trust', '--no-locale', '--encoding=UTF8', '-U', ADMIN, '-D', data))
        must('iniciar PostgreSQL temporal', tool(
            'pg_ctl', '-D', data, '-l', cluster/'server.log', '-o', f'-F -p {port} -c listen_addresses=127.0.0.1', '-w', 'start'))
        must('crear base', tool('createdb', '-h', '127.0.0.1', '-p', port, '-U', ADMIN, 'demo_tienda'))
        must('schema.sql', tool('psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-h', '127.0.0.1', '-p', port,
                                '-U', ADMIN, '-d', 'demo_tienda', '-f', REPO/'schema.sql'))
        seed(settings)
        from werkzeug.serving import make_server
        from app_loja.run import create_app
        server = make_server('127.0.0.1', APP_PORT, create_app(), threaded=True)
        url = f'http://127.0.0.1:{APP_PORT}'
        print(f'\nDemostración abierta en {url}')
        print(f'Roles: Administrador, Empleado y Cajero · contraseña de los tres: {DEMO_PASSWORD}')
        print('Ctrl+C cierra la demostración y borra la base temporal.')
        if '--sin-navegador' not in sys.argv:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nCerrando la demostración...')
    finally:
        if (data/'postmaster.pid').exists():
            tool('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')
        shutil.rmtree(cluster, ignore_errors=True)
    print('Base temporal borrada.')


if __name__ == '__main__':
    main()
