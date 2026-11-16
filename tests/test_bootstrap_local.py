"""Primera instalación en bases creadas solamente dentro del cluster del runner."""
import os
import io
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

import psycopg2
from app_loja.bootstrap_local import install, identifier, local_destination, password, read_secret


class BootstrapValidationTests(unittest.TestCase):
    def test_destination_and_password_validation(self):
        for name in ('postgres', 'template1', '../base', 'host;DROP', ''):
            with self.assertRaises(ValueError): identifier(name)
        self.assertEqual(identifier('loja_local'), 'loja_local')
        for responses in (['', ''], ['a', 'b'], ['x'*73, 'x'*73]):
            with patch('app_loja.bootstrap_local.getpass', side_effect=responses):
                with self.assertRaises(ValueError): password('TESTE', bcrypt=True)
        with self.assertRaises(ValueError): local_destination(None, 'localhost', 5432)
        from app_loja.bootstrap_local import guard_sql
        for socket,port in (('/tmp/socket,localhost',5432),('/tmp/socket',0),('/tmp/socket',65536)):
            with self.assertRaises(ValueError):guard_sql(socket,port,'loja_local','loja_app')
        malicious=str(Path(tempfile.gettempdir())/"$guard$'; SELECT 1/0; --")
        text=guard_sql(malicious,5432,'loja_local','loja_app')
        self.assertIn('DO $guard_$',text)
        from getpass import GetPassWarning
        with patch('app_loja.bootstrap_local.getpass', side_effect=GetPassWarning):
            with self.assertRaises(ValueError): read_secret('TESTE')


@unittest.skipUnless(os.getenv('LOJA_TEST_DB') == '1' and os.name != 'nt',
                     'Requiere el runner POSIX: socket Unix, sudo y /usr/bin/psql')
