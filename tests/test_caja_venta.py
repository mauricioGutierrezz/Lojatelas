"""1C: recepción integral con PostgreSQL real, sesiones HTTP y carreras con locks."""
import os
import re
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4


@unittest.skipUnless(os.getenv('LOJA_TEST_DB')=='1','Requiere el cluster descartable del runner')
class CajaVentaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from app_loja import db
        from app_loja.run import create_app
        cls.pg = psycopg2
        cls.admin_config = dict(host=os.environ['PGHOST'],port=os.environ['PGPORT'],
            dbname=os.environ['PGDATABASE'],user=os.environ['PGUSER'])
        cls.operator_config = {**cls.admin_config,'user':'loja_test_caja'}
        conn = psycopg2.connect(**cls.admin_config)
        try:
            with conn,conn.cursor() as c:
                c.execute('CREATE ROLE loja_test_caja LOGIN')
                c.execute('GRANT loja_operador TO loja_test_caja')
                cls.users = []
                for name,profile in (('Ana','admin'),('Berta','admin'),('Admin','admin')):
                    c.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES"
                        "(%s,%s,public.crypt('fixture-only',public.gen_salt('bf')),%s) RETURNING id",
                        (name,'caja_'+name,profile))
                    cls.users.append(c.fetchone()[0])
        finally:
            conn.close()
        cls.db = db
        cls.original = db.DB_CONFIG
        db.DB_CONFIG = cls.operator_config
        cls.app = create_app({'TESTING':True,'SECRET_KEY':'fixture-1c-only'})

    @classmethod
    def tearDownClass(cls):
        cls.db.DB_CONFIG = cls.original

    def query(self,sql,args=()):
        conn = self.pg.connect(**self.admin_config)
        try:
            with conn,conn.cursor() as c:
                c.execute(sql,args)
                return c.fetchall() if c.description else None
        finally:
            conn.close()

    def post(self,client,path,data):
        with client.session_transaction() as s:
            data = {**data,'csrf':s['csrf']}
        return client.post(path,data=data)

    def login(self,name='Ana'):
        client = self.app.test_client()
        client.get('/login')
        self.assertEqual(self.post(client,'/login',{'login':'caja_'+name,'senha':'fixture-only'}).status_code,302)
        client.get('/caixa')
        return client

    def setUp(self):
        self.client = self.login()
        self.ticket = self.db.iniciar_ticket(str(uuid4()),self.users[0])
        self.product = self.db.cadastrar_produto({'tipo_id':1,'nome':'Lino '+str(uuid4()),
            'unidade':'m','preco':Decimal('12.50'),'largura':None,'padrao':None},self.users[0])
        self.db.confirmar_ingresso(str(uuid4()),[
            {'produto_id':self.product,'rolos':2,'quantidade':'30'}],self.users[0])
        self.lots = [r[0] for r in self.query('SELECT id FROM public.estoque_lotes '
            'WHERE produto_id=%s ORDER BY id',(self.product,))]
        self.cut('2.5','7.125',allocations=[{'lote_id':self.lots[0],'quantidade':'3'},
            {'lote_id':self.lots[1],'quantidade':'4.125'}])

    def cut(self,sold='1',cut='1',ticket=None,product=None,allocations=None,user=None):
        return self.db.registrar_corte({'ticket_id':ticket or self.ticket,
            'produto_id':product or self.product,'quantidade_vendida':sold,'quantidade_cortada':cut,
            'chave':str(uuid4()),'alocacoes':allocations if allocations is not None else [{'lote_id':self.lots[0],'quantidade':cut}]},
            user or self.users[0])

    def draft(self,ticket=None):
        tid = ticket or self.ticket
        return {'ticket_id':tid,'conferencia':self.db.conferir_ticket(tid)[0]['conferencia'],'efectivo':'10'}

    def review(self,client=None,ticket=None):
        return (client or self.client).get(f'/caixa/tickets/{ticket or self.ticket}')

    def token(self,response):
        self.assertEqual(response.status_code,200)
        if response.is_json:
            return response.get_json()['envio']
        return re.search(r'name="envio" value="([^"]+)"',response.get_data(as_text=True)).group(1)

    def prepare(self,client=None,ticket=None,efectivo='10',modo='entregado'):
        client = client or self.client
        tid = ticket or self.ticket
        initial = self.token(self.review(client,tid))
        return self.post(client,f'/caixa/tickets/{tid}/composicion',
            {'envio':initial,'entregado':efectivo,'modo':modo})

    def receive(self,token,client=None,ticket=None):
        return self.post(client or self.client,f'/caixa/tickets/{ticket or self.ticket}/recibir',
            {'envio':token,'integral':'si'})

    def physical(self):
        return (self.query('SELECT * FROM public.estoque_lotes WHERE produto_id=%s ORDER BY id',(self.product,)),
            self.query('SELECT * FROM public.movimentacoes WHERE produto_id=%s ORDER BY id',(self.product,)),
            self.query('SELECT * FROM public.itens_ticket WHERE ticket_id=%s ORDER BY id',(self.ticket,)))

    def test_complete_flow_frozen_sold_value_multilote_other_operator_and_new_session(self):
        self.cut('1.125','2',user=self.users[1])
        original = self.physical()
        created = self.query('SELECT criado_em FROM public.tickets WHERE id=%s',(self.ticket,))[0][0]
        self.query('UPDATE public.produtos SET preco_unitario=99 WHERE id=%s',(self.product,))
        berta = self.login('Berta')
        code = self.query('SELECT codigo FROM public.tickets WHERE id=%s',(self.ticket,))[0][0]
        found = berta.get('/caixa',query_string={'codigo':' '+code.lower()+' '})
        self.assertEqual(found.location,f'/caixa/tickets/{self.ticket}')
        review = berta.get(found.location)
        for text in (code,'Cantidad vendida: 2,5','Cantidad cortada: 7,125','12,5','45,31','Ana','Berta'):
            self.assertIn(text,review.get_data(as_text=True))
        token = self.token(self.prepare(berta))
        first = self.receive(token,berta)
        repeated = self.receive(token,berta)
        self.assertEqual(first.status_code,302)
        self.assertEqual(first.location,repeated.location)
        sale = self.query('SELECT valor_total,metodo_pagamento,recebido_por,recebido_em FROM public.vendas '
            'WHERE ticket_id=%s',(self.ticket,))[0]
        self.assertEqual(sale[:3],(Decimal('45.31'),None,self.users[1]))
        self.assertGreaterEqual(sale[3],created)
        self.assertEqual(self.query('SELECT criado_em,status FROM public.tickets WHERE id=%s',
            (self.ticket,)),[(created,'pago')])
        self.assertEqual(self.physical(),original)
        summary = self.review(self.login()).get_data(as_text=True)
        for text in ('Venta concluida','Pagado','45,31','Recibido por Berta',code):
            self.assertIn(text,summary)
        self.assertEqual(self.query('SELECT valor_efectivo,valor_otro FROM public.vendas WHERE ticket_id=%s',
            (self.ticket,)),[(Decimal(10),Decimal('35.31'))])
        self.assertNotIn('name="integral"',summary)
        self.assertEqual(self.client.get(f'/tickets/{self.ticket}/productos').status_code,400)
        self.assertEqual(self.query('SELECT count(*) FROM public.vw_reconciliacao_estoque WHERE diferenca<>0')[0][0],0)

    def test_empty_ticket_invalid_conference_and_no_other_modes(self):
        empty = self.db.iniciar_ticket(str(uuid4()),self.users[0])
        self.assertNotIn(b'name="integral"',self.review(ticket=empty).data)
        for draft in (self.draft(empty),{**self.draft(),'conferencia':None},
                      {**self.draft(),'conferencia':'{}'},
                      {**self.draft(),'conferencia':'[{"valor_total":0}]'}):
            with self.subTest(draft=draft),self.assertRaises(self.pg.Error):
                self.db.receber_ticket(draft,self.users[0])
        for response in (self.client.get('/caixa'),self.review()):
            text = response.get_data(as_text=True).lower()
            for forbidden in ('forma de pago','transferencia','troco','descuento','name="valor_total"','name="otro"'):
                self.assertNotIn(forbidden,text)
        self.assertIn(b'No encontramos',self.client.get('/caixa?codigo=inexistente').data)
        self.assertEqual(self.review(ticket=999999999).status_code,404)
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id IN (%s,%s)',
            (empty,self.ticket))[0][0],0)

    def test_stale_conference_rejected_even_when_total_unchanged(self):
        token = self.token(self.prepare())
        original = self.draft()
        other = self.db.cadastrar_produto({'tipo_id':1,'nome':'Otro '+str(uuid4()),'unidade':'un',
            'preco':Decimal(0),'largura':None,'padrao':None},self.users[0])
        self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':other,'quantidade':'2'}],self.users[0])
        self.cut(product=other,allocations=[])
        self.assertEqual(self.db.conferir_ticket(self.ticket)[0]['total'],Decimal('31.25'))
        response = self.receive(token)
        self.assertEqual(response.status_code,409)
        self.assertIn('Volvé a revisar',response.get_data(as_text=True))
        with self.assertRaises(self.pg.Error):
            self.db.receber_ticket(original,self.users[0])
        self.assertEqual(self.query('SELECT status FROM public.tickets WHERE id=%s',(self.ticket,)),[('pendente',)])
        self.assertEqual(self.receive(self.token(self.prepare())).status_code,302)

    def test_authorization_idempotency_and_permissions(self):
        draft = self.draft()
        first = self.db.receber_ticket(draft,self.users[2])
        second = self.db.receber_ticket(draft,self.users[1])
        self.assertEqual(first,second)
        self.assertEqual(self.query('SELECT recebido_por,metodo_pagamento FROM public.vendas '
            'WHERE ticket_id=%s',(self.ticket,)),[(self.users[2],None)])
        with self.assertRaises(self.pg.Error):
            self.db.receber_ticket({**draft,'conferencia':'[]'},self.users[0])
        for sql in ('INSERT INTO public.vendas(ticket_id,recebido_por,valor_total,conferencia) VALUES (1,1,0,\'[]\')',
                    'UPDATE public.vendas SET valor_total=0','DELETE FROM public.vendas'):
            with self.subTest(sql=sql),self.assertRaises(self.pg.errors.InsufficientPrivilege):
                self.db.fetchall(sql)
        self.query('UPDATE public.usuarios SET ativo=false WHERE id=%s',(self.users[1],))
        try:
            with self.assertRaises(self.pg.Error):
                self.db.receber_ticket(draft,self.users[1])
        finally:
            self.query('UPDATE public.usuarios SET ativo=true WHERE id=%s',(self.users[1],))
        self.assertIsNone(self.query("SELECT to_regprocedure('public.fn_finalizar_venda(bigint,bigint,text)')")[0][0])
        self.assertIsNone(self.query("SELECT to_regprocedure('public.fn_finalizar_venda(bigint,bigint,jsonb)')")[0][0])

    def test_cash_other_and_mixed_compositions_bank_preview_and_persistence(self):
        for index,cash in enumerate(('0','31.25','10.10')):
            with self.subTest(cash=cash):
                ticket = self.ticket if index==0 else self.db.iniciar_ticket(str(uuid4()),self.users[0])
                if index:
                    self.cut('2.5','1',ticket=ticket)
                physical = self.query('SELECT quantidade_atual FROM public.estoque_lotes '
                    'WHERE produto_id=%s ORDER BY id',(self.product,))
                preview = self.prepare(ticket=ticket,efectivo=cash.replace('.',','))
                self.assertEqual(preview.status_code,200)
                html = preview.get_data(as_text=True)
                for forbidden in ('name="valor_total"','name="otro"','name="efectivo"'):
                    self.assertNotIn(forbidden,html)
                # La confirmación usa la composición firmada; otros campos no son fuente de verdad.
                result = self.post(self.client,f'/caixa/tickets/{ticket}/recibir',{
                    'envio':self.token(preview),'integral':'si','valor_total':'0','otro':'999',
                    'efectivo':'999','dinheiro_entregue':'999'})
                self.assertEqual(result.status_code,302)
                sale = self.query('SELECT valor_total,valor_efectivo,valor_otro FROM public.vendas '
                    'WHERE ticket_id=%s',(ticket,))[0]
                self.assertEqual(sale,(Decimal('31.25'),Decimal(cash),Decimal('31.25')-Decimal(cash)))
                self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes '
                    'WHERE produto_id=%s ORDER BY id',(self.product,)),physical)
                completed = self.review(self.login('Berta'),ticket).get_data(as_text=True)
                self.assertIn('Efectivo:',completed)
                self.assertIn('Otro:',completed)
                self.assertNotIn('name="efectivo"',completed)

    def test_invalid_cash_rejected_by_bank_and_form_without_partial_effects(self):
        draft = self.draft()
        physical = self.physical()
        for value in (None,'-0.01','31.26','32','NaN','Infinity','-Infinity','1.001','1000000000000'):
            with self.subTest(value=value),self.assertRaises(self.pg.Error):
                self.db.receber_ticket({**draft,'efectivo':value},self.users[0])
            with self.subTest(preview=value),self.assertRaises(self.pg.Error):
                self.db.composicao_recebimento(draft,value)
        for value in (None,'','-0.01','NaN','Infinity','-Infinity','1,001','1000000000000'):
            with self.subTest(entregado=value):
                response = self.prepare(efectivo=value)
                self.assertEqual(response.status_code,400)
                self.assertTrue(response.is_json)
                self.assertIn('error',response.get_json())
                self.assertNotIn('envio',response.get_json())
        initial = self.token(self.review())
        self.assertEqual(self.post(self.client,f'/caixa/tickets/{self.ticket}/composicion',
            {'envio':initial}).status_code,400)
        self.assertEqual(self.receive(initial).status_code,400)
        self.assertEqual(self.physical(),physical)
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id=%s',(self.ticket,))[0][0],0)

    def test_delivered_cash_and_shortcuts_only_persist_applied_composition(self):
        product = self.db.cadastrar_produto({'tipo_id':1,'nome':'UX '+str(uuid4()),'unidade':'un',
            'preco':Decimal('25501.50'),'largura':None,'padrao':None},self.users[0])
        self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':product,'quantidade':'10'}],self.users[0])
        cases = [('10.000','entregado','10000.00','15501.50'),
                 ('25.501,50','entregado','25501.50','0.00'),
                 ('30.000','entregado','25501.50','0.00'),
                 ('','otro','0.00','25501.50'),('','efectivo','25501.50','0.00')]
        for delivered,mode,cash,other in cases:
            with self.subTest(delivered=delivered,mode=mode):
                ticket = self.db.iniciar_ticket(str(uuid4()),self.users[0])
                self.cut(ticket=ticket,product=product,allocations=[])
                original = self.query('SELECT * FROM public.movimentacoes WHERE produto_id=%s ORDER BY id',(product,))
                preview = self.prepare(ticket=ticket,efectivo=delivered,modo=mode)
                self.assertEqual(preview.status_code,200)
                data = preview.get_json()
                self.assertEqual((Decimal(data['total']),Decimal(data['efectivo']),Decimal(data['otro'])),
                    (Decimal('25501.50'),Decimal(cash),Decimal(other)))
                self.assertEqual(set(data),{'total','efectivo','otro','envio'})
                self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id=%s',(ticket,)),[(0,)])
                from itsdangerous import URLSafeSerializer
                signed = URLSafeSerializer(self.app.secret_key,salt='corte-ticket-1b-recebimento').loads(data['envio'])
                self.assertEqual(set(signed),{'ticket_id','codigo','usuario_id','conferencia','efectivo'})
                self.assertEqual(Decimal(signed['efectivo']),Decimal(cash))
                self.assertEqual(self.receive(data['envio'],ticket=ticket).status_code,302)
                self.assertEqual(self.query('SELECT valor_total,valor_efectivo,valor_otro FROM public.vendas '
                    'WHERE ticket_id=%s',(ticket,)),[(Decimal('25501.50'),Decimal(cash),Decimal(other))])
                self.assertEqual(self.query('SELECT * FROM public.movimentacoes WHERE produto_id=%s ORDER BY id',
                    (product,)),original)
                completed = self.review(ticket=ticket).get_data(as_text=True)
                self.assertNotIn('Efectivo entregado',completed)
                self.assertNotIn('Vuelto',completed)

    def test_same_page_and_preparation_reject_stale_or_arbitrary_values(self):
        initial = self.token(self.review())
        html = self.review().get_data(as_text=True)
        for text in ('Efectivo entregado','Todo en efectivo','Todo en Otro',
                     'Cobro completo recibido','Confirmar cobro','id="confirmar-cobro" disabled'):
            self.assertIn(text,html)
        self.assertNotIn('Revisá la composición',html)
        self.assertNotIn('venta_composicion.html',self.app.jinja_env.list_templates())
        path = f'/caixa/tickets/{self.ticket}/composicion'
        preview = self.post(self.client,path,{'envio':initial,'entregado':'40',
            'total':'1','efectivo':'40','otro':'999','vuelto':'999'})
        self.assertEqual((preview.json['total'],preview.json['efectivo'],preview.json['otro']),
            ('31.25','31.25','0.00'))
        self.assertEqual(self.post(self.client,path,{'envio':initial,'modo':'inventado'}).status_code,400)
        self.cut()
        stale = self.post(self.client,path,{'envio':initial,'entregado':'40'})
        self.assertEqual(stale.status_code,409)
        self.assertTrue(stale.json['revisar'])
        self.assertNotIn('envio',stale.json)
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id=%s',(self.ticket,)),[(0,)])

    def test_changed_composition_replay_and_concurrent_receipt_cannot_overwrite_sale(self):
        first = self.draft()
        different = {**first,'efectivo':'11'}
        physical = self.physical()
        original_time = self.query('SELECT criado_em FROM public.tickets WHERE id=%s',(self.ticket,))[0][0]
        self.assertIsNone(self.run_pair(lambda c:self.sql_receive(c,first),
            lambda c:self.sql_receive(c,different,self.users[1])))
        sale = self.query('SELECT valor_efectivo,valor_otro,recebido_por,recebido_em FROM public.vendas '
            'WHERE ticket_id=%s',(self.ticket,))
        self.assertEqual(sale[0][:3],(Decimal(10),Decimal('21.25'),self.users[0]))
        with self.assertRaises(self.pg.Error):
            self.db.receber_ticket(different,self.users[1])
        self.db.receber_ticket(first,self.users[1])
        self.assertEqual(self.query('SELECT valor_efectivo,valor_otro,recebido_por,recebido_em FROM public.vendas '
            'WHERE ticket_id=%s',(self.ticket,)),sale)
        self.assertEqual(self.query('SELECT criado_em FROM public.tickets WHERE id=%s',(self.ticket,))[0][0],original_time)
        self.assertEqual(self.physical(),physical)

    def test_zero_value_ticket_has_zero_cash_and_zero_other(self):
        product = self.db.cadastrar_produto({'tipo_id':1,'nome':'Sin cargo '+str(uuid4()),'unidade':'un',
            'preco':Decimal(0),'largura':None,'padrao':None},self.users[0])
        self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':product,'quantidade':'1'}],self.users[0])
        ticket = self.db.iniciar_ticket(str(uuid4()),self.users[0])
        self.cut(product=product,ticket=ticket,allocations=[])
        self.assertEqual(self.receive(self.token(self.prepare(ticket=ticket,efectivo='0')),ticket=ticket).status_code,302)
        self.assertEqual(self.query('SELECT valor_total,valor_efectivo,valor_otro FROM public.vendas '
            'WHERE ticket_id=%s',(ticket,)),[(Decimal(0),Decimal(0),Decimal(0))])

    def test_tampering_csrf_identity_and_confirmation_required(self):
        token = self.token(self.prepare())
        for value in (token+'x','invalid'):
            self.assertEqual(self.receive(value).status_code,400)
        self.assertEqual(self.receive(token,self.login('Berta')).status_code,400)
        self.assertEqual(self.receive(token,ticket=self.ticket+999999).status_code,400)
        self.assertEqual(self.post(self.client,f'/caixa/tickets/{self.ticket}/recibir',{'envio':token}).status_code,400)
        self.assertEqual(self.client.post(f'/caixa/tickets/{self.ticket}/recibir',
            data={'envio':token,'integral':'si'}).status_code,400)
        self.assertEqual(self.post(self.client,'/tickets/nuevo',{'envio':token}).status_code,400)
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id=%s',(self.ticket,))[0][0],0)
        for route in ('/conteo','/fechar','/admin','/cancelar','/imprimir'):
            self.assertEqual(self.client.get(route).status_code,404)

    def test_post_insert_failure_is_atomic_and_retry_safe(self):
        draft = self.draft()
        physical = self.physical()
        self.query('''CREATE FUNCTION public.fail_1c_fixture() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.id=%s AND NEW.status='pago' THEN RAISE EXCEPTION 'fixture';
            END IF; RETURN NEW; END $$''',(self.ticket,))
        self.query('CREATE TRIGGER fail_1c_fixture BEFORE UPDATE ON public.tickets '
            'FOR EACH ROW EXECUTE FUNCTION public.fail_1c_fixture()')
        try:
            with self.assertRaises(self.pg.Error):
                self.db.receber_ticket(draft,self.users[0])
            self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id=%s',(self.ticket,))[0][0],0)
            self.assertEqual(self.query('SELECT status FROM public.tickets WHERE id=%s',(self.ticket,)),[('pendente',)])
            self.assertEqual(self.physical(),physical)
        finally:
            self.query('DROP TRIGGER fail_1c_fixture ON public.tickets')
            self.query('DROP FUNCTION public.fail_1c_fixture()')
        first = self.db.receber_ticket(draft,self.users[0])
        self.assertEqual(self.db.receber_ticket(draft,self.users[0]),first)

    def test_lost_response_after_commit_retries_same_receipt(self):
        token = self.token(self.prepare())
        receive = self.db.receber_ticket
        def lost_response(draft,user):
            receive(draft,user)
            raise self.pg.OperationalError('fixture lost response')
        with patch.object(self.db,'receber_ticket',side_effect=lost_response):
            failed = self.receive(token)
        self.assertEqual(failed.status_code,503)
        self.assertIn(token,failed.get_data(as_text=True))
        before = self.query('SELECT id,recebido_por,recebido_em FROM public.vendas WHERE ticket_id=%s',(self.ticket,))
        self.assertEqual(self.receive(token).status_code,302)
        self.assertEqual(self.query('SELECT id,recebido_por,recebido_em FROM public.vendas WHERE ticket_id=%s',
            (self.ticket,)),before)

    def run_pair(self,first,second):
        a = self.pg.connect(**self.operator_config)
        b = self.pg.connect(**self.operator_config)
        try:
            with a.cursor() as c:
                c.execute('SET ROLE loja_operador')
                first(c)
            def perform_second():
                with b,b.cursor() as c:
                    c.execute('SET ROLE loja_operador')
                    c.execute("SET LOCAL statement_timeout='8s'")
                    return second(c)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(perform_second)
                waited = False
                for _ in range(100):
                    state = self.query('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',
                        (b.get_backend_pid(),))
                    if state and state[0][0]=='Lock':
                        waited = True
                        break
                    time.sleep(.02)
                a.commit()
                self.assertTrue(waited,'La segunda operación debe esperar un lock real.')
                try:
                    return future.result(timeout=10)
                except self.pg.Error:
                    return None
        finally:
            a.close()
            b.close()

    def sql_receive(self,cursor,draft,user=None):
        cursor.execute('SELECT * FROM public.fn_finalizar_venda(%s,%s,%s::jsonb,%s)',
            (draft['ticket_id'],user or self.users[0],draft['conferencia'],draft['efectivo']))
        return cursor.fetchone()

    def sql_cut(self,cursor):
        cursor.execute('SELECT public.fn_adicionar_item_corte(%s,%s,1,2,%s::jsonb,%s,%s::uuid)',
            (self.ticket,self.product,'[{"lote_id":'+str(self.lots[0])+',"quantidade":2}]',
             self.users[1],str(uuid4())))
        return cursor.fetchone()

    def test_concurrent_receipts_by_different_operators_are_one_sale(self):
        draft = self.draft()
        physical = self.physical()
        result = self.run_pair(lambda c:self.sql_receive(c,draft),
            lambda c:self.sql_receive(c,draft,self.users[1]))
        self.assertIsNotNone(result)
        self.assertEqual(self.query('SELECT id,valor_total,recebido_por FROM public.vendas WHERE ticket_id=%s',
            (self.ticket,)),[(result[0],result[1],self.users[0])])
        self.assertEqual(self.physical(),physical)

    def test_concurrent_cut_then_receipt_rejects_stale_contents(self):
        draft = self.draft()
        self.assertIsNone(self.run_pair(self.sql_cut,lambda c:self.sql_receive(c,draft)))
        self.assertEqual(self.query('SELECT status FROM public.tickets WHERE id=%s',(self.ticket,)),[('pendente',)])
        self.assertEqual(self.query('SELECT count(*) FROM public.vendas WHERE ticket_id=%s',(self.ticket,))[0][0],0)
        sale = self.db.receber_ticket(self.draft(),self.users[0])
        self.assertEqual(sale['valor_total'],Decimal('43.75'))

    def test_concurrent_receipt_then_cut_preserves_physical_history(self):
        draft = self.draft()
        physical = self.physical()
        self.assertIsNone(self.run_pair(lambda c:self.sql_receive(c,draft),self.sql_cut))
        self.assertEqual(self.query('SELECT status FROM public.tickets WHERE id=%s',(self.ticket,)),[('pago',)])
        self.assertEqual(self.physical(),physical)

    def test_timestamps_previous_date_and_session_timezone_do_not_change_conference(self):
        self.query("UPDATE public.tickets SET criado_em=criado_em-interval '2 days' WHERE id=%s",(self.ticket,))
        self.query("UPDATE public.itens_ticket SET cortado_em=cortado_em-interval '2 days' WHERE ticket_id=%s",(self.ticket,))
        draft = self.draft()
        # Snapshot generado en Córdoba comparado por conexión en UTC.
        self.assertEqual(self.query('SELECT public.fn_conferencia_ticket(%s)::text',(self.ticket,))[0][0],draft['conferencia'])
        physical = self.physical()
        self.db.receber_ticket(draft,self.users[0])
        self.assertEqual(self.physical(),physical)
        row = self.query('SELECT t.criado_em,v.recebido_em FROM public.tickets t '
            'JOIN public.vendas v ON v.ticket_id=t.id WHERE t.id=%s',(self.ticket,))[0]
        self.assertGreater(row[1],row[0])


if __name__=='__main__':
    unittest.main()
