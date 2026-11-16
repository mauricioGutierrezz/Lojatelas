"""Contratos Windows y PostgreSQL TCP en cluster exclusivo del runner."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from psycopg2 import sql

from app_loja.bootstrap_windows import create_database, destination, install


class WindowsValidationTests(unittest.TestCase):
    def test_database_creation_does_not_retry_unrelated_postgresql_errors(self):
        from unittest.mock import MagicMock
        conn=MagicMock()
        conn.cursor.return_value.__enter__.return_value.execute.side_effect=psycopg2.OperationalError('permission denied')
        with self.assertRaisesRegex(psycopg2.OperationalError,'permission denied'):
            create_database(conn,'fixture_database')
        self.assertEqual(conn.cursor.return_value.__enter__.return_value.execute.call_count,1)

    def test_second_start_opens_running_store_without_prompting_for_database_password(self):
        from unittest.mock import MagicMock
        from app_loja.start_windows import main
        with (patch('sys.argv',['start_windows']),
              patch('app_loja.start_windows.urlopen') as request,
              patch('app_loja.start_windows.webbrowser.open') as browser,
              patch('app_loja.start_windows.read_secret') as password):
            response=MagicMock(status=200)
            response.read.return_value=b'<title>Urdimbre</title>'
            request.return_value.__enter__.return_value=response
            main()
        password.assert_not_called()
        browser.assert_called_once_with('http://127.0.0.1:5000')

    def test_first_start_binds_before_opening_browser(self):
        from unittest.mock import MagicMock
        from app_loja.start_windows import main
        server=MagicMock()
        with (patch.dict(os.environ), patch.dict('app_loja.config.DB_CONFIG'), patch('sys.argv',['start_windows']),
              patch('app_loja.start_windows.windows_secret.available',return_value=False),
              patch('app_loja.start_windows.red.network_mode',return_value=False),
              patch('app_loja.start_windows.urlopen',side_effect=OSError('not listening')),
              patch('app_loja.start_windows.read_secret',return_value='fixture-db-secret'),
              patch('app_loja.db.fetchone',return_value={'database':'urdimbre'}),
              patch('app_loja.run.create_app',return_value=object()),
              patch('werkzeug.serving.make_server',return_value=server) as make_server,
              patch('app_loja.start_windows.webbrowser.open') as browser):
            main()
        make_server.assert_called_once()
        browser.assert_called_once_with('http://127.0.0.1:5000')
        server.serve_forever.assert_called_once()

    def test_running_store_reopens_browser_without_starting_another_instance(self):
        from app_loja.start_windows import open_existing_store
        with patch('app_loja.start_windows.urlopen') as request, \
             patch('app_loja.start_windows.webbrowser.open') as browser:
            response=request.return_value.__enter__.return_value
            response.status=200
            response.read.return_value=b'<title>Urdimbre</title>'
            self.assertTrue(open_existing_store(5000))
            browser.assert_called_once_with('http://127.0.0.1:5000')
            browser.reset_mock()
            response.read.return_value=b'<title>Unrelated service</title>'
            self.assertFalse(open_existing_store(5000))
            browser.assert_not_called()

    def test_startup_diagnostic_explains_connection_error_without_printing_password(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from app_loja.start_windows import main
        secret='fixture-db-password'
        error=StringIO()
        with (patch.dict(os.environ), patch.dict('app_loja.config.DB_CONFIG'), patch('sys.argv',['start_windows']),
              patch('app_loja.start_windows.windows_secret.available',return_value=False),
              patch('app_loja.start_windows.red.network_mode',return_value=False),
              patch('app_loja.start_windows.urlopen',side_effect=OSError('not listening')),
              patch('app_loja.start_windows.read_secret',return_value=secret),
              patch('app_loja.db.fetchone',side_effect=psycopg2.OperationalError(f'password {secret} rejected')),
              redirect_stderr(error), self.assertRaises(SystemExit) as failed):
            main()
        self.assertEqual(failed.exception.code,1)
        self.assertIn('[oculta] rejected',error.getvalue())
        self.assertNotIn(secret,error.getvalue())

    def test_destination_refuses_remote_port_and_non_superuser(self):
        for state in [('postgres','5432','10.0.0.1','on'), ('postgres','5433','127.0.0.1','on'),
                      ('postgres','5432','127.0.0.1','off'), ('existing','5432','127.0.0.1','on')]:
            from unittest.mock import MagicMock
            conn = MagicMock()
            conn.cursor.return_value.__enter__.return_value.fetchone.return_value = state
            with self.assertRaises(ValueError): destination(conn,5432)

@unittest.skipUnless(os.name=='nt','Requiere cmd.exe de Windows')
class WindowsBatchFlowTests(unittest.TestCase):
    def run_copy(self, source, result):
        with tempfile.TemporaryDirectory(prefix='loja-bat-flow-') as directory:
            root=Path(directory)
            (root/'mock-python.cmd').write_text('@echo off\r\nexit /b %MOCK_EXIT%\r\n',encoding='ascii')
            original=(Path(__file__).resolve().parents[1]/source).read_text(encoding='utf-8')
            copied_text=original.replace(r'.\.venv-windows\Scripts\python.exe', 'call "%~dp0mock-python.cmd"')
            copied=root/source
            copied.parent.mkdir(parents=True,exist_ok=True)
            copied.write_text(copied_text,encoding='utf-8',newline='\r\n')
            environment={**os.environ,'MOCK_EXIT':str(result)}
            return subprocess.run([os.environ.get('COMSPEC','cmd.exe'),'/d','/c',str(copied)],
                                  input='\r\n',capture_output=True,text=True,timeout=10,env=environment)

    def test_success_and_error_paths_do_not_run_application_python(self):
        cases=[('preparar_base_de_datos.bat','Base de datos creada','No se pudo completar el bootstrap'),
               ('cambiar_contrasena.bat','Contrasena cambiada','La contrasena no se cambio'),
               ('iniciar.bat','Iniciando Urdimbre','Ocurrio un error'),
               ('respaldar.bat','Respaldo terminado','No se pudo crear el respaldo'),
               ('restaurar_respaldo.bat','Restauracion terminada','La restauracion no se completo'),
               ('ejecutar_pruebas.bat','PostgreSQL descartable','Hubo pruebas con fallas')]
        for script,success_marker,error_marker in cases:
            with self.subTest(script=script,exit_code=0):
                success=self.run_copy(script,0)
                self.assertEqual(success.returncode,0,success.stderr)
                self.assertIn(success_marker,success.stdout)
                self.assertNotIn(error_marker,success.stdout)
            with self.subTest(script=script,exit_code=1):
                failure=self.run_copy(script,1)
                self.assertEqual(failure.returncode,1,failure.stdout)
                self.assertIn(error_marker,failure.stdout)


@unittest.skipUnless(os.getenv('LOJA_TEST_DB')=='1' and os.getenv('LOJA_BOOTSTRAP_TCP')=='1',
                     'Requiere TCP del cluster nuevo del runner bootstrap')
class WindowsPostgresTests(unittest.TestCase):
    def setUp(self):
        self.host,self.port,self.admin=(os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        self.technical='win_admin_'+uuid4().hex[:12]
        self.secret='TESTE-'+uuid4().hex
        with psycopg2.connect(host=self.host,port=self.port,dbname='postgres',user=self.admin) as conn,conn.cursor() as cursor:
            cursor.execute("SET log_statement='none'; SET log_min_error_statement='panic'; SET log_min_duration_statement=-1")
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN SUPERUSER PASSWORD %s').format(sql.Identifier(self.technical)),(self.secret,))

    def arguments(self):
        return dict(port=int(self.port),database='windows_descartavel_'+uuid4().hex[:12],
                    user='windows_app_'+uuid4().hex[:12],admin_password=self.secret,
                    db_password='TESTE-'+uuid4().hex,
                    passwords={'admin':'teste','empleado':'TESTE-'+uuid4().hex,'cajero':'TESTE-'+uuid4().hex})

    def connect(self):
        return psycopg2.connect(host='127.0.0.1',port=self.port,dbname='postgres',user=self.technical,password=self.secret)

    def test_clean_install_repeat_refused_login_stock_pin_and_start(self):
        args=self.arguments()
        conn=self.connect()
        try:
            install(conn,**args)
            with self.assertRaisesRegex(ValueError,'ya existe'): install(conn,**args)
        finally: conn.close()
        with psycopg2.connect(host='127.0.0.1',port=self.port,dbname=args['database'],user=self.technical,password=self.secret) as conn,conn.cursor() as cursor:
            cursor.execute('SELECT login,perfil,nome FROM usuarios ORDER BY id');self.assertEqual(cursor.fetchall(),[('administrador','admin','Administrador'),('empleado','empleado','Empleado'),('cajero','cajero','Cajero')])
            cursor.execute('SELECT nome FROM tipos_tela ORDER BY id');self.assertEqual([r[0] for r in cursor.fetchall()],['Accesorios','Telas por peso','Telas de punto','Telas sintéticas'])
            cursor.execute('SELECT parent.rolname FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=%s',(args['user'],))
            self.assertEqual(cursor.fetchall(),[('loja_operador',)])
            cursor.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=%s',(args['user'],))
            self.assertEqual(cursor.fetchone(),(False,False,False))
        code='''import os
from unittest.mock import patch
from app_loja.start_windows import main
with patch('app_loja.start_windows.read_secret',return_value=os.environ['TEST_DB_SECRET']),patch('werkzeug.serving.make_server') as server,patch('app_loja.start_windows.webbrowser.open') as browser:
    main()
    server.assert_called_once()
    server.return_value.serve_forever.assert_called_once()
    browser.assert_called_once_with('http://127.0.0.1:55433')
from app_loja.config import DB_CONFIG
assert DB_CONFIG['dbname']==os.environ['TEST_DATABASE']
assert DB_CONFIG['user']==os.environ['TEST_USER']
assert DB_CONFIG['host']=='127.0.0.1'
from app_loja.run import create_app
app=create_app({'TESTING':True,'SECRET_KEY':'teste-windows'})
client=app.test_client()
client.get('/login')
with client.session_transaction() as s: csrf=s['csrf']
assert client.post('/login',data={'csrf':csrf,'login':'administrador','senha':'teste'}).status_code==302
assert client.get('/stock').status_code==200
assert client.get('/caixa/cierre').status_code==200
assert client.get('/precios').status_code==200
'''
        environment={**os.environ,'TEST_DB_SECRET':args['db_password'],'TEST_DATABASE':args['database'],'TEST_USER':args['user']}
        result=subprocess.run([sys.executable,'-c',code,'--database',args['database'],'--db-user',args['user'],'--db-port',self.port,'--port','55433'],env=environment,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn(args['db_password'],result.stdout)
        self.assertIn('Base: '+args['database'],result.stdout)

    def test_initialization_failure_preserves_new_database_and_no_login(self):
        args=self.arguments()
        conn=self.connect()
        try:
            with patch('app_loja.bootstrap_windows.initialize',side_effect=ValueError('TESTE falha')):
                with self.assertRaisesRegex(ValueError,'preservó'): install(conn,**args)
            with conn.cursor() as cursor:
                cursor.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(args['database'],));self.assertEqual(cursor.fetchone()[0],1)
                cursor.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s',(args['user'],));self.assertEqual(cursor.fetchone()[0],0)
        finally:conn.close()

    def test_secret_failure_rolls_back_categories_user_role_and_is_not_logged(self):
        args=self.arguments()
        args['passwords']={perfil:'TESTE-'+uuid4().hex for perfil in ('admin','empleado','cajero')}
        # El duplicado falla al crear la role, después de categorías/usuario.
        from app_loja.bootstrap_windows import initialize as real_initialize
        def conflicting_role(conn,**kwargs):
            real_initialize(conn,**kwargs)
            with conn.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(args['user'])))
            conn.commit()
        conn=self.connect()
        try:
            with patch('app_loja.bootstrap_windows.initialize',side_effect=conflicting_role):
                with self.assertRaisesRegex(ValueError,'preservó'):install(conn,**args)
        finally:conn.close()
        with psycopg2.connect(host='127.0.0.1',port=self.port,dbname=args['database'],user=self.technical,password=self.secret) as target,target.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM usuarios');self.assertEqual(cursor.fetchone()[0],0)
            cursor.execute('SELECT count(*) FROM tipos_tela');self.assertEqual(cursor.fetchone()[0],0)
        if os.getenv('LOJA_BOOTSTRAP_LOG'):
            log=Path(os.environ['LOJA_BOOTSTRAP_LOG']).read_text(encoding='utf-8')
            self.assertNotIn(args['db_password'],log)
            for secret in args['passwords'].values():self.assertNotIn(secret,log)


if __name__=='__main__':
    unittest.main()
