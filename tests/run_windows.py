"""Runner Windows: toda la suite contra un cluster PostgreSQL NUEVO y descartable.

Equivale a run_phase0_postgres.sh + run_bootstrap_postgres.sh. Nunca se conecta
a la base instalada: crea su propio cluster temporal en otro puerto, lo detiene
y lo borra al terminar. Uso: ejecutar_pruebas.bat
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from app_loja.backup_windows import pg_tool  # noqa: E402

ADMIN = 'loja_runner'


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def main():
    bindir = Path(pg_tool('pg_dump')).parent
    cluster = Path(tempfile.mkdtemp(prefix='loja-test-pg-'))
    data, log, port = cluster/'data', cluster/'server.log', free_port()
    environment = {**os.environ, 'PATH': f'{bindir}{os.pathsep}{os.environ["PATH"]}',
                   'PGHOST': '127.0.0.1', 'PGPORT': str(port), 'PGUSER': ADMIN,
                   'PGDATABASE': 'loja_unidades_descartavel_test', 'PGCLIENTENCODING': 'UTF8',
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
                   # Las pruebas nunca tocan secretos ni respaldos reales de la cuenta.
                   'LOJA_SECRET_DIR': str(cluster/'secrets'), 'LOJA_BACKUP_DIR': str(cluster/'backups')}
    for key in ('PGPASSWORD', 'PGSERVICE', 'PGPASSFILE', 'DB_PASSWORD'):
        environment.pop(key, None)
    failures = []

    def tool(name, *args, quiet=True):
        # Sin tuberías: pg_ctl deja al servidor heredando la salida y bloquearía la espera.
        output = subprocess.DEVNULL if quiet else None
        return subprocess.run([str(bindir/f'{name}.exe'), *map(str, args)], env=environment,
                              stdout=output, stderr=output, cwd=REPO).returncode

    def step(label, code):
        print(f'{"ok   " if code == 0 else "FALLA"} {label}', flush=True)
        if code:
            failures.append(label)
        return code == 0

    def server(action):
        options = f'-F -p {port} -c listen_addresses=127.0.0.1'
        if action == 'start':
            return tool('pg_ctl', '-D', data, '-l', log, '-o', options, '-w', 'start')
        return tool('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')

    def python(*args):
        return subprocess.run([sys.executable, *map(str, args)], env=environment, cwd=REPO).returncode

    def psql_file(path):
        return tool('psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-f', path)

    try:
        print(f'Cluster descartable: {cluster} · 127.0.0.1:{port}', flush=True)
        if not step('initdb', tool('initdb', '-A', 'trust', '--no-locale', '--encoding=UTF8', '-U', ADMIN, '-D', data)):
            return 1
        if not step('iniciar cluster', server('start')):
            return 1
        ready = (step('crear base descartable', tool('createdb', environment['PGDATABASE']))
                 and step('schema.sql', psql_file(REPO/'schema.sql')))
        if ready:
            step('sql/phase0_functional.sql', psql_file(REPO/'tests'/'sql'/'phase0_functional.sql'))
            step('phase0_concurrency.py', python(REPO/'tests'/'phase0_concurrency.py'))
            environment['LOJA_TEST_DB'] = '1'
            step('suite completa (unittest)', python('-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'))
            step('sql/phase0_closing.sql', psql_file(REPO/'tests'/'sql'/'phase0_closing.sql'))

        # Segunda fase: TCP con SCRAM real y registro detallado, como una instalación Windows.
        step('detener cluster', server('stop'))
        hba = data/'pg_hba.conf'
        hba.write_text(f'host all {ADMIN} 127.0.0.1/32 trust\nhost all all 127.0.0.1/32 scram-sha-256\n'
                       + hba.read_text(encoding='utf-8'), encoding='utf-8')
        with (data/'postgresql.conf').open('a', encoding='utf-8') as configuration:
            configuration.write("\nlog_statement='all'\nlog_min_duration_statement=0\n")
        if step('reiniciar cluster con SCRAM', server('start')):
            environment.update(PGDATABASE='postgres', LOJA_TEST_DB='1', LOJA_BOOTSTRAP_TCP='1',
                               LOJA_BOOTSTRAP_LOG=str(log))
            for pattern in ('test_bootstrap_windows.py', 'test_windows_practico.py'):
                step(f'{pattern} (TCP + SCRAM)', python('-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern))
    finally:
        if (data/'postmaster.pid').exists():
            server('stop')
        shutil.rmtree(cluster, ignore_errors=True)
    print()
    if failures:
        print('PRUEBAS CON FALLAS: ' + '; '.join(failures))
        return 1
    print('TODAS LAS PRUEBAS PASARON. El cluster temporal fue detenido y borrado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
