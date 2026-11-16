"""Roles Administrador, Empleado y Cajero: menú, rutas y segunda barrera en el banco."""
import os
import unittest
from decimal import Decimal
from uuid import uuid4

from app_loja import permisos

ADMIN, EMPLEADO, CAJERO = permisos.ADMIN, permisos.EMPLEADO, permisos.CAJERO


class PermisosTests(unittest.TestCase):
    def test_every_registered_route_belongs_to_a_declared_area(self):
        from app_loja.run import create_app
        app = create_app({'TESTING': True, 'SECRET_KEY': 'fixture-only'})
        for rule in app.url_map.iter_rules():
            with self.subTest(endpoint=rule.endpoint):
                # Una ruta sin área declarada quedaría negada hasta para el Administrador.
                self.assertTrue(permisos.allowed(rule.endpoint, 'GET', ADMIN))
        self.assertFalse(permisos.allowed('modulo_nuevo.pantalla', 'GET', ADMIN))

    def test_matrix_by_role(self):
        cases = {
            'entrada.stock': {EMPLEADO: True, CAJERO: False},
            'entrada.nuevo_producto': {EMPLEADO: True, CAJERO: False},
            'entrada.confirmar': {EMPLEADO: True, CAJERO: False},
            'ticket.index': {EMPLEADO: True, CAJERO: True},
            'corte.confirmar': {EMPLEADO: True, CAJERO: True},
            'caixa.index': {EMPLEADO: False, CAJERO: True},
            'caixa.recibir': {EMPLEADO: False, CAJERO: True},
            'conteo.consulta': {EMPLEADO: False, CAJERO: True},
            'conteo.fondo': {EMPLEADO: False, CAJERO: True},
            'conteo.confirmar': {EMPLEADO: False, CAJERO: True},
            'precios.index': {EMPLEADO: False, CAJERO: False},
            'precios.confirmar': {EMPLEADO: False, CAJERO: False},
        }
        for endpoint, expected in cases.items():
            for method in ('GET', 'POST'):
                with self.subTest(endpoint=endpoint, method=method):
                    self.assertTrue(permisos.allowed(endpoint, method, ADMIN))
                    for perfil, value in expected.items():
                        self.assertEqual(permisos.allowed(endpoint, method, perfil), value)
                    # Un perfil desconocido (p. ej. el antiguo 'operador') no abre nada.
                    self.assertFalse(permisos.allowed(endpoint, method, 'operador'))
                    self.assertFalse(permisos.allowed(endpoint, method, None))

    def test_photos_are_visible_to_every_role_but_only_stock_roles_upload(self):
        for endpoint in ('entrada.foto', 'entrada.miniatura'):
            for perfil in (ADMIN, EMPLEADO, CAJERO):
                self.assertTrue(permisos.allowed(endpoint, 'GET', perfil))
            self.assertFalse(permisos.allowed(endpoint, 'GET', 'operador'))
        self.assertFalse(permisos.allowed('entrada.foto', 'POST', CAJERO))
        self.assertTrue(permisos.allowed('entrada.foto', 'POST', EMPLEADO))

    def test_menu_and_first_screen(self):
        labels = {perfil: [label for _endpoint, label in permisos.menu(perfil)] for perfil in (ADMIN, EMPLEADO, CAJERO)}
        self.assertEqual(labels[ADMIN], ['Productos y stock', 'Corte / Ticket', 'Caja / Venta', 'Precios'])
        self.assertEqual(labels[EMPLEADO], ['Productos y stock', 'Corte / Ticket'])
        self.assertEqual(labels[CAJERO], ['Corte / Ticket', 'Caja / Venta'])
        self.assertEqual([permisos.home(p) for p in (ADMIN, EMPLEADO, CAJERO)],
                         ['entrada.stock', 'entrada.stock', 'ticket.index'])
        self.assertEqual(permisos.menu('operador'), [])
        self.assertEqual([login for login, _perfil in permisos.CUENTAS], ['administrador', 'empleado', 'cajero'])


@unittest.skipUnless(os.getenv('LOJA_TEST_DB') == '1' and os.getenv('LOJA_BOOTSTRAP_TCP') != '1',
                     'Requiere la base descartable con schema del runner')
class RolesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from app_loja import db
        from app_loja.run import create_app
        cls.pg = psycopg2
        cls.admin_config = dict(host=os.environ['PGHOST'], port=os.environ['PGPORT'],
                                dbname=os.environ['PGDATABASE'], user=os.environ['PGUSER'])
        cls.users = {}
        conn = psycopg2.connect(**cls.admin_config)
        try:
            with conn, conn.cursor() as c:
                c.execute('CREATE ROLE loja_test_roles LOGIN')
                c.execute('GRANT loja_operador TO loja_test_roles')
                c.execute("INSERT INTO public.tipos_tela(nome) VALUES(%s) RETURNING id", ('Roles '+uuid4().hex,))
                cls.category = c.fetchone()[0]
                for perfil in (ADMIN, EMPLEADO, CAJERO):
                    c.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES"
                              "(%s,%s,public.crypt('fixture-only',public.gen_salt('bf')),%s) RETURNING id",
                              (permisos.NOMBRES[perfil], 'roles_'+perfil, perfil))
                    cls.users[perfil] = c.fetchone()[0]
        finally:
            conn.close()
        cls.db = db
        cls.original = db.DB_CONFIG
        db.DB_CONFIG = {**cls.admin_config, 'user': 'loja_test_roles'}
        cls.app = create_app({'TESTING': True, 'SECRET_KEY': 'fixture-roles-only'})
        cls.product = db.cadastrar_produto(cls.product_data(), cls.users[ADMIN])
        db.confirmar_ingresso(str(uuid4()), [{'produto_id': cls.product, 'rolos': 1, 'quantidade': '50'}], cls.users[ADMIN])

    @classmethod
    def tearDownClass(cls):
        cls.db.DB_CONFIG = cls.original

    @classmethod
    def product_data(cls):
        return {'tipo_id': cls.category, 'nome': 'Roles '+uuid4().hex, 'unidade': 'm', 'preco': Decimal('10'),
                'largura': None, 'padrao': None}

    def query(self, statement, args=()):
        conn = self.pg.connect(**self.admin_config)
        try:
            with conn, conn.cursor() as c:
                c.execute(statement, args)
                return c.fetchall() if c.description else None
        finally:
            conn.close()

    def login(self, perfil):
        client = self.app.test_client()
        client.get('/login')
        response = self.post(client, '/login', {'login': 'roles_'+perfil, 'senha': 'fixture-only'})
        self.assertEqual(response.status_code, 302)
        # El ingreso renueva la sesión; el primer pedido posterior emite el nuevo token CSRF.
        client.get(response.location)
        return client, response.location

    def post(self, client, path, data):
        with client.session_transaction() as s:
            data = {**data, 'csrf': s['csrf']}
        return client.post(path, data=data)

    def lot(self):
        return self.query('SELECT id FROM public.estoque_lotes WHERE produto_id=%s', (self.product,))[0][0]

    def cut(self, ticket, user):
        return self.db.registrar_corte({'ticket_id': ticket, 'produto_id': self.product, 'quantidade_vendida': '1',
                                        'quantidade_cortada': '1', 'chave': str(uuid4()),
                                        'alocacoes': [{'lote_id': self.lot(), 'quantidade': '1'}]}, user)

    def denied(self, call):
        with self.assertRaises(self.pg.Error) as error:
            call()
        self.assertEqual(error.exception.pgcode, '42501')

    def test_login_offers_the_three_roles_and_lands_on_each_first_screen(self):
        page = self.app.test_client().get('/login').get_data(as_text=True)
        for login, perfil in permisos.CUENTAS:
            self.assertIn(f'<option value="{login}"', page)
            self.assertIn(permisos.NOMBRES[perfil], page)
        for perfil, home in ((ADMIN, '/stock'), (EMPLEADO, '/stock'), (CAJERO, '/tickets')):
            client, location = self.login(perfil)
            self.assertEqual(location, home)
            self.assertEqual(client.get('/').location, home)
            self.assertEqual(client.get('/login').location, home)

    def test_each_role_opens_only_its_screens_and_sees_only_its_menu(self):
        ticket = self.db.iniciar_ticket(str(uuid4()), self.users[ADMIN])
        self.cut(ticket, self.users[ADMIN])
        day = self.query('SELECT public.fn_data_operacional()')[0][0].isoformat()
        routes = {
            '/stock': (EMPLEADO,), '/productos/nuevo': (EMPLEADO,), f'/productos/{self.product}': (EMPLEADO,),
            f'/entrada?produto_id={self.product}': (EMPLEADO,),
            '/tickets': (EMPLEADO, CAJERO), f'/tickets/{ticket}': (EMPLEADO, CAJERO),
            f'/tickets/{ticket}/productos': (EMPLEADO, CAJERO),
            f'/tickets/{ticket}/corte/{self.product}': (EMPLEADO, CAJERO),
            '/caixa': (CAJERO,), f'/caixa/tickets/{ticket}': (CAJERO,), '/caixa/consulta': (CAJERO,),
            '/caixa/cierre': (CAJERO,),
            '/precios': (),
        }
        for perfil in (ADMIN, EMPLEADO, CAJERO):
            client, home = self.login(perfil)
            menu = client.get(home).get_data(as_text=True)
            for _endpoint, label, _roles in permisos.MENU:
                self.assertEqual(f'>{label}</a>' in menu, label in dict(permisos.menu(perfil)).values(), (perfil, label))
            self.assertIn(f'<span class="user">{permisos.NOMBRES[perfil]}</span>', menu)
            for route, roles in routes.items():
                with self.subTest(perfil=perfil, route=route):
                    expected = 200 if perfil == ADMIN or perfil in roles else 403
                    response = client.get(route)
                    self.assertEqual(response.status_code, expected)
                    if expected == 403:
                        self.assertIn('Tu rol no tiene acceso', response.get_data(as_text=True))
            # El enlace a Caja solo aparece para quien puede cobrar.
            self.assertEqual('Ir a Caja / Venta' in client.get(f'/tickets/{ticket}').get_data(as_text=True),
                             perfil != EMPLEADO)
            self.assertEqual(client.get(f'/caixa/cierre/{day}').status_code, 403 if perfil == EMPLEADO else 404)

    def test_cajero_cannot_change_stock_by_form_or_database_but_sees_photos(self):
        client, _home = self.login(CAJERO)
        before = self.query('SELECT count(*) FROM public.produtos')[0][0]
        forms = {'/productos/nuevo': {'nome': 'Intruso', 'tipo_id': str(self.category), 'unidade': 'm', 'preco': '1'},
                 '/entrada/revisar': {'produto_id': str(self.product), 'rolos': '1', 'quantidade': '5'},
                 '/entrada/confirmar': {'chave': str(uuid4())},
                 f'/productos/{self.product}/foto': {}}
        for path, data in forms.items():
            with self.subTest(path=path):
                self.assertEqual(self.post(client, path, data).status_code, 403)
        # Ver una foto está permitido: sin foto responde 404, no 403.
        self.assertEqual(client.get(f'/productos/{self.product}/foto/miniatura').status_code, 404)
        user = self.users[CAJERO]
        self.denied(lambda: self.db.cadastrar_produto(self.product_data(), user))
        self.denied(lambda: self.db.confirmar_ingresso(
            str(uuid4()), [{'produto_id': self.product, 'rolos': 1, 'quantidade': '5'}], user))
        self.assertEqual(self.query('SELECT count(*) FROM public.produtos')[0][0], before)
        self.assertEqual(self.query('SELECT count(*) FROM public.estoque_lotes WHERE produto_id=%s', (self.product,))[0][0], 1)

    def test_empleado_loads_stock_and_cuts_and_cajero_cuts_and_receives(self):
        empleado, cajero = self.users[EMPLEADO], self.users[CAJERO]
        product = self.db.cadastrar_produto(self.product_data(), empleado)
        self.db.confirmar_ingresso(str(uuid4()), [{'produto_id': product, 'rolos': 1, 'quantidade': '5'}], empleado)
        ticket = self.db.iniciar_ticket(str(uuid4()), empleado)
        self.cut(ticket, empleado)
        self.cut(ticket, cajero)
        draft = {'ticket_id': ticket, 'conferencia': self.db.conferir_ticket(ticket)[0]['conferencia'], 'efectivo': '5'}
        self.denied(lambda: self.db.receber_ticket(draft, empleado))
        self.assertEqual(self.query('SELECT status FROM public.tickets WHERE id=%s', (ticket,)), [('pendente',)])
        self.db.receber_ticket(draft, cajero)
        self.assertEqual(self.query('SELECT status,(SELECT recebido_por FROM public.vendas WHERE ticket_id=t.id) '
                                    'FROM public.tickets t WHERE id=%s', (ticket,)), [('pago', cajero)])

    def test_old_profile_is_rejected_by_the_database(self):
        with self.assertRaises(self.pg.Error):
            self.query("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES('x',%s,'x','operador')",
                       ('roles_'+uuid4().hex,))


if __name__ == '__main__':
    unittest.main()
