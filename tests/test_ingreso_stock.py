"""Pruebas de 1A. Integración solo contra el cluster descartable del runner."""
import os
import io
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from app_loja.validation import decimal_input, groups_input, product_input


class DecimalValidationTests(unittest.TestCase):
    def test_comma_without_rounding(self):
        self.assertEqual(decimal_input('30,125', 'Cantidad', 3), Decimal('30.125'))
        self.assertEqual(groups_input(1, ['4', '1'], ['30', '45']),
                         [{'produto_id': 1, 'rolos': 4, 'quantidade': '30'},
                          {'produto_id': 1, 'rolos': 1, 'quantidade': '45'}])

    def test_invalid_values(self):
        for value in ('NaN', 'Infinity', '-1', '0', '1.0001', '1.234,00', '1000000000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal_input(value, 'Cantidad', 3)
        for rolls in ('0', '-2', '1.5', 'abc'):
            with self.subTest(rolls=rolls), self.assertRaises(ValueError):
                groups_input(1, [rolls], ['30'])
        with self.assertRaises(ValueError):
            groups_input(1, ['1'], [])

    def test_optional_fields_and_price(self):
        data = product_input({'nome': ' Lino azul ', 'tipo_id': '1',
                              'unidade': 'm', 'preco': '25,50'})
        self.assertEqual(data['nome'], 'Lino azul')
        self.assertEqual(data['preco'], Decimal('25.50'))
        self.assertIsNone(data['largura'])
        self.assertIsNone(data['padrao'])
        with self.assertRaises(ValueError):
            product_input({'nome': 'Lino', 'tipo_id': '1', 'unidade': 'm',
                           'preco': '25,50', 'largura': '1000'})

    def test_initial_price_thousands_never_become_decimal_price(self):
        for raw,expected in (('12500','12500'),('12.500','12500'),
                             ('12.500,50','12500.50'),('12500,50','12500.50')):
            with self.subTest(raw=raw):
                data=product_input({'nome':'Fixture','tipo_id':'1','unidade':'m','preco':raw})
                self.assertEqual(data['preco'],Decimal(expected))
        for raw in ('12.50,00','12.5000','NaN','-12.500','1,001'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                product_input({'nome':'Fixture','tipo_id':'1','unidade':'m','preco':raw})


@unittest.skipUnless(os.getenv('LOJA_TEST_DB') == '1', 'Requiere el cluster descartable del runner')
class IngresoStockIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from app_loja import db
        from app_loja.run import create_app
        cls.psycopg2 = psycopg2
        cls.admin_config = dict(host=os.environ['PGHOST'], port=os.environ['PGPORT'],
                               dbname=os.environ['PGDATABASE'], user=os.environ['PGUSER'])
        conn = psycopg2.connect(**cls.admin_config)
        try:
            with conn, conn.cursor() as c:
                c.execute('CREATE ROLE loja_test_app LOGIN')
                c.execute('GRANT loja_operador TO loja_test_app')
                c.execute("INSERT INTO public.usuarios (nome,login,senha_hash,perfil) VALUES "
                          "('Atendente teste','atendente_1a',public.crypt(%s,public.gen_salt('bf')),'admin') RETURNING id",
                          ('test-only-password',))
                cls.usuario_id = c.fetchone()[0]
        finally:
            conn.close()
        cls.operator_config = {**cls.admin_config, 'user': 'loja_test_app'}
        cls.original_db_config = db.DB_CONFIG
        db.DB_CONFIG = cls.operator_config
        cls.db = db
        cls.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-session'})

    @classmethod
    def tearDownClass(cls):
        cls.db.DB_CONFIG = cls.original_db_config

    def setUp(self):
        self.client = self.app.test_client()
        self.client.get('/login')
        with self.client.session_transaction() as s:
            token = s['csrf']
        response = self.client.post('/login', data={
            'csrf': token, 'login': 'atendente_1a', 'senha': 'test-only-password'})
        self.assertEqual(response.status_code, 302)

    def post(self, path, data):
        self.client.get('/stock')
        with self.client.session_transaction() as s:
            data = {**data, 'csrf': s['csrf']}
        return self.client.post(path, data=data)

    def create_product(self):
        return self.db.cadastrar_produto(product_input({
            'nome': f'Lino {uuid4()}', 'tipo_id': '1', 'unidade': 'm',
            'preco': '25,50', 'padrao': '30', 'largura': '1,40'}), self.usuario_id)

    def admin_query(self, sql, args=()):
        conn = self.psycopg2.connect(**self.admin_config)
        try:
            with conn, conn.cursor() as c:
                c.execute(sql, args)
                return c.fetchall() if c.description else None
        finally:
            conn.close()

    def test_complete_web_flow_and_persistence(self):
        name = f'Producto web {uuid4()}'
        response = self.post('/productos/nuevo', {
            'nome': name, 'tipo_id': '1', 'unidade': 'm', 'preco': '18,50', 'padrao': '30'})
        self.assertEqual(response.status_code, 302)
        product_id = int(response.location.split('produto_id=')[1])
        form = self.client.get(response.location)
        self.assertIn(b'lang="es-AR"', form.data)
        self.assertIn(b'Ingresar stock', form.data)
        self.assertIn(b'value="30"', form.data)
        response = self.post('/entrada/revisar', {
            'produto_id': str(product_id), 'rolos': ['4', '1'], 'quantidade': ['30', '45']})
        self.assertEqual(response.status_code, 302)
        review = self.client.get(response.location)
        self.assertIn(b'165 m', review.data)
        self.assertEqual(self.admin_query(
            'SELECT count(*) FROM public.estoque_lotes WHERE produto_id=%s', (product_id,))[0][0], 0)
        with self.client.session_transaction() as s:
            key = s['ingresso']['chave']
        response = self.post('/entrada/confirmar', {'chave': key})
        self.assertEqual(response.status_code, 302)
        result = self.client.get(response.location)
        self.assertIn(b'Ingreso confirmado', result.data)
        repeated = self.post('/entrada/confirmar', {'chave': key})
        self.assertEqual(response.location, repeated.location)
        lots = self.admin_query('SELECT quantidade_inicial,quantidade_atual FROM '
                               'public.estoque_lotes WHERE produto_id=%s ORDER BY id', (product_id,))
        self.assertEqual(lots, [(Decimal(30), Decimal(30))] * 4 + [(Decimal(45), Decimal(45))])
        self.assertEqual(self.admin_query('SELECT estoque_total,maior_lote_disponivel FROM '
                        'public.vw_estoque_por_produto WHERE produto_id=%s', (product_id,)),
                         [(Decimal(165), Decimal(45))])
        self.post('/logout', {})
        self.setUp()  # Nueva sesión HTTP, mismas filas persistidas en PostgreSQL.
        detail = self.client.get(f'/productos/{product_id}')
        self.assertIn(name.encode(), detail.data)
        self.assertIn(b'165 m', detail.data)
        self.assertIn(b'Declarado', detail.data)
        self.assertIn(b'Ingreso ', detail.data)
        filtered = self.client.get('/stock', query_string={'q': name, 'categoria': '1'})
        self.assertIn(name.encode(), filtered.data)

    def test_es_ar_prices_persist_and_display_without_silent_reduction(self):
        for raw,expected,shown in (('12500','12500','12.500,00'),('12.500','12500','12.500,00'),
            ('12.500,50','12500.50','12.500,50'),('12500,50','12500.50','12.500,50')):
            with self.subTest(raw=raw):
                name='Precio QA '+str(uuid4())
                response=self.post('/productos/nuevo',{'nome':name,'tipo_id':'1','unidade':'m','preco':raw})
                self.assertEqual(response.status_code,302)
                product_id=int(response.location.split('produto_id=')[1])
                self.assertEqual(self.admin_query('SELECT preco_unitario FROM produtos WHERE id=%s',
                    (product_id,))[0][0],Decimal(expected))
                self.assertIn(shown,self.client.get(f'/productos/{product_id}').get_data(as_text=True))
                self.assertIn(shown,self.client.get('/stock',query_string={'q':name}).get_data(as_text=True))

    def test_stock_search_ignores_accents_in_name_and_category(self):
        name='Gabardina petróleo '+str(uuid4())
        product_id=self.db.cadastrar_produto(product_input({'nome':name,'tipo_id':'1',
            'unidade':'m','preco':'8500,50'}),self.usuario_id)
        for query in ('petróleo','petroleo','PETROLEO','PETRÓLEO','petro\u0301leo'):
            with self.subTest(query=query):
                self.assertIn(name,self.client.get('/stock',query_string={'q':query,'categoria':'1'}).get_data(as_text=True))
        self.assertEqual(self.admin_query('SELECT nome FROM produtos WHERE id=%s',(product_id,))[0][0],name)
        self.admin_query("INSERT INTO tipos_tela(nome) VALUES(%s) RETURNING id",('Categoría '+str(uuid4()),))
        category=self.admin_query('SELECT max(id) FROM tipos_tela')[0][0]
        category_name=self.admin_query('SELECT nome FROM tipos_tela WHERE id=%s',(category,))[0][0]
        other=self.db.cadastrar_produto(product_input({'nome':'Sin acento '+str(uuid4()),'tipo_id':str(category),
            'unidade':'m','preco':'10'}),self.usuario_id)
        self.assertIn(f'/productos/{other}',self.client.get('/stock',query_string={'q':category_name.replace('í','i')}).get_data(as_text=True))

    def test_price_hashes_and_declared_quantity_protected(self):
        product_id = self.create_product()
        key = str(uuid4())
        groups = [{'produto_id': product_id, 'rolos': 1, 'quantidade': '30'}]
        ingreso_id = self.db.confirmar_ingresso(key, groups, self.usuario_id)
        for sql, args in (
            ('UPDATE public.produtos SET preco_unitario=1 WHERE id=%s', (product_id,)),
            ('SELECT senha_hash FROM public.usuarios', ()),
            ('UPDATE public.itens_ingresso SET quantidade=40 WHERE ingresso_id=%s', (ingreso_id,)),
            ('UPDATE public.estoque_lotes SET quantidade_atual=40 WHERE produto_id=%s', (product_id,)),
            ('INSERT INTO public.ingressos (registrado_por) VALUES (%s)', (self.usuario_id,)),
        ):
            with self.subTest(sql=sql), self.assertRaises(self.psycopg2.errors.InsufficientPrivilege):
                self.db.fetchall(sql, args)
        self.assertEqual(self.admin_query('SELECT preco_unitario FROM public.produtos WHERE id=%s',
                                         (product_id,))[0][0], Decimal('25.50'))
        with self.assertRaises(self.psycopg2.Error):
            self.admin_query('UPDATE public.itens_ingresso SET quantidade=40 WHERE ingresso_id=%s', (ingreso_id,))
        auth = self.db.fetchone('SELECT * FROM public.fn_autenticar_usuario(%s,%s)',
                               ('atendente_1a', 'test-only-password'))
        self.assertEqual(set(auth), {'id', 'nome', 'login', 'perfil'})

    def test_partial_failure_rolls_back_and_retry_is_safe(self):
        product_id = self.create_product()
        key = str(uuid4())
        bad = [{'produto_id': product_id, 'rolos': 2, 'quantidade': '30'},
               {'produto_id': 9223372036854775807, 'rolos': 1, 'quantidade': '45'}]
        with self.assertRaises(self.psycopg2.Error):
            self.db.confirmar_ingresso(key, bad, self.usuario_id)
        self.assertEqual(self.admin_query('SELECT count(*) FROM public.estoque_lotes WHERE produto_id=%s',
                                         (product_id,))[0][0], 0)
        self.assertEqual(self.admin_query('SELECT count(*) FROM public.ingressos WHERE chave_confirmacao=%s',
                                         (key,))[0][0], 0)
        good = [{'produto_id': product_id, 'rolos': 2, 'quantidade': '30'}]
        first = self.db.confirmar_ingresso(key, good, self.usuario_id)
        self.assertEqual(first, self.db.confirmar_ingresso(key, good, self.usuario_id))
        with self.assertRaises(self.psycopg2.Error):
            self.db.confirmar_ingresso(key, bad, self.usuario_id)
        self.assertEqual(self.admin_query('SELECT count(*) FROM public.vw_reconciliacao_estoque '
                                         'WHERE diferenca<>0')[0][0], 0)

    def test_csrf_validation_and_deferred_modules_unavailable(self):
        self.assertEqual(self.client.post('/productos/nuevo', data={'nome': 'sin csrf'}).status_code, 400)
        for path in ('/conteo', '/aprovar'):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertNotIn(b'aprobaci', self.client.get('/stock').data)
        product_id = self.create_product()
        for roll, quantity in (('1.5', '30'), ('2', 'NaN'), ('4', '30.0001')):
            response = self.post('/entrada/revisar', {'produto_id': str(product_id),
                                                     'rolos': [roll], 'quantidade': [quantity]})
            self.assertEqual(response.status_code, 400)

    def test_initial_setup_is_atomic_and_login_stays_safe(self):
        from app_loja.setup_local import main
        login = f'fixture_{uuid4()}'
        category = f'Categoría {uuid4()}'
        second_category = f'Categoría {uuid4()}'
        output = io.StringIO()
        for name, fails in ((category, False), (second_category, True)):
            with patch('sys.argv', ['setup_local', '--categoria', name, '--nombre', 'Fixture',
                                    '--login', login]), \
                 patch('app_loja.setup_local.getpass', return_value='fixture-password'), \
                 redirect_stdout(output), redirect_stderr(output):
                if fails:
                    with self.assertRaises(SystemExit):
                        main()
                else:
                    main()
        self.assertNotIn('fixture-password', output.getvalue())
        self.assertEqual(self.admin_query('SELECT count(*) FROM public.tipos_tela WHERE nome=%s',
                                         (second_category,))[0][0], 0)
        self.assertIsNotNone(self.db.fetchone('SELECT * FROM public.fn_autenticar_usuario(%s,%s)',
                                              (login, 'fixture-password')))
        self.assertIsNone(self.db.fetchone('SELECT * FROM public.fn_autenticar_usuario(%s,%s)',
                                          (login, 'wrong-password')))
        self.admin_query('UPDATE public.usuarios SET ativo=false WHERE login=%s', (login,))
        self.assertIsNone(self.db.fetchone('SELECT * FROM public.fn_autenticar_usuario(%s,%s)',
                                          (login, 'fixture-password')))

    def test_decimal_quantities_and_original_product_suggestion(self):
        product_id = self.create_product()
        key = str(uuid4())
        groups = groups_input(product_id, ['2'], ['45,125'])
        ingreso_id = self.db.confirmar_ingresso(key, groups, self.usuario_id)
        self.assertEqual(self.admin_query('SELECT quantidade FROM public.itens_ingresso '
                                         'WHERE ingresso_id=%s ORDER BY id', (ingreso_id,)),
                         [(Decimal('45.125'),)] * 2)
        self.assertEqual(self.admin_query('SELECT quantidade_padrao_lote FROM public.produtos '
                                         'WHERE id=%s', (product_id,)), [(Decimal(30),)])

    def test_real_concurrent_confirmation_waits_and_is_idempotent(self):
        from psycopg2.extras import Json
        product_id = self.create_product()
        key = str(uuid4())
        groups = [{'produto_id': product_id, 'rolos': 4, 'quantidade': '30'},
                  {'produto_id': product_id, 'rolos': 1, 'quantidade': '45'}]
        a = self.psycopg2.connect(**self.operator_config)
        b = self.psycopg2.connect(**self.operator_config)
        try:
            with a.cursor() as c:
                c.execute('SET ROLE loja_operador')
                c.execute('SELECT public.fn_confirmar_ingresso(%s,%s,%s)', (key, Json(groups), self.usuario_id))
                first_id = c.fetchone()[0]

            def second():
                with b, b.cursor() as c:
                    c.execute('SET ROLE loja_operador')
                    c.execute("SET LOCAL statement_timeout='8s'")
                    c.execute('SELECT public.fn_confirmar_ingresso(%s,%s,%s)', (key, Json(groups), self.usuario_id))
                    return c.fetchone()[0]

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(second)
                waited = False
                for _ in range(50):
                    state = self.admin_query('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',
                                             (b.get_backend_pid(),))
                    if state and state[0][0] == 'Lock':
                        waited = True
                        break
                    time.sleep(0.02)
                a.commit()
                self.assertTrue(waited, 'La segunda conexión debe esperar el lock de confirmación.')
                self.assertEqual(first_id, future.result(timeout=10))
            self.assertEqual(self.admin_query('SELECT count(*) FROM public.estoque_lotes '
                                             'WHERE produto_id=%s', (product_id,))[0][0], 5)
            self.assertEqual(self.admin_query('SELECT count(*) FROM public.movimentacoes '
                                             'WHERE produto_id=%s AND tipo=\'ENTRADA\'', (product_id,))[0][0], 5)
        finally:
            a.close()
            b.close()


if __name__ == '__main__':
    unittest.main()