class BootstrapPostgresTests(unittest.TestCase):
    def test_clean_install_refusal_login_stock_environment_and_secrets(self):
        host, port, admin = (os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        runtime_host = '127.0.0.1' if os.getenv('LOJA_BOOTSTRAP_TCP') == '1' else host
        name = 'bootstrap_descartavel_' + uuid4().hex[:12]
        user = 'bootstrap_app_' + uuid4().hex[:12]
        # Exclusivamente credenciales ficticias; nunca usar secretos de instalación.
        db_secret = 'TESTE-conexao-' + uuid4().hex
        app_secret = 'teste'
        args = dict(socket=host, port=int(port), database=name, user=user,
                    db_password=db_secret, name='TESTE Operação', login='teste_instalacao',
                    app_password=app_secret, categories=['TESTE Categoría'])
        conn = psycopg2.connect(host=host, port=port, dbname='postgres', user=admin)
        try:
            with self.assertRaises(ValueError): install(conn, **{**args, 'port':int(port)+1})
            conn.rollback()
            install(conn, **args)
            with self.assertRaisesRegex(ValueError, 'ya existe'): install(conn, **args)
        finally:
            conn.close()
        with psycopg2.connect(host=host, port=port, dbname=name, user=admin) as conn, conn.cursor() as c:
            c.execute('SELECT count(*),min(login) FROM usuarios')
            self.assertEqual(c.fetchone(), (1,'teste_instalacao'))
            c.execute('SELECT senha_hash FROM usuarios');self.assertNotEqual(c.fetchone()[0], app_secret)
            c.execute('SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=%s',(user,))
            self.assertEqual(c.fetchone(), (True,False,False,False,False))
            c.execute('SELECT rolpassword FROM pg_authid WHERE rolname=%s',(user,))
            self.assertTrue(c.fetchone()[0].startswith('SCRAM-SHA-256$'))
            c.execute('SELECT parent.rolname FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=%s',(user,))
            self.assertEqual(c.fetchall(),[('loja_operador',)])
        # Subprocess realmente usa DB_* e autentica como conexão restrita.
        env = {**os.environ, 'DB_HOST':runtime_host, 'DB_PORT':port, 'DB_NAME':name, 'DB_USER':user, 'DB_PASSWORD':db_secret, 'BOOTSTRAP_TEST_PASSWORD':app_secret}
        code = '''import os
import io
from contextlib import redirect_stdout
from app_loja.config import DB_CONFIG
from app_loja.run import create_app
assert DB_CONFIG['dbname']==os.environ['DB_NAME']
assert DB_CONFIG['user']==os.environ['DB_USER']
app=create_app({'TESTING':True,'SECRET_KEY':'teste-instalacao'})
client=app.test_client()
page=client.get('/login')
with client.session_transaction() as session: csrf=session['csrf']
response=client.post('/login',data={'csrf':csrf,'login':'teste_instalacao','senha':os.environ['BOOTSTRAP_TEST_PASSWORD']})
assert response.status_code==302,response.status_code
assert client.get('/stock').status_code==200
'''
        import sys
        result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0, result.stderr)
        if runtime_host == '127.0.0.1':
            with self.assertRaises(psycopg2.OperationalError):
                psycopg2.connect(host=runtime_host, port=port, dbname=name, user=user, password='TESTE-incorreta')
        with psycopg2.connect(host=runtime_host, port=port, dbname=name, user=user, password=db_secret) as conn,conn.cursor() as c:
            c.execute('SELECT count(*) FROM vw_usuarios');self.assertEqual(c.fetchone()[0],1)
            with self.assertRaises(psycopg2.Error):c.execute('SELECT senha_hash FROM usuarios')
        for command in (['git','diff'], ['git','diff','--cached']):
            diff = subprocess.run(command,capture_output=True,text=True,check=True).stdout
            self.assertNotIn(db_secret,diff)  # Senha operacional fictícia aprovada: teste.

    def test_interactive_command_reports_environment_without_secrets(self):
        from app_loja.bootstrap_local import main
        import sys
        host, port, admin = (os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        database = 'bootstrap_cli_' + uuid4().hex[:12]
        user = 'bootstrap_cli_app_' + uuid4().hex[:12]
        db_secret, app_secret = 'TESTE-' + uuid4().hex, 'teste'
        out = io.StringIO()
        argv = ['bootstrap_local','--socket',host,'--port',port,'--database',database,'--db-user',user]
        actual_run = subprocess.run
        elevated = os.getenv('LOJA_BOOTSTRAP_SUDO')=='1'
        commands = []
        def run(command, **kwargs):
            commands.append((command,kwargs.get('cwd')))
            self.assertNotIn(db_secret,' '.join(command))
            if command==['sudo','-v']:
                return subprocess.CompletedProcess(command,0)
            if command[:5]==['sudo','-n','-u','postgres','--'] and command[5]=='/usr/bin/psql':
                self.assertEqual(kwargs['cwd'],'/')
                self.assertNotIn('PGPASSWORD',kwargs['env'])
                if not elevated:
                    command=command[5:]
                    command[command.index('-U')+1]=admin
            return actual_run(command,**kwargs)
        with patch.object(sys,'argv',argv), patch('builtins.input',side_effect=[database,'TESTE CLI','teste_cli','TESTE Categoría']), patch('app_loja.bootstrap_local.getpass',side_effect=[db_secret,db_secret,app_secret,app_secret]), patch('app_loja.bootstrap_local.subprocess.run',side_effect=run), redirect_stdout(out):
            main()
        text=out.getvalue()
        for setting in ('DB_HOST=127.0.0.1','DB_PORT='+port,'DB_NAME='+database,'DB_USER='+user):
            self.assertIn(setting,text)
        self.assertNotIn(db_secret,text)
        with patch.object(sys,'argv',argv), patch('app_loja.bootstrap_local.getpass') as secret, patch('app_loja.bootstrap_local.subprocess.run',side_effect=run):
            with self.assertRaises(SystemExit) as stopped:main()
            self.assertEqual(stopped.exception.code,1);secret.assert_not_called()
        with psycopg2.connect(host=host,port=port,dbname=database,user=admin) as conn,conn.cursor() as c:
            c.execute("SELECT count(*) FROM fn_autenticar_usuario('teste_cli','teste')")
            self.assertEqual(c.fetchone()[0],1)
        runtime_host='127.0.0.1' if os.getenv('LOJA_BOOTSTRAP_TCP')=='1' else host
        env={**os.environ,'DB_HOST':runtime_host,'DB_PORT':port,'DB_NAME':database,'DB_USER':user,'DB_PASSWORD':db_secret}
        code="""from app_loja.run import create_app
app=create_app({'TESTING':True,'SECRET_KEY':'teste-bootstrap'})
client=app.test_client()
client.get('/login')
with client.session_transaction() as s:csrf=s['csrf']
response=client.post('/login',data={'csrf':csrf,'login':'teste_cli','senha':'teste'})
assert response.status_code==302
assert client.get('/stock').status_code==200
"""
        child=actual_run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
        self.assertEqual(child.returncode,0,child.stderr)
        if elevated:
            # Cenário real: o postgres NÃO consegue executar o venv na home.
            result=actual_run(['sudo','-n','-u','postgres','--','/usr/bin/test','-x',sys.executable],cwd='/',capture_output=True)
            self.assertEqual(result.returncode,1)
        else:
            print('Elevación sudo simulada; ejecución real pendiente si no hay credencial sudo local.')

    def test_initialization_failure_preserves_new_base_and_does_not_create_login(self):
        host, port, admin = (os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        database = 'bootstrap_falha_' + uuid4().hex[:12]
        user = 'bootstrap_falha_app_' + uuid4().hex[:12]
        conn = psycopg2.connect(host=host, port=port, dbname='postgres', user=admin)
        try:
            with patch('app_loja.bootstrap_local.initialize', side_effect=ValueError('estructura inesperada')):
                with self.assertRaisesRegex(ValueError,'preservó'):
                    install(conn,socket=host,port=int(port),database=database,user=user,
                            db_password='TESTE-'+uuid4().hex,name='TESTE',login='teste',
                            app_password='TESTE-'+uuid4().hex,categories=['TESTE'])
            with conn.cursor() as c:
                c.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(database,));self.assertEqual(c.fetchone()[0],1)
                c.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s',(user,));self.assertEqual(c.fetchone()[0],0)
        finally:
            conn.close()

    def test_elevated_install_failure_keeps_new_database(self):
        from app_loja.bootstrap_local import AdminSQL,install_elevated
        host,port,admin=(os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        database='bootstrap_elev_falha_'+uuid4().hex[:12]
        user='bootstrap_elev_app_'+uuid4().hex[:12]
        actual_run=subprocess.run
        def run(command,**kwargs):
            if os.getenv('LOJA_BOOTSTRAP_SUDO')!='1':
                command=command[5:]
                command[command.index('-U')+1]=admin
            return actual_run(command,**kwargs)
        with patch('app_loja.bootstrap_local.subprocess.run',side_effect=run),patch('app_loja.install_schema.destination_source',return_value='BEGIN; CREATE TABLE fixture_falha(id integer); SELECT 1/0; COMMIT;'):
            with self.assertRaises(ValueError):
                install_elevated(AdminSQL(host,int(port)),socket=host,port=int(port),database=database,user=user,
                                 db_password='TESTE-'+uuid4().hex,name='TESTE',login='teste',app_password='teste',categories=['TESTE'])
        with psycopg2.connect(host=host,port=port,dbname=database,user=admin) as conn,conn.cursor() as c:
            c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'");self.assertEqual(c.fetchone()[0],0)
            c.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s',(user,));self.assertEqual(c.fetchone()[0],0)

    def test_elevated_secret_failure_is_atomic_and_not_logged(self):
        from pathlib import Path
        from app_loja.bootstrap_local import AdminSQL,install_elevated
        host,port,admin=(os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        database='bootstrap_secret_falha_'+uuid4().hex[:12]
        user='bootstrap_secret_app_'+uuid4().hex[:12]
        db_secret='TESTE-sigilo-'+uuid4().hex
        app_secret='TESTE-sigilo-'+uuid4().hex
        actual_run=subprocess.run
        def run(command,**kwargs):
            # Injetar falha DEPOIS de configurar usuário/role, antes do COMMIT.
            source=kwargs['input'];head,separator,tail=source.rpartition('COMMIT;')
            kwargs['input']=head+'SELECT 1/0; COMMIT;'+tail
            if os.getenv('LOJA_BOOTSTRAP_SUDO')!='1':
                command=command[5:];command[command.index('-U')+1]=admin
            return actual_run(command,**kwargs)
        with patch('app_loja.bootstrap_local.subprocess.run',side_effect=run):
            with self.assertRaises(ValueError) as error:
                install_elevated(AdminSQL(host,int(port)),socket=host,port=int(port),database=database,user=user,
                                 db_password=db_secret,name='TESTE',login='teste',app_password=app_secret,categories=['TESTE'])
        self.assertNotIn(db_secret,str(error.exception));self.assertNotIn(app_secret,str(error.exception))
        with psycopg2.connect(host=host,port=port,dbname=database,user=admin) as conn,conn.cursor() as c:
            c.execute('SELECT count(*) FROM usuarios');self.assertEqual(c.fetchone()[0],0)
            c.execute('SELECT count(*) FROM tipos_tela');self.assertEqual(c.fetchone()[0],0)
            c.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s',(user,));self.assertEqual(c.fetchone()[0],0)
        if os.getenv('LOJA_BOOTSTRAP_LOG'):
            log=Path(os.environ['LOJA_BOOTSTRAP_LOG']).read_text()
            self.assertNotIn(db_secret,log);self.assertNotIn(app_secret,log)

    def test_socket_sql_injection_and_wrong_destination_leave_no_base(self):
        from app_loja.bootstrap_local import AdminSQL,guard_sql
        from app_loja.install_schema import destination_source
        host,port,admin=(os.environ[k] for k in ('PGHOST','PGPORT','PGUSER'))
        database='bootstrap_destino_'+uuid4().hex[:12];user='bootstrap_destino_app_'+uuid4().hex[:12]
        actual_run=subprocess.run
        def run(command,**kwargs):
            if os.getenv('LOJA_BOOTSTRAP_SUDO')!='1':
                command=command[5:];command[command.index('-U')+1]=admin
            return actual_run(command,**kwargs)
        for expected in (host+"/$guard$'; END; $guard$; SELECT 1/0; --",host+"/$destination$'; END; $destination$; SELECT 1/0; --"):
            with patch('app_loja.bootstrap_local.subprocess.run',side_effect=run):
                with self.assertRaises(ValueError):
                    AdminSQL(host,int(port)).execute(guard_sql(expected,int(port),database,user))
                with self.assertRaises(ValueError):
                    AdminSQL(host,int(port)).execute(destination_source(database=database,port=int(port),socket=expected))
        with psycopg2.connect(host=host,port=port,dbname='postgres',user=admin) as conn,conn.cursor() as c:
            c.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(database,));self.assertEqual(c.fetchone()[0],0)
