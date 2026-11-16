"""Límite de intentos, contraseña protegida por Windows, respaldo y restauración."""
from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import psycopg2
from psycopg2 import sql

from app_loja import backup_windows, windows_secret
from app_loja.throttle import AttemptLimiter, wait_message

USER = {'id': 1, 'nome': 'Fixture', 'login': 'fixture', 'perfil': 'admin'}


class AttemptLimiterTests(unittest.TestCase):
    def test_free_attempts_then_growing_wait_capped_and_reset_on_success(self):
        now = [1000.0]
        limiter = AttemptLimiter(free=3, base=30, maximum=100, clock=lambda: now[0])
        self.assertEqual([limiter.failure('pin') for _ in range(2)], [0, 0])
        self.assertEqual(limiter.wait_seconds('pin'), 0)
        self.assertEqual(limiter.failure('pin'), 30)
        self.assertEqual(limiter.wait_seconds('pin'), 31)
        self.assertEqual(limiter.wait_seconds('login'), 0)
        now[0] += 30
        self.assertEqual(limiter.wait_seconds('pin'), 0)
        self.assertEqual(limiter.failure('pin'), 60)
        self.assertEqual(limiter.failure('pin'), 100)
        limiter.success('pin')
        self.assertEqual(limiter.wait_seconds('pin'), 0)
        self.assertEqual(limiter.failure('pin'), 0)

    def test_messages_use_minutes_and_seconds(self):
        self.assertIn('45 segundos', wait_message(45))
        self.assertIn('1 minuto ', wait_message(60))
        self.assertIn('3 minutos', wait_message(121))


class LockoutRouteTests(unittest.TestCase):
    def client(self, logged=True):
        from app_loja.run import create_app
        app = create_app({'TESTING': True, 'SECRET_KEY': 'fixture-only'})
        client = app.test_client()
        client.get('/login')
        with client.session_transaction() as session:
            if logged:
                session['usuario_id'] = 1
            csrf = session['csrf']
        return app, client, csrf

    def test_login_is_not_checked_while_locked(self):
        with patch('app_loja.db.fetchone', return_value=None), \
             patch('app_loja.routes.auth_routes.verificar_login', return_value=None) as verify:
            app, client, csrf = self.client(logged=False)
            for _ in range(5):
                self.assertEqual(client.post('/login', data={'csrf': csrf, 'login': 'a', 'senha': 'b'}).status_code, 200)
            blocked = client.post('/login', data={'csrf': csrf, 'login': 'a', 'senha': 'b'})
            self.assertEqual(blocked.status_code, 429)
            self.assertIn('Demasiados intentos', blocked.get_data(as_text=True))
            self.assertEqual(verify.call_count, 5)
            # El límite es por cuenta: errar en un rol no bloquea a los otros.
            self.assertEqual(client.post('/login', data={'csrf': csrf, 'login': 'cajero', 'senha': 'b'}).status_code, 200)
            self.assertEqual(verify.call_count, 6)

    def test_unicode_digit_product_id_is_a_bad_request_not_a_server_error(self):
        with patch('app_loja.db.fetchone', return_value=USER):
            app, client, csrf = self.client()
            response = client.post('/entrada/revisar', data={'csrf': csrf, 'produto_id': '²', 'quantidade': '1'})
        self.assertEqual(response.status_code, 400)


