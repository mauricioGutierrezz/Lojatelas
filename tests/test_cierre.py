"""Cierre: cada prueba usa una base descartable independiente para cerrar fechas reales."""
import os
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_caja_venta as fixtures


@unittest.skipUnless(os.getenv('LOJA_TEST_DB')=='1','Requiere el cluster descartable del runner')
class CierreIntegrationTests(unittest.TestCase):
    query = fixtures.CajaVentaIntegrationTests.query
    post = fixtures.CajaVentaIntegrationTests.post
    login = fixtures.CajaVentaIntegrationTests.login
    cut = fixtures.CajaVentaIntegrationTests.cut
    physical = fixtures.CajaVentaIntegrationTests.physical
    run_pair = fixtures.CajaVentaIntegrationTests.run_pair
    sql_receive = fixtures.CajaVentaIntegrationTests.sql_receive
    receipt_draft = fixtures.CajaVentaIntegrationTests.draft

    @classmethod
    def setUpClass(cls):
        import psycopg2
        from app_loja import db
        cls.pg = psycopg2
        cls.db = db
        cls.original = db.DB_CONFIG
        cls.cluster_config = dict(host=os.environ['PGHOST'],port=os.environ['PGPORT'],
            dbname='postgres',user=os.environ['PGUSER'])
        conn = cls.pg.connect(**cls.cluster_config)
        try:
            with conn,conn.cursor() as c:
                c.execute('CREATE ROLE loja_test_cierre LOGIN')
                c.execute('GRANT loja_operador TO loja_test_cierre')
        finally:
            conn.close()

    def setUp(self):
        from psycopg2 import sql
        from app_loja.run import create_app
        self.database = 'loja_cierre_'+uuid4().hex
        conn = self.pg.connect(**self.cluster_config)
        try:
            conn.autocommit = True
            with conn.cursor() as c:
                c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.database)))
        finally:
            conn.close()
        self.admin_config = {**self.cluster_config,'dbname':self.database}
        self.operator_config = {**self.admin_config,'user':'loja_test_cierre'}
        conn = self.pg.connect(**self.admin_config)
        try:
            with conn,conn.cursor() as c:
                c.execute((Path(__file__).resolve().parents[1]/'schema.sql').read_text(encoding='utf-8'))
        finally:
            conn.close()
        self.query("INSERT INTO public.tipos_tela(nome) VALUES ('Telas')")
        self.users = []
        for name in ('Ana','Berta'):
            self.users.append(self.query("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES"
                "(%s,%s,public.crypt('fixture-only',public.gen_salt('bf')),'admin') RETURNING id",
                (name,'caja_'+name))[0][0])
        self.roles = {perfil: self.query("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES"
            "(%s,%s,public.crypt('fixture-only',public.gen_salt('bf')),%s) RETURNING id",
            (perfil.title(),'caja_'+perfil.title(),perfil))[0][0] for perfil in ('cajero','empleado')}
        self.db.DB_CONFIG = self.operator_config
        self.app = create_app({'TESTING':True,'SECRET_KEY':'fixture-cierre-only'})
        self.client = self.login()
        self.day = self.query('SELECT public.fn_data_operacional()')[0][0]
        self.product = self.db.cadastrar_produto({'tipo_id':1,'nome':'Lino','unidade':'m',
            'preco':Decimal(10),'largura':None,'padrao':None},self.users[0])
        self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':self.product,'rolos':1,'quantidade':'100'}],self.users[0])
        self.lots = [self.query('SELECT id FROM public.estoque_lotes')[0][0]]
        self.ticket = self.db.iniciar_ticket(str(uuid4()),self.users[0])
        self.cut('2','3')

    def tearDown(self):
        from psycopg2 import sql
        self.db.DB_CONFIG = self.original
        conn = self.pg.connect(**self.cluster_config)
        try:
            conn.autocommit = True
            with conn.cursor() as c:
                c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(self.database)))
        finally:
            conn.close()

    def fund(self,value='100',day=None,key=None,user=None):
        return self.db.registrar_fundo({'data':(day or self.day).isoformat(),'chave':key or str(uuid4())},
            value,user or self.users[0])

    def unlock(self,client=None):
        # El PIN general fue reemplazado por los roles: no hay nada que desbloquear.
        return client or self.client

    def token(self,response):
        self.assertEqual(response.status_code,200)
        html = response.get_data(as_text=True)
        preparation = re.search(r'<form[^>]*action="/caixa/cierre/revisar"[^>]*>(.*?)</form>',html,re.S)
        if preparation:
            return re.search(r'name="envio" value="([^"]+)"',preparation.group(1)).group(1)
        return fixtures.CajaVentaIntegrationTests.token(self,response)

    def draft(self,day=None,count=None):
        state = self.db.consultar_caixa(day or self.day)[0]
        return {'data':state['data'].isoformat(),'conferencia':state['conferencia'],
            'contado':count,'chave':str(uuid4())}

    def receive(self,cash='5',ticket=None):
        draft = self.receipt_draft(ticket)
        draft['efectivo'] = cash
        return self.db.receber_ticket(draft,self.users[0])

    def close(self,draft=None,user=None):
        return self.db.fechar_caixa(draft or self.draft(),user or self.users[0])

    def sql_close(self,c,draft,user=None):
        c.execute('SELECT public.fn_fechar_caixa(%s,%s,%s::jsonb,%s,%s::uuid)',
            (draft['data'],user or self.users[0],draft['conferencia'],draft['contado'],draft['chave']))
        return c.fetchone()[0]

    def test_consulta_is_read_only_absent_fund_does_not_block_sales(self):
        for _ in range(2):
            page = self.client.get('/caixa/consulta')
            self.assertEqual(page.status_code,200)
            self.assertIn(b'Sin informar',page.data)
            self.assertNotIn(b'name="envio"',page.data)
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],0)
        self.receive()
        state,closed,history = self.db.consultar_caixa()
        self.assertEqual((state['total_vendido'],state['efectivo_vendas'],state['valor_otro']),
            (Decimal(20),Decimal(5),Decimal(15)))
        self.assertIsNone(state['fundo_inicial'])
        self.assertIsNone(state['efectivo_segun_fondo_vendas'])
        self.assertIsNone(closed)
        with self.assertRaises(self.pg.Error):
            self.close()
        self.fund('0')
        self.assertEqual(self.db.consultar_caixa()[0]['efectivo_segun_fondo_vendas'],Decimal(5))

    def test_fund_history_idempotency_no_carry_and_closed_snapshot_preserved(self):
        self.fund('500',day=self.day-timedelta(days=1))
        self.assertIsNone(self.db.consultar_caixa()[0]['fundo_id'])
        key = str(uuid4())
        first = self.fund('100',key=key)
        self.assertEqual(first,self.fund('100',key=key))
        with self.assertRaises(self.pg.Error):
            self.fund('101',key=key)
        self.close()
        before = self.query('SELECT * FROM public.fechamentos_caixa')
        self.fund('200',user=self.users[1])
        state,closed,history = self.db.consultar_caixa()
        self.assertEqual(state['fundo_inicial'],Decimal(200))
        self.assertEqual(closed['fundo_inicial'],Decimal(100))
        self.assertEqual(self.query('SELECT * FROM public.fechamentos_caixa'),before)
        self.assertEqual([f['valor'] for f in history],[Decimal(200),Decimal(100)])
        self.assertEqual(history[0]['registrado_por'],self.users[1])
        self.assertGreaterEqual(history[0]['registrado_em'],history[1]['registrado_em'])
        for value in ('-1','NaN','Infinity','1.001'):
            with self.assertRaises(self.pg.Error):
                self.fund(value)

    def test_optional_count_null_zero_positive_negative_and_exact_match(self):
        self.fund('100')
        self.receive()
        # Cada fecha de prueba tiene su propio fondo; la fecha actual queda sin cerrar hasta el último caso.
        for offset,count,expected in ((-4,None,None),(-3,'0',Decimal(-100)),
                                      (-2,'110',Decimal(10)),(-1,'100',Decimal(0))):
            day = self.day+timedelta(days=offset)
            self.fund(day=day)
            self.close(self.draft(day,count))
            self.assertEqual(self.query('SELECT divergencia FROM public.fechamentos_caixa WHERE data_referencia=%s',
                (day,))[0][0],expected)
        self.close(self.draft(count='103.25'))
        self.assertEqual(self.query('SELECT valor_contado,divergencia FROM public.fechamentos_caixa '
            'WHERE data_referencia=%s',(self.day,)),[(Decimal('103.25'),Decimal('-1.75'))])

    def test_cierre_atomic_idempotent_unique_and_does_not_change_other_records(self):
        self.fund()
        paid = self.receipt_draft()
        self.db.receber_ticket(paid,self.users[0])
        physical = self.physical()
        sales = self.query('SELECT * FROM public.vendas')
        tickets = self.query('SELECT * FROM public.tickets')
        draft = self.draft()
        first = self.close(draft)
        self.assertEqual(self.close(draft,user=self.users[1]),first)
        for changed in ({**draft,'chave':str(uuid4())},{**draft,'contado':'0'}):
            with self.assertRaises(self.pg.Error):
                self.close(changed)
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],1)
        self.assertEqual(self.physical(),physical)
        self.assertEqual(self.query('SELECT * FROM public.vendas'),sales)
        self.assertEqual(self.query('SELECT * FROM public.tickets'),tickets)
        self.assertEqual(self.db.receber_ticket(paid,self.users[1])['valor_total'],Decimal(20))
        other = self.db.iniciar_ticket(str(uuid4()),self.users[1])
        self.cut(ticket=other)
        with self.assertRaises(self.pg.Error):
            self.receive(ticket=other)
        self.assertNotIn(b'name="efectivo"',self.client.get(f'/caixa/tickets/{other}').data)

    def test_stale_fund_same_value_revision_and_same_total_sale_require_review(self):
        self.fund()
        draft = self.draft(count='100')
        self.fund('100',user=self.users[1])
        with self.assertRaises(self.pg.Error):
            self.close(draft)
        with self.assertRaises(ValueError):
            self.db.preparar_cierre(draft,'100')
        draft = self.draft()
        self.query('UPDATE public.produtos SET preco_unitario=0 WHERE id=%s',(self.product,))
        other = self.db.iniciar_ticket(str(uuid4()),self.users[1])
        self.cut(ticket=other)
        self.receive('0',other)
        self.assertEqual(self.db.consultar_caixa()[0]['total_vendido'],Decimal(0))
        with self.assertRaises(self.pg.Error):
            self.close(draft)
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],0)

    def test_date_is_receipt_date_cordoba_pending_old_tickets_and_three_compositions(self):
        self.query("UPDATE public.tickets SET criado_em=criado_em-interval '2 days'")
        self.query("UPDATE public.itens_ticket SET cortado_em=cortado_em-interval '2 days'")
        self.receive('20')
        self.assertEqual(self.db.consultar_caixa()[0]['total_vendido'],Decimal(20))
        self.assertEqual(self.db.consultar_caixa(self.day-timedelta(days=2))[0]['total_vendido'],Decimal(0))
        for cash in ('0','5'):
            ticket = self.db.iniciar_ticket(str(uuid4()),self.users[1])
            self.cut('2','1',ticket=ticket)
            self.receive(cash,ticket)
        pending = self.db.iniciar_ticket(str(uuid4()),self.users[1])
        self.cut('99','1',ticket=pending)
        state = self.db.consultar_caixa()[0]
        self.assertEqual((state['total_vendido'],state['efectivo_vendas'],state['valor_otro']),
            (Decimal(60),Decimal(25),Decimal(35)))
        self.query("UPDATE public.vendas SET recebido_em=(%s::date+interval '2 hours') AT TIME ZONE 'UTC' WHERE ticket_id=%s",
            (self.day,self.ticket))
        self.assertEqual(self.db.consultar_caixa()[0]['total_vendido'],Decimal(40))
        self.assertEqual(self.db.consultar_caixa(self.day-timedelta(days=1))[0]['total_vendido'],Decimal(20))

    def test_concurrent_receipt_then_close_waits_and_rejects_old_movement(self):
        self.fund()
        draft = self.draft()
        receipt = self.receipt_draft()
        self.assertIsNone(self.run_pair(lambda c:self.sql_receive(c,receipt),lambda c:self.sql_close(c,draft)))
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],0)
        self.close()
        self.assertEqual(self.query('SELECT total_vendido FROM public.fechamentos_caixa')[0][0],Decimal(20))

    def test_concurrent_close_then_receipt_blocks_without_partial_sale(self):
        self.fund()
        draft = self.draft()
        receipt = self.receipt_draft()
        physical = self.physical()
        self.assertIsNone(self.run_pair(lambda c:self.sql_close(c,draft),lambda c:self.sql_receive(c,receipt)))
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas')[0][0],0)
        self.assertEqual(self.query('SELECT status FROM public.tickets')[0][0],'pendente')
        self.assertEqual(self.physical(),physical)

    def test_concurrent_same_closure_and_different_closures_do_not_duplicate(self):
        self.fund()
        draft = self.draft()
        result = self.run_pair(lambda c:self.sql_close(c,draft),lambda c:self.sql_close(c,draft,self.users[1]))
        self.assertEqual(result,self.query('SELECT id FROM public.fechamentos_caixa')[0][0])
        yesterday = self.day-timedelta(days=1)
        self.fund(day=yesterday)
        a,b = self.draft(yesterday),self.draft(yesterday)
        self.assertIsNone(self.run_pair(lambda c:self.sql_close(c,a),lambda c:self.sql_close(c,b)))
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa WHERE data_referencia=%s',
            (yesterday,))[0][0],1)

    def test_fund_correction_and_close_share_same_day_lock(self):
        self.fund()
        draft = self.draft()
        def correction(c):
            c.execute('SELECT public.fn_registrar_fundo(%s,101,%s,%s::uuid)',(self.day,self.users[1],str(uuid4())))
        self.assertIsNone(self.run_pair(correction,lambda c:self.sql_close(c,draft)))
        self.close()
        self.assertEqual(self.query('SELECT fundo_inicial FROM public.fechamentos_caixa')[0][0],Decimal(101))

    def test_permissions_inactive_user_and_invalid_count_leave_no_closure(self):
        self.fund()
        for count in ('-1','NaN','Infinity','0.001','1000000000000'):
            with self.assertRaises(self.pg.Error):
                self.close(self.draft(count=count))
        for sql in ('DELETE FROM public.fundos_caixa','UPDATE public.fundos_caixa SET valor=1',
                    'DELETE FROM public.fechamentos_caixa','UPDATE public.fechamentos_caixa SET total_vendido=1'):
            with self.assertRaises(self.pg.errors.InsufficientPrivilege):
                self.db.fetchall(sql)
        self.query('UPDATE public.usuarios SET ativo=false WHERE id=%s',(self.users[1],))
        with self.assertRaises(self.pg.Error):
            self.close(user=self.users[1])
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],0)
        self.assertIsNone(self.query("SELECT to_regprocedure('public.fn_fechar_caixa(date,bigint,numeric,text)')")[0][0])

    def test_post_insert_failure_rolls_back_and_lost_response_is_safe(self):
        self.fund()
        draft = self.draft()
        self.query('''CREATE FUNCTION public.fail_close_fixture() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'fixture'; END $$''')
        self.query('CREATE TRIGGER fail_close_fixture AFTER INSERT ON public.fechamentos_caixa '
            'FOR EACH ROW EXECUTE FUNCTION public.fail_close_fixture()')
        with self.assertRaises(self.pg.Error):
            self.close(draft)
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],0)
        self.query('DROP TRIGGER fail_close_fixture ON public.fechamentos_caixa')
        self.unlock()
        preview = self.post(self.client,'/caixa/cierre/revisar',{
            'envio':self.token(self.client.get('/caixa/cierre')),'contado':''})
        token = self.token(preview)
        close = self.db.fechar_caixa
        def lost(d,user):
            close(d,user)
            raise self.pg.OperationalError('fixture')
        with patch.object(self.db,'fechar_caixa',side_effect=lost):
            self.assertEqual(self.post(self.client,'/caixa/cierre/confirmar',{
                'envio':token,'definitivo':'si'}).status_code,503)
        before = self.query('SELECT * FROM public.fechamentos_caixa')
        self.assertEqual(self.post(self.client,'/caixa/cierre/confirmar',{
            'envio':token,'definitivo':'si'}).status_code,302)
        self.assertEqual(self.query('SELECT * FROM public.fechamentos_caixa'),before)

    def test_web_flow_optional_count_history_completed_record_and_stale_review(self):
        self.unlock()
        form = self.client.get('/caixa/cierre')
        response = self.post(self.client,'/caixa/fondo',{'envio':self.token(form),'valor':'100,50'})
        self.assertEqual(response.status_code,302)
        self.receive()
        preparo = self.token(self.client.get('/caixa/cierre'))
        self.fund('101')
        stale = self.post(self.client,'/caixa/cierre/revisar',{'envio':preparo,'contado':'10'})
        self.assertEqual(stale.status_code,302)
        new = self.client.get(stale.location)
        self.assertNotIn(b'value="10"',new.data)
        response = self.post(self.client,'/caixa/cierre/revisar',{'envio':self.token(new),'contado':'104'})
        self.assertIn(b'-2',response.data)
        token = self.token(response)
        result = self.post(self.client,'/caixa/cierre/confirmar',{'envio':token,'definitivo':'si'})
        self.assertEqual(result.status_code,302)
        completed = self.unlock(self.login('Berta')).get(result.location)
        for word in ('Cierre confirmado','Ana','Diferencia','-2'):
            self.assertIn(word,completed.get_data(as_text=True))
        for forbidden in ('observaciones','justific','falta de dinero','sobrante','name="total_vendido"'):
            self.assertNotIn(forbidden,completed.get_data(as_text=True))
        self.assertIn(b'Sin reapertura',completed.data)
        self.assertEqual(self.client.get('/caixa/consulta').status_code,200)

    def test_es_ar_fund_count_and_cash_screens_keep_two_decimals(self):
        self.unlock()
        # El mismo parser corrige todos los formularios monetarios, sin confundir cantidades.
        initial=self.client.get('/caixa/cierre')
        fund_token=re.search(r'<form[^>]*action="/caixa/fondo"[^>]*>.*?name="envio" value="([^"]+)"',
            initial.get_data(as_text=True),re.S).group(1)
        result=self.post(self.client,'/caixa/fondo',{'envio':fund_token,'valor':'12.500'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(self.query('SELECT valor FROM fundos_caixa')[0][0],Decimal('12500'))
        current=self.client.get('/caixa/cierre')
        self.assertIn('12.500,00',current.get_data(as_text=True))
        review=self.post(self.client,'/caixa/cierre/revisar',{'envio':self.token(current),'contado':'12.500,50'})
        self.assertIn('Efectivo contado: <strong>12.500,50</strong>',review.get_data(as_text=True))
        self.assertIn('Diferencia: <strong>0,50</strong>',review.get_data(as_text=True))
        result=self.post(self.client,'/caixa/cierre/confirmar',{'envio':self.token(review),'definitivo':'si'})
        self.assertEqual(result.status_code,302)
        for path in (result.location,'/caixa/consulta'):
            self.assertIn('12.500,00',self.client.get(path).get_data(as_text=True))
        self.assertEqual(self.query('SELECT valor_contado,divergencia FROM fechamentos_caixa'),
            [(Decimal('12500.50'),Decimal('0.50'))])

    def test_web_csrf_purpose_signature_and_definitive_confirmation(self):
        self.fund()
        self.unlock()
        preparo = self.token(self.client.get('/caixa/cierre'))
        self.assertEqual(self.post(self.client,'/caixa/cierre/confirmar',{
            'envio':preparo,'definitivo':'si'}).status_code,400)
        token = self.token(self.post(self.client,'/caixa/cierre/revisar',{'envio':preparo,'contado':''}))
        self.assertEqual(self.post(self.client,'/caixa/cierre/confirmar',{'envio':token}).status_code,400)
        self.assertEqual(self.post(self.client,'/caixa/cierre/confirmar',{'envio':token+'x','definitivo':'si'}).status_code,400)
        self.assertEqual(self.client.post('/caixa/cierre/confirmar',data={'envio':token,'definitivo':'si'}).status_code,400)
        self.assertEqual(self.post(self.unlock(self.login('Berta')),'/caixa/cierre/confirmar',
            {'envio':token,'definitivo':'si'}).status_code,400)
        self.assertEqual(self.client.get('/caixa/cierre/no-fecha').status_code,404)
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa')[0][0],0)

    def test_roles_cajero_closes_without_pin_through_every_step(self):
        cajero = self.login('Cajero')
        self.assertNotIn(b'name="pin"',cajero.get('/caixa/cierre').data)
        form = cajero.get('/caixa/cierre')
        self.assertEqual(self.post(cajero,'/caixa/fondo',{'envio':self.token(form),'valor':'100'}).status_code,302)
        for route in ('/static/stock.css','/tickets','/caixa/consulta'):
            cajero.get(route).close()
        review = self.post(cajero,'/caixa/cierre/revisar',{'envio':self.token(cajero.get('/caixa/cierre')),'contado':''})
        self.assertEqual(review.status_code,200)
        self.assertEqual(review.headers['Cache-Control'],'no-store')
        from unittest.mock import MagicMock
        # Aviso de respaldo al cerrar: se llama una vez y una falla suya nunca afecta el Cierre.
        self.app.config['AL_CERRAR'] = hook = MagicMock(side_effect=RuntimeError('respaldo no disponible'))
        result = self.post(cajero,'/caixa/cierre/confirmar',{'envio':self.token(review),'definitivo':'si'})
        self.assertEqual(result.status_code,302)
        hook.assert_called_once_with()
        self.assertIn(b'Cierre confirmado',cajero.get(result.location).data)
        self.assertEqual(self.query('SELECT fechado_por FROM public.fechamentos_caixa'),[(self.roles['cajero'],)])
        # La corrección del Fondo sigue sin modificar el Cierre registrado.
        self.assertEqual(self.post(cajero,'/caixa/fondo',{'envio':self.token(cajero.get('/caixa/cierre')),'valor':'150'}).status_code,302)
        self.assertEqual(self.query('SELECT fundo_inicial FROM public.fechamentos_caixa'),[(Decimal(100),)])

    def test_roles_empleado_cannot_reach_caja_fondo_or_cierre_by_url_form_or_database(self):
        empleado = self.client.application.test_client()
        empleado.get('/login')
        self.assertEqual(self.post(empleado,'/login',{'login':'caja_Empleado','senha':'fixture-only'}).status_code,302)
        with empleado.session_transaction() as s:
            s['cierre_autorizado'] = True  # Un flag del cliente nunca concede acceso.
        for route in ('/caixa','/caixa/consulta','/caixa/cierre',f'/caixa/cierre/{self.day.isoformat()}',
                      f'/caixa/tickets/{self.ticket}'):
            with self.subTest(route=route):
                self.assertEqual(empleado.get(route).status_code,403)
        valid = self.token(self.client.get('/caixa/cierre'))
        with patch.object(self.db,'registrar_fundo') as fund, \
             patch.object(self.db,'preparar_cierre') as prepare, \
             patch.object(self.db,'fechar_caixa') as close, \
             patch.object(self.db,'receber_ticket') as receive:
            for route in ('/caixa/fondo','/caixa/cierre/revisar','/caixa/cierre/confirmar',
                          f'/caixa/tickets/{self.ticket}/recibir'):
                self.assertEqual(self.post(empleado,route,{'envio':valid,'valor':'999','definitivo':'si',
                    'integral':'si'}).status_code,403)
            for mock in (fund,prepare,close,receive):
                mock.assert_not_called()
        # Segunda barrera: las funciones del banco rechazan el rol aunque la aplicación fallara.
        user = self.roles['empleado']
        for attempt in (lambda: self.fund('100',user=user), lambda: self.close(user=user),
                        lambda: self.db.receber_ticket({**self.receipt_draft(),'efectivo':'5'},user)):
            with self.assertRaises(self.pg.Error) as denied:
                attempt()
            self.assertEqual(denied.exception.pgcode,'42501')
        self.assertEqual(self.query('SELECT count(*) FROM public.fundos_caixa'),[(0,)])
        self.assertEqual(self.query('SELECT count(*) FROM public.fechamentos_caixa'),[(0,)])
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas'),[(0,)])

    def test_roles_logout_and_inactive_account_lose_access(self):
        cajero = self.login('Cajero')
        cookie = cajero.get_cookie('session').value
        self.assertEqual(cajero.get('/caixa/cierre').status_code,200)
        self.query("UPDATE public.usuarios SET ativo=false WHERE login='caja_Cajero'")
        self.assertEqual(cajero.get('/caixa/cierre').status_code,302)
        self.query("UPDATE public.usuarios SET ativo=true,perfil='empleado' WHERE login='caja_Cajero'")
        cajero.set_cookie('session',cookie)
        # El rol se lee del banco en cada pedido: la cookie anterior no conserva el permiso.
        self.assertEqual(cajero.get('/caixa/cierre').status_code,403)

    def test_new_operational_date_receives_without_carrying_yesterday_fund(self):
        self.fund(day=self.day-timedelta(days=1))
        self.close(self.draft(self.day-timedelta(days=1)))
        self.receive()
        self.assertIsNone(self.db.consultar_caixa()[0]['fundo_id'])
        self.assertEqual(self.db.consultar_caixa()[0]['total_vendido'],Decimal(20))


if __name__=='__main__':
    unittest.main()
