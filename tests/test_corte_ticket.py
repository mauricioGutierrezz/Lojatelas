"""1B: PostgreSQL real, conexión restringida, sesiones HTTP y locks observados."""
import os
import re
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from app_loja.corte import allocation_input, suggestion


class SelectionTests(unittest.TestCase):
    def test_open_first_then_smallest_capable_manual_split(self):
        lots = [{'lote_id':1,'status_operacional':'aberto','quantidade_atual':Decimal(30)},
                {'lote_id':2,'status_operacional':'aberto','quantidade_atual':Decimal(12)},
                {'lote_id':3,'status_operacional':'fechado','quantidade_atual':Decimal(10)}]
        self.assertEqual(suggestion(lots,Decimal(8)),2)
        self.assertEqual(suggestion(lots,Decimal(15)),1)
        self.assertEqual(suggestion(lots,Decimal(31)),None)
        self.assertEqual(suggestion(lots[2:],Decimal(8)),3)

    def test_exact_manual_allocations_reject_duplicates_and_mismatch(self):
        self.assertEqual(allocation_input(['2','1'],['1,125','2'],Decimal('3.125')),
                         [{'lote_id':1,'quantidade':'2'},{'lote_id':2,'quantidade':'1.125'}])
        for ids,amounts in ((['1','1'],['1','2']),(['1'],['NaN']),(['1'],['2.0001']),
                           (['1'],['2']),(['1'],[])):
            with self.subTest(ids=ids,amounts=amounts), self.assertRaises(ValueError):
                allocation_input(ids,amounts,Decimal(3))