class StartSecretTests(unittest.TestCase):
    def start(self, argv, *, saved, typed='typed-secret', fetch=None, configured=False):
        from app_loja.start_windows import main
        store = MagicMock()
        store.available.return_value = True
        store.load.return_value = saved
        store.connection_name.side_effect = windows_secret.connection_name
        with (patch.dict(os.environ), patch.dict('app_loja.config.DB_CONFIG'),
              patch('sys.argv', ['start_windows', *argv]),
              patch('app_loja.start_windows.windows_secret', store),
              patch('app_loja.start_windows.red.network_mode', return_value=False),
              patch('app_loja.start_windows.urlopen', side_effect=OSError('not listening')),
              patch('app_loja.start_windows.read_secret', return_value=typed) as prompt,
              patch('app_loja.db.fetchone', **(fetch or {'return_value': {'database': 'urdimbre'}})) as query,
              patch('app_loja.backup_windows.daily', return_value='respaldo ficticio') as daily,
              patch('app_loja.backup_windows.configured', return_value=configured),
              patch('app_loja.backup_windows.hourly') as self.hourly,
              patch('app_loja.backup_windows.background') as self.background,
              patch('app_loja.run.create_app', return_value=object()) as self.created,
              patch('werkzeug.serving.make_server', return_value=MagicMock()),
              patch('app_loja.start_windows.webbrowser.open'),
              patch('builtins.print') as output):
            main()
            from app_loja.config import DB_CONFIG
            used = DB_CONFIG['password']
            hook = (self.created.call_args.args[0] or {}).get('AL_CERRAR') if self.created.call_args else None
            if hook:
                hook()
        printed = ' '.join(str(call) for call in output.call_args_list)
        return store, prompt, used, printed, daily, query

    def test_saved_secret_starts_without_prompt_and_runs_daily_backup(self):
        store, prompt, used, printed, daily, _ = self.start([], saved='saved-secret')
        prompt.assert_not_called()
        store.save.assert_not_called()
        self.assertEqual(used, 'saved-secret')
        daily.assert_called_once_with('urdimbre', 5432)
        self.assertNotIn('saved-secret', printed)

    def test_configured_backup_runs_hourly_and_after_each_cierre_only_when_configured(self):
        self.start([], saved='saved-secret')
        self.hourly.assert_not_called()
        self.background.assert_not_called()
        self.assertIsNone(self.created.call_args.args[0])
        self.start([], saved='saved-secret', configured=True)
        self.hourly.assert_called_once_with('urdimbre', 5432)
        self.background.assert_called_once_with('urdimbre', 5432)

    def test_first_start_asks_once_and_saves_only_after_a_working_connection(self):
        store, prompt, used, printed, _, _ = self.start([], saved=None)
        prompt.assert_called_once()
        store.save.assert_called_once_with('db-loja_app-urdimbre-5432', 'typed-secret')
        self.assertNotIn('typed-secret', printed)

    def test_stale_saved_secret_asks_again_and_replaces_it(self):
        fetch = {'side_effect': [psycopg2.OperationalError('rejected saved-secret'), {'database': 'urdimbre'}]}
        store, prompt, used, printed, _, _ = self.start([], saved='saved-secret', fetch=fetch)
        prompt.assert_called_once()
        self.assertEqual(used, 'typed-secret')
        store.save.assert_called_once_with('db-loja_app-urdimbre-5432', 'typed-secret')
        self.assertNotIn('saved-secret', printed)

    def test_no_recordar_keeps_the_interactive_contract(self):
        store, prompt, _, _, _, _ = self.start(['--no-recordar'], saved='saved-secret')
        prompt.assert_called_once()
        store.load.assert_not_called()
        store.save.assert_not_called()

    def test_olvidar_deletes_the_saved_secret_without_connecting(self):
        store, prompt, _, _, _, query = self.start(['--olvidar'], saved='saved-secret')
        store.forget.assert_called_once_with('db-loja_app-urdimbre-5432')
        prompt.assert_not_called()
        query.assert_not_called()


@unittest.skipUnless(os.name == 'nt', 'DPAPI solo existe en Windows')
class WindowsSecretTests(unittest.TestCase):
    def test_roundtrip_is_encrypted_bound_to_name_and_outside_the_project(self):
        secret = 'TESTE-'+uuid4().hex
        with tempfile.TemporaryDirectory(prefix='loja-secret-test-') as directory, \
             patch.dict(os.environ, {'LOJA_SECRET_DIR': directory}):
            self.assertIsNone(windows_secret.load('db-fixture'))
            windows_secret.save('db-fixture', secret)
            stored = (Path(directory)/'db-fixture.dpapi').read_bytes()
            self.assertNotIn(secret.encode(), stored)
            self.assertEqual(windows_secret.load('db-fixture'), secret)
            # Copiado con otro nombre no se descifra: el nombre forma parte de la protección.
            (Path(directory)/'db-other.dpapi').write_bytes(stored)
            self.assertIsNone(windows_secret.load('db-other'))
            (Path(directory)/'db-broken.dpapi').write_bytes(b'not protected')
            self.assertIsNone(windows_secret.load('db-broken'))
            windows_secret.forget('db-fixture')
            self.assertIsNone(windows_secret.load('db-fixture'))
            with self.assertRaises(ValueError):
                windows_secret.save('../escape', secret)
        with patch.dict(os.environ, {'LOJA_SECRET_DIR': str(windows_secret.REPOSITORY/'app_loja')}):
            with self.assertRaises(ValueError):
                windows_secret.save('db-fixture', secret)
        self.assertFalse((windows_secret.REPOSITORY/'app_loja'/'db-fixture.dpapi').exists())


class BackupFileTests(unittest.TestCase):
    def fake_run(self, command, password, timeout):
        if '-f' in command:
            Path(command[command.index('-f')+1]).write_bytes(b'fixture dump')
        return 'toc'

    def test_daily_runs_once_keeps_newest_and_ignores_other_files(self):
        with tempfile.TemporaryDirectory(prefix='loja-backup-test-') as directory, \
             patch('app_loja.backup_windows.windows_secret.load', return_value='fixture'), \
             patch('app_loja.backup_windows.pg_tool', side_effect=lambda name: name), \
             patch('app_loja.backup_windows._run', side_effect=self.fake_run) as run:
            folder = Path(directory)
            (folder/'notas.txt').write_text('no es respaldo')
            (folder/'otra_base-20260101-000000.dump').write_bytes(b'x')
            # Tres del 1 de enero, dos del 2, y luego uno por hora el día 10.
            moments = [datetime(2026, 1, 1, 9), datetime(2026, 1, 1, 13), datetime(2026, 1, 1, 18),
                       datetime(2026, 1, 2, 9), datetime(2026, 1, 2, 17),
                       datetime(2026, 1, 10, 9), datetime(2026, 1, 10, 10), datetime(2026, 1, 10, 11)]
            for moment in moments:
                backup_windows.run_backup('fixture_db', 5432, folder, now=moment)
            # Últimas 48 h completas; de los días anteriores, solo el último de cada día.
            self.assertEqual([p.name for p in backup_windows.existing(folder, 'fixture_db')],
                             ['fixture_db-20260101-180000.dump', 'fixture_db-20260102-170000.dump',
                              'fixture_db-20260110-090000.dump', 'fixture_db-20260110-100000.dump',
                              'fixture_db-20260110-110000.dump'])
            self.assertTrue((folder/'notas.txt').exists() and (folder/'otra_base-20260101-000000.dump').exists())
            calls = run.call_count
            # Con uno reciente no se repite; pasado el intervalo, sí.
            self.assertIsNone(backup_windows.run_backup('fixture_db', 5432, folder, min_minutes=60,
                                                        now=datetime(2026, 1, 10, 11, 59)))
            self.assertEqual(run.call_count, calls)
            self.assertIsNotNone(backup_windows.run_backup('fixture_db', 5432, folder, min_minutes=60,
                                                           now=datetime(2026, 1, 10, 12, 0)))
            # Pasados 30 días no queda nada de enero salvo lo reciente.
            backup_windows.run_backup('fixture_db', 5432, folder, now=datetime(2026, 2, 20, 9))
            self.assertEqual([p.name for p in backup_windows.existing(folder, 'fixture_db')],
                             ['fixture_db-20260220-090000.dump'])
            self.assertFalse(list(folder.glob('*.partial')))

    def test_quiet_backup_never_raises_and_does_not_overlap(self):
        with patch('app_loja.backup_windows.run_backup', side_effect=ValueError('sin conexión')) as run:
            self.assertIsNone(backup_windows.quiet_backup('fixture_db', 5432))
            self.assertTrue(backup_windows._running.acquire(blocking=False))
            try:
                self.assertIsNone(backup_windows.quiet_backup('fixture_db', 5432))
            finally:
                backup_windows._running.release()
            self.assertEqual(run.call_count, 1)
        with patch('app_loja.backup_windows.run_backup', return_value=Path('x.dump')) as run:
            backup_windows.background('fixture_db', 5432).join(timeout=5)
            run.assert_called_once()

    def test_failed_dump_leaves_no_file_and_daily_never_raises(self):
        with tempfile.TemporaryDirectory(prefix='loja-backup-test-') as directory, \
             patch.dict(os.environ, {'LOJA_BACKUP_DIR': directory}), \
             patch('app_loja.backup_windows.pg_tool', side_effect=lambda name: name):
            with patch('app_loja.backup_windows.windows_secret.load', return_value=None):
                self.assertIn('respaldar.bat', backup_windows.daily('fixture_db', 5432))
            with patch('app_loja.backup_windows.windows_secret.load', return_value='fixture'), \
                 patch('app_loja.backup_windows._run', side_effect=ValueError('sin conexión')):
                message = backup_windows.daily('fixture_db', 5432)
            self.assertIn('AVISO', message)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_secret_is_passed_by_environment_and_hidden_in_errors(self):
        with patch.dict(os.environ, {'DB_PASSWORD': 'other-secret'}), \
             patch('app_loja.backup_windows.subprocess.run') as run:
            run.return_value = MagicMock(returncode=1, stderr='fallo con fixture-secret\notra línea')
            with self.assertRaisesRegex(ValueError, r'fallo con \[oculta\]'):
                backup_windows._run(['pg_dump', '-f', 'x'], 'fixture-secret', 5)
            self.assertNotIn('fixture-secret', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['env']['PGPASSWORD'], 'fixture-secret')
            self.assertNotIn('DB_PASSWORD', run.call_args.kwargs['env'])