@unittest.skipUnless(os.getenv('LOJA_TEST_DB')=='1','Requiere el cluster descartable del runner')
class CorteTicketIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from app_loja import db
        from app_loja.run import create_app
        cls.pg = psycopg2
        cls.admin_config = dict(host=os.environ['PGHOST'],port=os.environ['PGPORT'],
            dbname=os.environ['PGDATABASE'],user=os.environ['PGUSER'])
        cls.operator_config = {**cls.admin_config,'user':'loja_test_corte'}
        conn = psycopg2.connect(**cls.admin_config)
        try:
            with conn,conn.cursor() as c:
                c.execute('CREATE ROLE loja_test_corte LOGIN')
                c.execute('GRANT loja_operador TO loja_test_corte')
                cls.users = []
                for name in ('Ana','Berta'):
                    c.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES"
                        "(%s,%s,public.crypt('fixture-only',public.gen_salt('bf')),'admin') RETURNING id",
                        (name,'corte_'+name))
                    cls.users.append(c.fetchone()[0])
        finally:
            conn.close()
        cls.db = db
        cls.original = db.DB_CONFIG
        db.DB_CONFIG = cls.operator_config
        cls.app = create_app({'TESTING':True,'SECRET_KEY':'fixture-1b-only'})

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

    def login(self,name='Ana'):
        client = self.app.test_client()
        client.get('/login')
        response = self.post(client,'/login',{'login':'corte_'+name,'senha':'fixture-only'})
        self.assertEqual(response.status_code,302)
        client.get('/stock')
        return client

    def post(self,client,path,data):
        with client.session_transaction() as s:
            data = {**data,'csrf':s['csrf']}
        return client.post(path,data=data)

    def setUp(self):
        self.client = self.login()
        self.ticket = self.db.iniciar_ticket(str(uuid4()),self.users[0])
        self.product = self.db.cadastrar_produto({'tipo_id':1,'nome':'Algodón '+str(uuid4()),
            'unidade':'m','preco':Decimal('12.50'),'largura':None,'padrao':Decimal(30)},self.users[0])
        self.db.confirmar_ingresso(str(uuid4()),[
            {'produto_id':self.product,'rolos':1,'quantidade':'30'},
            {'produto_id':self.product,'rolos':1,'quantidade':'45'}],self.users[0])
        self.lots = [r[0] for r in self.query('SELECT id FROM public.estoque_lotes WHERE produto_id=%s ORDER BY id',
                                            (self.product,))]

    def draft(self,quantity='5',allocations=None,ticket=None,product=None,sold=None):
        return {'ticket_id':ticket or self.ticket,'produto_id':product or self.product,
                'quantidade_vendida':sold if sold is not None else quantity,
                'quantidade_cortada':quantity,'chave':str(uuid4()),
                'alocacoes':allocations or [{'lote_id':self.lots[0],'quantidade':quantity}]}

    def token(self,response):
        self.assertEqual(response.status_code,200)
        return re.search(r'name="envio" value="([^"]+)"',response.get_data(as_text=True)).group(1)

    def review(self,client,product,quantity,ids,amounts,sold=None):
        sold = quantity if sold is None else sold
        selection = client.get(f'/tickets/{self.ticket}/corte/{product}',query_string={'quantidade_vendida':sold,'quantidade_cortada':quantity})
        preparation = re.search(r'name="preparo" value="([^"]+)"',selection.get_data(as_text=True)).group(1)
        return self.post(client,f'/tickets/{self.ticket}/corte/{product}/revisar',{
            'preparo':preparation,'quantidade_vendida':sold,'quantidade_cortada':quantity,'lote_id':[str(i) for i in ids],'retirar':amounts})

    def test_repeated_preparation_and_confirmation_share_one_cut_key(self):
        path = f'/tickets/{self.ticket}/corte/{self.product}'
        selection = self.client.get(path,query_string={'quantidade_vendida':'5','quantidade_cortada':'5'})
        preparation = re.search(r'name="preparo" value="([^"]+)"',selection.get_data(as_text=True)).group(1)
        data = {'preparo':preparation,'quantidade_vendida':'5','quantidade_cortada':'5','lote_id':[str(self.lots[0])],'retirar':['5']}
        first = self.token(self.post(self.client,path+'/revisar',data))
        second = self.token(self.post(self.client,path+'/revisar',data))
        self.assertEqual(first,second)
        self.assertEqual(self.confirm(self.client,first).status_code,302)
        self.assertEqual(self.confirm(self.client,second).status_code,302)
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (self.ticket,))[0][0],1)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
                                   (self.lots[0],))[0][0],Decimal(25))

    def confirm(self,client,token):
        return self.post(client,f'/tickets/{self.ticket}/corte/confirmar',{'envio':token,'realizado':'si'})

    def test_category_search_todos_context_and_return_after_cut(self):
        from html import unescape
        from urllib.parse import parse_qs,urlsplit
        label='Filtro petróleo '+str(uuid4())
        self.query('UPDATE produtos SET nome=%s WHERE id=%s',(label,self.product))
        category=self.query('INSERT INTO tipos_tela(nome) VALUES(%s) RETURNING id',('Otros '+str(uuid4()),))[0][0]
        self.db.cadastrar_produto({'tipo_id':category,'nome':label+' otro','unidade':'m',
            'preco':Decimal(1),'largura':None,'padrao':None},self.users[0])
        paths=('/stock',f'/tickets/{self.ticket}/productos')
        for path in paths:
            page=self.client.get(path,query_string={'q':label.replace('petróleo','petroleo'),'categoria':'1'}).get_data(as_text=True)
            self.assertIn(label,page)
            self.assertNotIn(label+' otro',page)
            self.assertIn('value="1" aria-pressed="true"',page)
            self.assertNotIn('<select',page)
            # Sin JS, el botón también reemplaza la categoría del input oculto.
            page=self.client.get(path+'?q='+label.replace('petróleo','petroleo')+'&categoria=1&categoria=').get_data(as_text=True)
            self.assertIn(label+' otro',page)
            self.assertIn('value="" aria-pressed="true"',page)
        context={'q':label.replace('petróleo','petroleo'),'categoria':'1'}
        path=f'/tickets/{self.ticket}/corte/{self.product}'
        page=self.client.get(path,query_string=context).get_data(as_text=True)
        back=unescape(re.search(r'href="([^"]+)"[^>]*>← Ticket',page).group(1))
        self.assertEqual(parse_qs(urlsplit(back).query),{'categoria':['1'],'q':[context['q']]})
        preparation=re.search(r'name="preparo" value="([^"]+)"',page).group(1)
        data={'preparo':preparation,'quantidade_vendida':'2,5','quantidade_cortada':'7,125',
              'lote_id':[str(lid) for lid in self.lots],'retirar':['3','4,125']}
        review=self.post(self.client,path+'/revisar',data)
        back=unescape(re.search(r'href="([^"]+)"[^>]*>← Volver a la selección',review.get_data(as_text=True)).group(1))
        returned=self.client.get(back).get_data(as_text=True)
        self.assertIn(f'name="q" value="{context["q"]}"',returned)
        self.assertIn('name="categoria" value="1"',returned)
        registered=self.confirm(self.client,self.token(review))
        self.assertEqual(urlsplit(registered.location).path,f'/tickets/{self.ticket}/productos')
        self.assertEqual(parse_qs(urlsplit(registered.location).query),{'q':[context['q']],'categoria':['1']})
        summary=self.client.get(registered.location).get_data(as_text=True)
        for text in ('Ticket ya registrado',label,'Vendida: 2,5','Cortada: 7,125','Total registrado:','31,25','Ver ticket completo','Ir a Caja / Venta'):
            self.assertIn(text,summary)
        complete=unescape(re.search(r'href="([^"]+)"[^>]*>Ver ticket completo',summary).group(1))
        complete=self.client.get(complete).get_data(as_text=True)
        again=unescape(re.search(r'href="([^"]+)"[^>]*>\+ Agregar producto',complete).group(1))
        self.assertEqual(parse_qs(urlsplit(again).query),{'q':[context['q']],'categoria':['1']})
        self.assertIn('Ticket ya registrado',self.client.get(path).get_data(as_text=True))

    def test_inline_distribution_errors_preserve_inputs_and_preparation(self):
        path=f'/tickets/{self.ticket}/corte/{self.product}'
        initial=self.client.get(path).get_data(as_text=True)
        prep=re.search(r'name="preparo" value="([^"]+)"',initial).group(1)
        for sold,cut,amounts in (('2,5','7,125',['3','4']),('2,5','31',['31','']),
                               ('2,5','7,125',['3','inválido']),('inválido','7,125',['3','4,125'])):
            with self.subTest(sold=sold,cut=cut,amounts=amounts):
                response=self.post(self.client,path+'/revisar',{'preparo':prep,'quantidade_vendida':sold,
                    'quantidade_cortada':cut,'lote_id':[str(lid) for lid in self.lots],'retirar':amounts})
                self.assertEqual(response.status_code,400)
                text=response.get_data(as_text=True)
                self.assertIn('id="corte-seleccion"',text)
                self.assertIn('role="alert"',text)
                self.assertIn(f'name="preparo" value="{prep}"',text)
                self.assertIn(f'name="quantidade_vendida" inputmode="decimal" value="{sold}"',text)
                self.assertIn(f'name="quantidade_cortada" inputmode="decimal" value="{cut}"',text)
                for lid,amount in zip(self.lots,amounts):
                    self.assertIn(f'id="lote-{lid}" name="retirar" inputmode="decimal" value="{amount}"',text)
        self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],0)
        self.assertEqual(self.query('SELECT quantidade_atual FROM estoque_lotes WHERE id=ANY(%s) ORDER BY id',
            (self.lots,)),[(Decimal(30),),(Decimal(45),)])

    def test_partial_suggestion_readonly_single_roll_and_manual_preserved(self):
        path=f'/tickets/{self.ticket}/corte/{self.product}'
        for sold,cut in (('2','5'),('10000','5'),('2','40'),('2','60')):
            response=self.client.get(path,query_string={'parcial':'si','quantidade_vendida':sold,'quantidade_cortada':cut})
            self.assertEqual(response.status_code,200)
            self.assertNotIn(b'<html',response.data)
            self.assertLessEqual(response.get_data(as_text=True).count('data-suggested'),1)
            values=re.findall('name="retirar" inputmode="decimal" value="([^"]*)"',response.get_data(as_text=True))
            self.assertLessEqual(sum(bool(v) for v in values),1)
            if cut=='60':self.assertEqual(values,['',''])
        response=self.client.get(path,query_string={'parcial':'si','quantidade_vendida':'2,5','quantidade_cortada':'7,125',
            'lote_id':[str(lid) for lid in self.lots],'retirar':['3','4,125']})
        for lid,amount in zip(self.lots,('3','4,125')):
            self.assertIn(f'id="lote-{lid}" name="retirar" inputmode="decimal" value="{amount}"',response.get_data(as_text=True))
        self.assertEqual(self.client.get(path,query_string={'parcial':'si','quantidade_vendida':'2','quantidade_cortada':'inválido'}).status_code,400)
        self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],0)

    def test_empty_ticket_has_no_caja_shortcut_items_have_secondary_caja(self):
        for path in (f'/tickets/{self.ticket}',f'/tickets/{self.ticket}/productos',f'/tickets/{self.ticket}/corte/{self.product}'):
            self.assertNotIn(f'href="/caixa/tickets/{self.ticket}"',self.client.get(path).get_data(as_text=True))
        # Caja puede consultar un ticket vacío, pero el banco no autoriza el cobro.
        with self.assertRaises(self.pg.Error):
            self.db.preparar_cobro({'ticket_id':self.ticket,'conferencia':self.db.conferir_ticket(self.ticket)[0]['conferencia']},None,'otro')
        first=self.confirm(self.client,self.token(self.review(self.client,self.product,'5',[self.lots[0]],['5'])))
        second=self.confirm(self.client,self.token(self.review(self.client,self.product,'7',self.lots,['3','4'],sold='2')))
        self.assertEqual(first.location,second.location)
        summary=self.client.get(second.location).get_data(as_text=True)
        self.assertIn('2 item(s) registrado(s)',summary)
        self.assertIn('Total registrado: <strong>87,50</strong>',summary)
        page=self.client.get(f'/tickets/{self.ticket}').get_data(as_text=True)
        self.assertIn('class="button" href=',page)
        self.assertIn('+ Agregar producto',page)
        self.assertIn(f'class="button secondary" href="/caixa/tickets/{self.ticket}"',page)
        self.assertEqual(self.client.get(f'/caixa/tickets/{self.ticket}').status_code,200)

    def test_web_flow_repetition_shared_ticket_authors_price_and_persistence(self):
        nuevo = self.token(self.client.get('/tickets'))
        created = self.post(self.client,'/tickets/nuevo',{'envio':nuevo})
        repeated = self.post(self.client,'/tickets/nuevo',{'envio':nuevo})
        self.assertEqual(created.location,repeated.location)
        selection = self.client.get(f'/tickets/{self.ticket}/corte/{self.product}?quantidade_vendida=5&quantidade_cortada=5')
        self.assertIn(b'Sugerido',selection.data)
        self.assertIn(b'value="5"',selection.data)
        review = self.review(self.client,self.product,'5',[self.lots[0]],['5'])
        token = self.token(review)
        self.assertIn(b'25',review.data)
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (self.ticket,))[0][0],0)
        self.assertEqual(self.confirm(self.client,token).status_code,302)
        self.assertEqual(self.confirm(self.client,token).status_code,302)
        self.query('UPDATE public.produtos SET preco_unitario=99 WHERE id=%s',(self.product,))
        berta = self.login('Berta')
        code = self.query('SELECT codigo FROM public.tickets WHERE id=%s',(self.ticket,))[0][0]
        found = berta.get('/tickets',query_string={'codigo':code.lower()})
        self.assertIn(code.encode(),found.data)
        token2 = self.token(self.review(berta,self.product,'40',self.lots,['10','30']))
        self.assertEqual(self.confirm(berta,token2).status_code,302)
        rows = self.query('SELECT quantidade_vendida,preco_unitario,cortado_por FROM public.itens_ticket '
                          'WHERE ticket_id=%s ORDER BY id',(self.ticket,))
        self.assertEqual(rows,[(Decimal(5),Decimal('12.50'),self.users[0]),
                               (Decimal(40),Decimal(99),self.users[1])])
        # Un segundo producto en el mismo atendimento.
        other = self.db.cadastrar_produto({'tipo_id':1,'nome':'Otro '+str(uuid4()),'unidade':'kg',
            'preco':Decimal(2),'largura':None,'padrao':None},self.users[1])
        self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':other,'pecas':1,'quantidade':'2'}],self.users[1])
        otherlot = self.query('SELECT id FROM public.estoque_lotes WHERE produto_id=%s',(other,))[0][0]
        self.confirm(berta,self.token(self.review(berta,other,'1,125',[otherlot],['1,125'])))
        fresh = self.login('Berta')
        summary = fresh.get(f'/tickets/{self.ticket}')
        for text in (code,'Pago pendiente','Ana','Berta','Precio congelado','4.024,75'):
            self.assertIn(text.encode(),summary.data)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes '
                                   'WHERE produto_id=%s ORDER BY id',(self.product,)),
                         [(Decimal(15),),(Decimal(15),)])
        self.assertEqual(self.query('SELECT count(*) FROM public.movimentacoes m JOIN public.itens_ticket i '
            'ON i.id=m.item_ticket_id WHERE i.ticket_id=%s AND m.usuario_id<>i.cortado_por',
            (self.ticket,))[0][0],0)
        self.assertEqual(self.query('SELECT count(*) FROM public.vw_reconciliacao_estoque WHERE diferenca<>0')[0][0],0)

    def test_back_from_review_restores_multilote_and_same_submission_key(self):
        from html import unescape
        original=self.review(self.client,self.product,'7,125',self.lots,['3','4,125'],sold='2,5')
        original_token=self.token(original)
        back=unescape(re.search(r'href="([^"]+)"[^>]*>← Volver a la selección',original.get_data(as_text=True)).group(1))
        returned=self.client.get(back)
        html=returned.get_data(as_text=True)
        self.assertEqual(returned.status_code,200)
        self.assertIn('name="quantidade_vendida" inputmode="decimal" value="2,5"',html)
        self.assertIn('name="quantidade_cortada" inputmode="decimal" value="7,125"',html)
        for lid,amount in zip(self.lots,('3','4,125')):
            self.assertIn(f'id="lote-{lid}" name="retirar" inputmode="decimal" value="{amount}"',html)
        prep=re.search(r'name="preparo" value="([^"]+)"',html).group(1)
        again=self.post(self.client,f'/tickets/{self.ticket}/corte/{self.product}/revisar',{
            'preparo':prep,'quantidade_vendida':'2,5','quantidade_cortada':'7,125',
            'lote_id':[str(lid) for lid in self.lots],'retirar':['3','4,125']})
        self.assertEqual(self.token(again),original_token)
        self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],0)
        self.assertEqual(self.client.get(back.split('?')[0],query_string={'volver':'invalid'}).status_code,400)
        berta=self.login('Berta')
        self.assertEqual(berta.get(back).status_code,400)
        self.assertEqual(self.confirm(self.client,original_token).status_code,302)
        self.assertEqual(self.confirm(self.client,self.token(again)).status_code,302)
        self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],1)

    def test_corte_search_without_accent_and_review_money_uses_sold_quantity(self):
        name='Gabardina petróleo '+str(uuid4())
        self.query('UPDATE produtos SET nome=%s,preco_unitario=12500.50 WHERE id=%s',(name,self.product))
        for query in ('petroleo','petróleo','PETRÓLEO'):
            response=self.client.get(f'/tickets/{self.ticket}/productos',query_string={'q':query})
            self.assertIn(name,response.get_data(as_text=True))
            self.assertIn('12.500,50',response.get_data(as_text=True))
        review=self.review(self.client,self.product,'7,125',self.lots,['3','4,125'],sold='2,5')
        text=review.get_data(as_text=True)
        self.assertIn('Precio unitario actual: 12.500,50',text)
        self.assertIn('Subtotal: <strong>31.251,25</strong>',text)
        self.assertIn('Cantidad cortada: 7,125',text)
        self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],0)
        self.confirm(self.client,self.token(review))
        self.assertEqual(self.query('SELECT preco_unitario,valor_total FROM itens_ticket WHERE ticket_id=%s',(self.ticket,)),
            [(Decimal('12500.50'),Decimal('31251.25'))])
        for path in (f'/tickets/{self.ticket}','/tickets',f'/caixa/tickets/{self.ticket}'):
            self.assertIn('31.251,25',self.client.get(path).get_data(as_text=True))

    def test_review_subtotal_matches_postgres_rounding_at_half_cent(self):
        self.query('UPDATE produtos SET preco_unitario=0.04 WHERE id=%s',(self.product,))
        review=self.review(self.client,self.product,'1',[self.lots[0]],['1'],sold='0,125')
        self.assertIn('Subtotal: <strong>0,01</strong>',review.get_data(as_text=True))
        self.confirm(self.client,self.token(review))
        self.assertEqual(self.query('SELECT valor_total FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],Decimal('0.01'))

    def test_return_keeps_selected_roll_even_if_another_cut_exhausted_it(self):
        from html import unescape
        review=self.review(self.client,self.product,'7,125',self.lots,['3','4,125'],sold='2,5')
        back=unescape(re.search(r'href="([^"]+)"[^>]*>← Volver a la selección',review.get_data(as_text=True)).group(1))
        other=self.db.iniciar_ticket(str(uuid4()),self.users[1])
        self.db.registrar_corte(self.draft('30',ticket=other),self.users[1])
        page=self.client.get(back).get_data(as_text=True)
        self.assertIn('Agotado',page)
        self.assertIn(f'id="lote-{self.lots[0]}" name="retirar" inputmode="decimal" value="3"',page)
        self.assertIn(f'id="lote-{self.lots[1]}" name="retirar" inputmode="decimal" value="4,125"',page)
        rejected=self.confirm(self.client,self.token(review))
        self.assertEqual(rejected.status_code,409)
        self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE ticket_id=%s',(self.ticket,))[0][0],0)

    def test_invalid_inputs_and_permissions_have_no_partial_effects(self):
        for draft in (self.draft('31'), self.draft('5',[{'lote_id':self.lots[0],'quantidade':'4'}]),
                      self.draft('5',[{'lote_id':self.lots[0],'quantidade':'2'},
                                      {'lote_id':999999999,'quantidade':'3'}]),
                      self.draft('NaN'),self.draft('Infinity'),self.draft('0'),self.draft('1.0001'),
                      self.draft('5',[{'lote_id':self.lots[0],'quantidade':'2'},
                                      {'lote_id':self.lots[0],'quantidade':'3'}])):
            with self.subTest(draft=draft),self.assertRaises(self.pg.Error):
                self.db.registrar_corte(draft,self.users[0])
        otherproduct = self.db.cadastrar_produto({'tipo_id':1,'nome':'Otro','unidade':'m',
            'preco':Decimal(1),'largura':None,'padrao':None},self.users[0])
        with self.assertRaises(self.pg.Error):
            self.db.registrar_corte(self.draft(product=otherproduct),self.users[0])
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (self.ticket,))[0][0],0)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes '
                                   'WHERE produto_id=%s ORDER BY id',(self.product,)),[(Decimal(30),),(Decimal(45),)])
        for sql in ('INSERT INTO public.tickets(atendido_por) VALUES (1)',
                    'UPDATE public.itens_ticket SET preco_unitario=1',
                    'DELETE FROM public.itens_ticket','UPDATE public.estoque_lotes SET quantidade_atual=100',
                    'SELECT senha_hash FROM public.usuarios'):
            with self.subTest(sql=sql),self.assertRaises(self.pg.errors.InsufficientPrivilege):
                self.db.fetchall(sql)
        # La ruta antigua sin identificación no debe existir como vía alternativa.
        self.assertIsNone(self.query("SELECT to_regprocedure('public.fn_adicionar_item_corte(bigint,bigint,numeric,jsonb,bigint)')")[0][0])
        self.assertIsNone(self.query("SELECT to_regprocedure('public.fn_adicionar_item_corte(bigint,bigint,numeric,jsonb,bigint,uuid)')")[0][0])

    def test_independent_quantities_value_stock_movements_and_neutral_difference(self):
        # Ambas las órdenes y diferencias amplias son válidas; sin tolerancia ni clasificación.
        cases = [('2','3.125'),('10000','0.001'),('0.001','10'),('1','1')]
        for sold,cut in cases:
            with self.subTest(sold=sold,cut=cut):
                draft = self.draft(cut,sold=sold)
                item = self.db.registrar_corte(draft,self.users[0])
                self.assertEqual(self.db.registrar_corte(draft,self.users[0]),item)
                row = self.query('SELECT quantidade_vendida,quantidade_cortada,diferenca_quantidade,'
                    'valor_total,preco_unitario FROM public.itens_ticket WHERE id=%s',(item,))[0]
                self.assertEqual(row,(Decimal(sold),Decimal(cut),Decimal(cut)-Decimal(sold),
                    (Decimal(sold)*Decimal('12.50')).quantize(Decimal('.01')),Decimal('12.50')))
                self.assertEqual(self.query('SELECT sum(quantidade) FROM public.alocacoes_estoque '
                    'WHERE item_ticket_id=%s',(item,))[0][0],Decimal(cut))
                self.assertEqual(self.query('SELECT tipo,quantidade,usuario_id FROM public.movimentacoes '
                    'WHERE item_ticket_id=%s',(item,)),[('CORTE',Decimal(cut),self.users[0])])
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
            (self.lots[0],))[0][0],Decimal('15.874'))
        self.assertEqual(self.query('SELECT count(*) FROM public.vw_reconciliacao_estoque WHERE diferenca<>0')[0][0],0)

    def test_web_distinct_quantities_multilote_and_display(self):
        review = self.review(self.client,self.product,'7.125',self.lots,['3','4.125'],sold='2,5')
        for text in ('Cantidad vendida: 2,5','Cantidad cortada: 7,125','Diferencia (cortada − vendida): 4,625'):
            self.assertIn(text,review.get_data(as_text=True))
        token = self.token(review)
        self.assertEqual(self.confirm(self.client,token).status_code,302)
        self.assertEqual(self.confirm(self.client,token).status_code,302)
        self.query('UPDATE public.produtos SET preco_unitario=99 WHERE id=%s',(self.product,))
        summary = self.client.get(f'/tickets/{self.ticket}').get_data(as_text=True)
        for text in ('Cantidad vendida: 2,5','Cantidad cortada: 7,125','4,625','31,25','12,5'):
            self.assertIn(text,summary)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes '
            'WHERE produto_id=%s ORDER BY id',(self.product,)),[(Decimal(27),),(Decimal('40.875'),)])
        selection = self.client.get(f'/tickets/{self.ticket}/corte/{self.product}',
            query_string={'quantidade_vendida':'10000','quantidade_cortada':'5'})
        self.assertIn(b'Sugerido',selection.data)

    def test_each_quantity_validated_and_both_bound_to_idempotency(self):
        for field in ('quantidade_vendida','quantidade_cortada'):
            for value in (None,'0','-1','NaN','Infinity','1.0001','1000000000'):
                with self.subTest(field=field,value=value),self.assertRaises(self.pg.Error):
                    self.db.registrar_corte({**self.draft(),field:value},self.users[0])
        draft = self.draft('5',sold='100')
        first = self.db.registrar_corte(draft,self.users[0])
        for changed in ({**draft,'quantidade_vendida':'101'},
                        {**draft,'quantidade_cortada':'6',
                         'alocacoes':[{'lote_id':self.lots[0],'quantidade':'6'}]}):
            with self.assertRaises(self.pg.Error):
                self.db.registrar_corte(changed,self.users[0])
        self.assertEqual(self.db.registrar_corte(draft,self.users[0]),first)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
            (self.lots[0],))[0][0],Decimal(25))

    def test_deferred_allocation_integrity_uses_cut_quantity(self):
        item = self.db.registrar_corte(self.draft('5',sold='100'),self.users[0])
        with self.assertRaises(self.pg.Error):
            self.query('UPDATE public.itens_ticket SET quantidade_cortada=6 WHERE id=%s',(item,))
        self.assertEqual(self.query('SELECT quantidade_vendida,quantidade_cortada FROM public.itens_ticket '
            'WHERE id=%s',(item,)),[(Decimal(100),Decimal(5))])

    def test_real_post_write_failure_rolls_back_every_effect(self):
        # Forzar un fallo al escribir el segundo movimiento, después del primero.
        self.query('''CREATE FUNCTION public.fail_1b_fixture() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.tipo='CORTE' AND NEW.lote_id=%s THEN RAISE EXCEPTION 'fixture';
            END IF; RETURN NEW; END $$''',(self.lots[1],))
        self.query('CREATE TRIGGER fail_1b_fixture BEFORE INSERT ON public.movimentacoes '
                   'FOR EACH ROW EXECUTE FUNCTION public.fail_1b_fixture()')
        draft = self.draft('10',[{'lote_id':self.lots[0],'quantidade':'5'},
                                {'lote_id':self.lots[1],'quantidade':'5'}],sold='2')
        try:
            with self.assertRaises(self.pg.Error):
                self.db.registrar_corte(draft,self.users[0])
            self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                       (self.ticket,))[0][0],0)
            self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes '
                                       'WHERE produto_id=%s ORDER BY id',(self.product,)),[(Decimal(30),),(Decimal(45),)])
            self.assertEqual(self.query("SELECT count(*) FROM public.movimentacoes WHERE produto_id=%s AND tipo='CORTE'",
                                       (self.product,))[0][0],0)
        finally:
            self.query('DROP TRIGGER fail_1b_fixture ON public.movimentacoes')
            self.query('DROP FUNCTION public.fail_1b_fixture()')
        first = self.db.registrar_corte(draft,self.users[0])
        self.assertEqual(first,self.db.registrar_corte(draft,self.users[0]))

    def test_changed_payload_reused_key_and_tampered_web_requests_rejected(self):
        draft = self.draft()
        self.db.registrar_corte(draft,self.users[0])
        changed = {**draft,'quantidade_cortada':'6','alocacoes':[{'lote_id':self.lots[0],'quantidade':'6'}]}
        for changed_draft,user in ((changed,self.users[0]),(draft,self.users[1])):
            with self.assertRaises(self.pg.Error):
                self.db.registrar_corte(changed_draft,user)
        token = self.token(self.review(self.client,self.product,'2',[self.lots[0]],['2']))
        self.assertEqual(self.confirm(self.client,token+'x').status_code,400)
        self.assertEqual(self.post(self.client,f'/tickets/{self.ticket}/corte/confirmar',{'envio':token}).status_code,400)
        self.assertEqual(self.confirm(self.login('Berta'),token).status_code,400)
        self.assertEqual(self.post(self.client,'/tickets/nuevo',{'envio':token}).status_code,400)
        self.assertEqual(self.client.post('/tickets/nuevo',data={'envio':token}).status_code,400)
        for path in ('/conteo','/pagar','/cancelar','/imprimir'):
            self.assertEqual(self.client.get(path).status_code,404)

    def test_stock_changed_since_review_safe_failure_and_same_key_retry(self):
        token = self.token(self.review(self.client,self.product,'25',[self.lots[0]],['25']))
        self.db.registrar_corte(self.draft('10'),self.users[1])
        response = self.confirm(self.client,token)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.token_for_error(response),token)
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (self.ticket,))[0][0],1)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
                                   (self.lots[0],))[0][0],Decimal(20))

    def test_roll_states_live_suggestion_and_manual_choice(self):
        self.db.registrar_corte(self.draft('20'),self.users[0])
        from app_loja.routes.corte_routes import available_lots
        lots = available_lots(self.product,Decimal(5))
        self.assertEqual(lots[0]['lote_id'],self.lots[0])
        self.assertEqual(suggestion(lots,Decimal(5)),self.lots[0])
        # La atendente puede seleccionar un cerrado aunque se sugiera un abierto.
        token = self.token(self.review(self.client,self.product,'5',[self.lots[1]],['5']))
        self.assertEqual(self.confirm(self.client,token).status_code,302)
        self.assertEqual(suggestion(available_lots(self.product,Decimal(12)),Decimal(12)),self.lots[1])
        self.db.registrar_corte(self.draft('10'),self.users[0])
        self.assertEqual(self.query('SELECT status_operacional,quantidade_atual FROM public.estoque_lotes '
            'WHERE id=%s',(self.lots[0],)),[('esgotado',Decimal(0))])
        self.assertNotIn(self.lots[0],[lot['lote_id'] for lot in available_lots(self.product,Decimal(1))])

    def test_non_pending_ticket_and_inactive_user_cannot_add_cuts(self):
        self.query("UPDATE public.tickets SET status='pago' WHERE id=%s",(self.ticket,))
        with self.assertRaises(self.pg.Error):
            self.db.registrar_corte(self.draft(),self.users[0])
        self.assertEqual(self.client.get(f'/tickets/{self.ticket}/productos').status_code,400)
        # Fixture de usuario inactivo, sin cambiar la política de identidad.
        self.query('UPDATE public.usuarios SET ativo=false WHERE id=%s',(self.users[1],))
        try:
            with self.assertRaises(self.pg.Error):
                self.db.registrar_corte(self.draft(),self.users[1])
        finally:
            self.query('UPDATE public.usuarios SET ativo=true WHERE id=%s',(self.users[1],))
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (self.ticket,))[0][0],0)

    def token_for_error(self,response):
        return re.search(r'name="envio" value="([^"]+)"',response.get_data(as_text=True)).group(1)

    def run_blocked_pair(self,first,second,first_user=None,second_user=None):
        from psycopg2.extras import Json
        a = self.pg.connect(**self.operator_config)
        b = self.pg.connect(**self.operator_config)
        sql = 'SELECT public.fn_adicionar_item_corte(%s,%s,%s,%s,%s::jsonb,%s,%s::uuid)'
        def args(draft,user):
            return (draft['ticket_id'],draft['produto_id'],draft['quantidade_vendida'],draft['quantidade_cortada'],Json(draft['alocacoes']),
                    user or self.users[0],draft['chave'])
        try:
            with a.cursor() as c:
                c.execute('SET ROLE loja_operador')
                c.execute(sql,args(first,first_user))
                first_id = c.fetchone()[0]
            def perform_second():
                with b,b.cursor() as c:
                    c.execute('SET ROLE loja_operador')
                    c.execute("SET LOCAL statement_timeout='8s'")
                    c.execute(sql,args(second,second_user))
                    return c.fetchone()[0]
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(perform_second)
                waited = False
                for _ in range(50):
                    state = self.query('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',
                                       (b.get_backend_pid(),))
                    if state and state[0][0]=='Lock':
                        waited = True
                        break
                    time.sleep(.02)
                a.commit()
                self.assertTrue(waited,'La segunda conexión debe esperar un lock real.')
                try:
                    result = future.result(timeout=10)
                except self.pg.Error:
                    result = None
                return first_id,result
        finally:
            a.close()
            b.close()

    def test_concurrent_same_submission_is_one_cut(self):
        draft = self.draft('5',sold='100')
        first,second = self.run_blocked_pair(draft,draft)
        self.assertEqual(first,second)
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (self.ticket,))[0][0],1)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
                                   (self.lots[0],))[0][0],Decimal(25))

    def test_concurrent_different_tickets_same_roll_revalidates_balance(self):
        other_ticket = self.db.iniciar_ticket(str(uuid4()),self.users[1])
        first,second = self.run_blocked_pair(self.draft('20',sold='1'),self.draft('20',ticket=other_ticket,sold='2'),
                                            second_user=self.users[1])
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(self.query('SELECT count(*) FROM public.itens_ticket WHERE ticket_id=%s',
                                   (other_ticket,))[0][0],0)
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
                                   (self.lots[0],))[0][0],Decimal(10))

    def test_concurrent_different_cuts_same_ticket_preserve_both_authors(self):
        first,second = self.run_blocked_pair(self.draft('5',sold='100'),self.draft('7',sold='1'),second_user=self.users[1])
        self.assertNotEqual(first,second)
        self.assertIsNotNone(second)
        self.assertEqual(self.query('SELECT cortado_por FROM public.itens_ticket WHERE ticket_id=%s ORDER BY id',
                                   (self.ticket,)),[(self.users[0],),(self.users[1],)])
        self.assertEqual(self.query('SELECT quantidade_atual FROM public.estoque_lotes WHERE id=%s',
                                   (self.lots[0],))[0][0],Decimal(18))


if __name__=='__main__':
    unittest.main()