@unittest.skipUnless(os.name == 'nt' and os.getenv('LOJA_TEST_DB') == '1' and os.getenv('LOJA_BOOTSTRAP_TCP') == '1',
                     'Requiere el cluster TCP + SCRAM del runner Windows')
class BackupPostgresTests(unittest.TestCase):
    """Cluster descartable: allí se puede crear la role postgres que usa la instalación real."""
    @classmethod
    def setUpClass(cls):
        cls.port = int(os.environ['PGPORT'])
        cls.admin_password = 'TESTE-'+uuid4().hex
        with psycopg2.connect(host=os.environ['PGHOST'], port=cls.port, dbname='postgres',
                              user=os.environ['PGUSER']) as conn, conn.cursor() as cursor:
            cursor.execute("SET log_statement='none'; SET log_min_error_statement='panic'; SET log_min_duration_statement=-1")
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='postgres'")
            cursor.execute(sql.SQL('{} ROLE postgres LOGIN SUPERUSER PASSWORD %s').format(
                sql.SQL('ALTER' if cursor.fetchone() else 'CREATE')), (cls.admin_password,))

    def test_configure_backup_restore_into_new_database_and_never_replace(self):
        from app_loja.bootstrap_windows import install
        database = 'respaldo_descartavel_'+uuid4().hex[:12]
        user = 'respaldo_app_'+uuid4().hex[:12]
        db_password = 'TESTE-'+uuid4().hex
        conn = backup_windows.admin_connection(self.port, self.admin_password)
        try:
            install(conn, port=self.port, database=database, user=user, admin_password=self.admin_password,
                    db_password=db_password, categories=['TESTE Uno', 'TESTE Dos'],
                    passwords={'admin': 'teste', 'empleado': 'teste-e', 'cajero': 'teste-c'})
        finally:
            conn.close()
        with tempfile.TemporaryDirectory(prefix='loja-backup-pg-') as directory, \
             patch.dict(os.environ, {'LOJA_SECRET_DIR': str(Path(directory)/'secrets')}):
            folder = Path(directory)/'respaldos'
            with self.assertRaises(backup_windows.NotConfigured):
                backup_windows.run_backup(database, self.port, folder)
            conn = backup_windows.admin_connection(self.port, self.admin_password)
            try:
                backup_windows.configure(conn, database, self.port)
                first = windows_secret.load(backup_windows.secret_name(database, self.port))
                # Repetir renueva la contraseña de la role propia, sin duplicarla.
                backup_windows.configure(conn, database, self.port)
                with conn.cursor() as cursor:
                    cursor.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=%s',
                                   (backup_windows.BACKUP_ROLE,))
                    self.assertEqual(cursor.fetchone(), (False, False, False))
            finally:
                conn.close()
            self.assertNotEqual(first, windows_secret.load(backup_windows.secret_name(database, self.port)))
            created = backup_windows.run_backup(database, self.port, folder)
            self.assertTrue(created.is_file() and created.stat().st_size > 0)
            self.assertIsNone(backup_windows.run_backup(database, self.port, folder, min_minutes=60))
            # La role de respaldo solo lee: no puede modificar la base.
            secret = windows_secret.load(backup_windows.secret_name(database, self.port))
            with psycopg2.connect(host='127.0.0.1', port=self.port, dbname=database,
                                  user=backup_windows.BACKUP_ROLE, password=secret) as reader, reader.cursor() as cursor:
                with self.assertRaises(psycopg2.Error):
                    cursor.execute("INSERT INTO public.tipos_tela(nome) VALUES('TESTE intruso')")
            restored = database+'_r'
            backup_windows.restore(created, restored, self.port, self.admin_password, app_roles=(user,))
            with self.assertRaisesRegex(ValueError, 'ya existe'):
                backup_windows.restore(created, restored, self.port, self.admin_password)
            with self.assertRaisesRegex(ValueError, 'ya existe'):
                backup_windows.restore(created, database, self.port, self.admin_password)
            # La aplicación opera sobre la base restaurada con su role restringida.
            with psycopg2.connect(host='127.0.0.1', port=self.port, dbname=restored,
                                  user=user, password=db_password) as app, app.cursor() as cursor:
                cursor.execute('SET ROLE loja_operador')
                cursor.execute('SELECT nome FROM public.tipos_tela ORDER BY nome')
                self.assertEqual([row[0] for row in cursor.fetchall()], ['TESTE Dos', 'TESTE Uno'])
                cursor.execute("SELECT id FROM public.fn_autenticar_usuario('administrador','teste')")
                self.assertEqual(len(cursor.fetchall()), 1)
                cursor.execute("SAVEPOINT s")
                with self.assertRaises(psycopg2.Error):
                    cursor.execute('SELECT senha_hash FROM public.usuarios')
                cursor.execute("ROLLBACK TO s")
        if os.getenv('LOJA_BOOTSTRAP_LOG'):
            log = Path(os.environ['LOJA_BOOTSTRAP_LOG']).read_text(encoding='utf-8')
            self.assertNotIn(secret, log)
            self.assertNotIn(first, log)

    def second_cluster(self, directory, password):
        """Otro PostgreSQL vacío, como un equipo nuevo: solo existe el usuario postgres."""
        import socket
        import subprocess
        bindir = Path(backup_windows.pg_tool('pg_dump')).parent
        data = Path(directory)/'otro-equipo'
        secret_file = Path(directory)/'pw.txt'
        secret_file.write_text(password, encoding='ascii')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]

        def tool(name, *args):
            return subprocess.run([str(bindir/f'{name}.exe'), *map(str, args)], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL).returncode

        self.assertEqual(tool('initdb', '-A', 'scram-sha-256', '--no-locale', '--encoding=UTF8', '-U', 'postgres',
                              f'--pwfile={secret_file}', '-D', data), 0)
        secret_file.unlink()
        self.assertEqual(tool('pg_ctl', '-D', data, '-l', Path(directory)/'otro.log', '-o',
                              f'-F -p {port} -c listen_addresses=127.0.0.1', '-w', 'start'), 0)
        self.addCleanup(lambda: tool('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop'))
        return port

    def test_recovery_on_an_empty_postgresql_leaves_the_store_ready_in_one_step(self):
        from app_loja import bootstrap_windows, recuperar_windows
        database = 'recuperar_descartavel_'+uuid4().hex[:10]
        user = 'recuperar_app_'+uuid4().hex[:10]
        passwords = {perfil: 'TESTE-'+uuid4().hex for perfil in ('admin', 'empleado', 'cajero')}
        conn = backup_windows.admin_connection(self.port, self.admin_password)
        try:
            bootstrap_windows.install(conn, port=self.port, database=database, user=user,
                                      admin_password=self.admin_password, db_password='TESTE-'+uuid4().hex,
                                      passwords=passwords)
        finally:
            conn.close()
        with self.connect(database) as origin, origin.cursor() as cursor:
            cursor.execute("INSERT INTO public.tipos_tela(nome) VALUES('TESTE dato a recuperar')")
        origin.close()
        with tempfile.TemporaryDirectory(prefix='loja-recuperar-pg-', ignore_cleanup_errors=True) as directory:
            folder = Path(directory)/'respaldos'
            with patch.dict(os.environ, {'LOJA_SECRET_DIR': str(Path(directory)/'equipo-viejo')}):
                conn = backup_windows.admin_connection(self.port, self.admin_password)
                try:
                    backup_windows.configure(conn, database, self.port)
                finally:
                    conn.close()
                created = backup_windows.run_backup(database, self.port, folder)
            # Equipo nuevo: otro PostgreSQL, otra contraseña de postgres y ningún secreto guardado.
            new_admin = 'TESTE-'+uuid4().hex
            new_port = self.second_cluster(directory, new_admin)
            with patch.dict(os.environ, {'LOJA_SECRET_DIR': str(Path(directory)/'equipo-nuevo')}):
                self.assertEqual(recuperar_windows.newest_backup(folder, database), created)
                with self.assertRaisesRegex(ValueError, 'No hay respaldos'):
                    recuperar_windows.newest_backup(Path(directory)/'vacia', database)
                self.assertTrue(recuperar_windows.recover(created, new_port, new_admin, database, user))
                with self.assertRaisesRegex(ValueError, 'ya existe'):
                    recuperar_windows.recover(created, new_port, new_admin, database, user)
                app_secret = windows_secret.load(windows_secret.connection_name('db', user, database, new_port))
                self.assertTrue(app_secret)
                # La aplicación opera con su role restringida y las mismas contraseñas de rol.
                with psycopg2.connect(host='127.0.0.1', port=new_port, dbname=database, user=user,
                                      password=app_secret) as app, app.cursor() as cursor:
                    cursor.execute('SET ROLE loja_operador')
                    cursor.execute("SELECT count(*) FROM public.tipos_tela WHERE nome='TESTE dato a recuperar'")
                    self.assertEqual(cursor.fetchone()[0], 1)
                    cursor.execute('SELECT login,perfil FROM public.vw_usuarios ORDER BY id')
                    self.assertEqual(cursor.fetchall(), [('administrador', 'admin'), ('empleado', 'empleado'), ('cajero', 'cajero')])
                    cursor.execute('SAVEPOINT s')
                    with self.assertRaises(psycopg2.Error):
                        cursor.execute('SELECT senha_hash FROM public.usuarios')
                    cursor.execute('ROLLBACK TO s')
                app.close()
                with psycopg2.connect(host='127.0.0.1', port=new_port, dbname=database, user='postgres',
                                      password=new_admin) as check, check.cursor() as cursor:
                    cursor.execute(bootstrap_windows.QUIET)
                    cursor.execute('SELECT id FROM public.fn_autenticar_usuario(%s,%s)', ('cajero', passwords['cajero']))
                    self.assertEqual(len(cursor.fetchall()), 1)
                check.close()
                # El respaldo automático ya funciona en el equipo nuevo, sin más pasos.
                again = backup_windows.run_backup(database, new_port, Path(directory)/'respaldos-nuevos')
                self.assertTrue(again.is_file() and again.stat().st_size > 0)

    def connect(self, database, user='postgres', password=None):
        return psycopg2.connect(host='127.0.0.1', port=self.port, dbname=database, user=user,
                                password=password or self.admin_password)

    def test_previous_version_is_archived_and_new_base_keeps_the_connection_role(self):
        from app_loja import bootstrap_windows, cambiar_contrasena
        database = 'roles_descartavel_'+uuid4().hex[:12]
        user = 'roles_app_'+uuid4().hex[:12]
        db_password = 'TESTE-'+uuid4().hex
        passwords = {perfil: 'TESTE-'+uuid4().hex for perfil in ('admin', 'empleado', 'cajero')}
        arguments = dict(port=self.port, database=database, user=user, admin_password=self.admin_password,
                         passwords=passwords)
        conn = backup_windows.admin_connection(self.port, self.admin_password)
        try:
            bootstrap_windows.install(conn, db_password=db_password, **arguments)
            self.assertTrue(bootstrap_windows.has_roles(conn, database, self.admin_password, self.port))
            with self.assertRaisesRegex(ValueError, 'no es una instalación reconocida'):
                bootstrap_windows.has_roles(conn, 'postgres', self.admin_password, self.port)
            # Simular la versión anterior: perfiles sin Cajero y un dato que debe sobrevivir.
            with self.connect(database) as old, old.cursor() as cursor:
                cursor.execute('ALTER TABLE public.usuarios DROP CONSTRAINT usuarios_perfil_check')
                cursor.execute("ALTER TABLE public.usuarios ADD CONSTRAINT usuarios_perfil_check "
                               "CHECK (perfil IN ('operador','admin')) NOT VALID")
                cursor.execute("INSERT INTO public.tipos_tela(nome) VALUES('TESTE dato anterior')")
            old.close()
            self.assertFalse(bootstrap_windows.has_roles(conn, database, self.admin_password, self.port))
            # Sin confirmación explícita de actualización, la instalación sigue rechazando la base y la role.
            with self.assertRaisesRegex(ValueError, 'ya existe'):
                bootstrap_windows.install(conn, db_password=db_password, **arguments)
            busy = self.connect(database)
            try:
                with self.assertRaisesRegex(ValueError, 'está abierta'):
                    bootstrap_windows.archive(conn, database)
            finally:
                busy.close()
            archived = bootstrap_windows.archive(conn, database)
            self.assertTrue(archived.startswith(database+'_anterior_'))
            bootstrap_windows.install(conn, db_password=None, reuse_role=True, **arguments)
            self.assertTrue(bootstrap_windows.has_roles(conn, database, self.admin_password, self.port))
            with self.assertRaisesRegex(ValueError, 'no existe o tiene privilegios'):
                bootstrap_windows.install(conn, db_password=None, reuse_role=True,
                                          **{**arguments, 'database': database+'_x', 'user': 'role_ausente_'+uuid4().hex[:8]})
        finally:
            conn.close()
        with self.connect(archived) as old, old.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.tipos_tela WHERE nome='TESTE dato anterior'")
            self.assertEqual(cursor.fetchone()[0], 1)
        old.close()
        # La misma role y la misma contraseña de conexión operan la base nueva, ya con roles.
        with self.connect(database, user, db_password) as app, app.cursor() as cursor:
            cursor.execute('SET ROLE loja_operador')
            cursor.execute('SELECT login,perfil FROM public.vw_usuarios ORDER BY id')
            self.assertEqual(cursor.fetchall(), [('administrador', 'admin'), ('empleado', 'empleado'), ('cajero', 'cajero')])
            cursor.execute('SELECT nome FROM public.tipos_tela ORDER BY id')
            self.assertEqual([row[0] for row in cursor.fetchall()], list(bootstrap_windows.CATEGORIAS))
        app.close()
        new_password = 'TESTE-'+uuid4().hex
        cambiar_contrasena.change(self.admin_password, self.port, database, 'cajero', new_password)
        with self.assertRaisesRegex(ValueError, 'No se encontró'):
            cambiar_contrasena.change(self.admin_password, self.port, database, 'inexistente', new_password)
        # Sesión técnica sin registro: esta consulta de prueba lleva contraseñas en sus argumentos.
        with self.connect(database) as app, app.cursor() as cursor:
            cursor.execute(bootstrap_windows.QUIET)
            for login, secret, expected in (('cajero', new_password, 1), ('cajero', passwords['cajero'], 0),
                                            ('empleado', passwords['empleado'], 1)):
                cursor.execute('SELECT id FROM public.fn_autenticar_usuario(%s,%s)', (login, secret))
                self.assertEqual(len(cursor.fetchall()), expected)
        app.close()
        if os.getenv('LOJA_BOOTSTRAP_LOG'):
            log = Path(os.environ['LOJA_BOOTSTRAP_LOG']).read_text(encoding='utf-8')
            for secret in (*passwords.values(), new_password, db_password):
                self.assertNotIn(secret, log)


if __name__ == '__main__':
    unittest.main()
