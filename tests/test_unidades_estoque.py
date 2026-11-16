"""Percursos m/un/kg completos, exclusivamente no PostgreSQL descartável do runner."""
import os
import re
import json
import unittest
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

@unittest.skipUnless(os.getenv('LOJA_TEST_DB')=='1','Requiere PostgreSQL descartable')
class UnidadesTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import psycopg2
  from app_loja import db
  from app_loja.run import create_app
  cls.pg=psycopg2; cls.db=db
  cls.config=dict(host=os.environ['PGHOST'],port=os.environ['PGPORT'],dbname=os.environ['PGDATABASE'],user=os.environ['PGUSER'])
  with psycopg2.connect(**cls.config) as conn,conn.cursor() as c:
   c.execute('CREATE ROLE unidades_test_app LOGIN'); c.execute('GRANT loja_operador TO unidades_test_app')
   c.execute("INSERT INTO usuarios(nome,login,senha_hash,perfil) VALUES('TESTE Unidades','unidades_test','fixture','admin') RETURNING id");cls.user=c.fetchone()[0]
   c.execute("INSERT INTO tipos_tela(nome) VALUES('TESTE Unidades') RETURNING id");cls.cat=c.fetchone()[0]
  cls.previous=db.DB_CONFIG; db.DB_CONFIG={**cls.config,'user':'unidades_test_app'}
  cls.app=create_app({'TESTING':True,'SECRET_KEY':'fixture-unidades'})
 @classmethod
 def tearDownClass(cls): cls.db.DB_CONFIG=cls.previous
 def setUp(self):
  self.client=self.app.test_client()
  with self.client.session_transaction() as s:s.update(usuario_id=self.user,csrf='fixture-csrf')
 def post(self,url,data): return self.client.post(url,data={'csrf':'fixture-csrf',**data})
 def query(self,sql,args=()):
  with self.pg.connect(**self.config) as conn,conn.cursor() as c:
   c.execute(sql,args);return c.fetchall() if c.description else None
 def product(self,unit):
  return self.db.cadastrar_produto(dict(tipo_id=self.cat,nome='TESTE '+unit+' '+str(uuid4()),unidade=unit,preco=Decimal('12.50'),largura=None,padrao=None),self.user)
 def entry(self,p,unit,quantity,count=1,key=None):
  g={'produto_id':p,'quantidade':str(quantity)}
  if unit!='un':g['rolos' if unit=='m' else 'pecas']=count
  return self.db.confirmar_ingresso(key or str(uuid4()),[g],self.user)
 def ticket(self):return self.db.iniciar_ticket(str(uuid4()),self.user)
 def lots(self,p):return self.query('SELECT id,quantidade_atual,status_operacional FROM estoque_lotes WHERE produto_id=%s ORDER BY id',(p,))
 def cut(self,t,p,sold,cut,allocations=None,key=None):
  return self.db.registrar_corte(dict(ticket_id=t,produto_id=p,quantidade_vendida=str(sold),quantidade_cortada=str(cut),alocacoes=allocations or [],chave=key or str(uuid4())),self.user)
 def alloc(self,lot,q):return {'lote_id':lot,'quantidade':str(q)}
 def balance(self,p):return self.query('SELECT estoque_total FROM vw_estoque_por_produto WHERE produto_id=%s',(p,))[0][0]
 def token(self,response,name):
  match=re.search(r'name="'+name+'" value="([^"]+)"',response.get_data(as_text=True));self.assertIsNotNone(match);return match[1]
 def test_m_five_rolls_max_review_preserved(self):
  p=self.product('m');self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':p,'rolos':4,'quantidade':'30'},{'produto_id':p,'rolos':1,'quantidade':'45'}],self.user)
  self.assertEqual(len(self.lots(p)),5);self.assertEqual(self.balance(p),165)
  t=self.ticket();response=self.client.get(f'/tickets/{t}/corte/{p}?quantidade_vendida=10&quantidade_cortada=40')
  self.assertIn(b'data-max-for',response.data);self.assertIn(b'Cantidad cortada',response.data)
  lots=self.lots(p);self.cut(t,p,10,40,[self.alloc(lots[0][0],20),self.alloc(lots[-1][0],20)])
  self.assertEqual(self.balance(p),125)
 def test_kg_thirty_pieces_partial_exhaustion_multilot(self):
  p=self.product('kg');self.entry(p,'kg',10,30);self.assertEqual(self.balance(p),300);lots=self.lots(p);self.assertEqual(len(lots),30)
  t=self.ticket();self.cut(t,p,1,Decimal('2.5'),[self.alloc(lots[0][0],'2.5')])
  updated=self.lots(p);self.assertEqual(updated[0][1:],(Decimal('7.5'),'aberto'));self.assertTrue(all(l[2]=='fechado' for l in updated[1:]))
  self.cut(t,p,9,Decimal('8.5'),[self.alloc(lots[0][0],'7.5'),self.alloc(lots[1][0],1)])
  self.assertEqual(self.lots(p)[0][2],'esgotado');self.assertEqual(self.balance(p),289)
  page=self.client.get(f'/tickets/{t}/corte/{p}?quantidade_vendida=1&quantidade_cortada=1').get_data(as_text=True)
  self.assertIn('pieza',page);self.assertNotIn('rollo',page.lower())
 def test_un_30_20_minus_7_and_replenish(self):
  p=self.product('un');self.assertEqual(self.balance(p),0);a=self.entry(p,'un',30);b=self.entry(p,'un',20);t=self.ticket();item=self.cut(t,p,7,7)
  self.assertEqual(self.balance(p),43);self.assertEqual(self.lots(p),[])
  self.assertEqual(self.query('SELECT count(*) FROM alocacoes_estoque WHERE item_ticket_id=%s',(item,))[0][0],0)
  self.assertEqual(self.query("SELECT count(*),count(lote_id),count(item_ingresso_id) FROM movimentacoes WHERE item_ticket_id=%s",(item,))[0],(1,0,0))
  self.assertEqual([r[0] for r in self.query('SELECT saldo_depois FROM vw_historico_produto WHERE produto_id=%s ORDER BY id',(p,))],[30,50,43])
  self.cut(t,p,43,43);self.assertEqual(self.balance(p),0);self.entry(p,'un',5);self.assertEqual(self.balance(p),5)
  for path in (f'/ingresos/{a}',f'/ingresos/{b}',f'/productos/{p}',f'/tickets/{t}',f'/tickets/{t}/corte/{p}'):
   page=self.client.get(path);self.assertEqual(page.status_code,200);self.assertNotIn('rollo',page.get_data(as_text=True).lower())
 def test_un_http_entry_review_and_return(self):
  p=self.product('un');page=self.client.get('/entrada?produto_id='+str(p));self.assertNotIn(b'name="rolos"',page.data);self.assertNotIn(b'name="pecas"',page.data)
  for q in ('1.5','-1','NaN','0','1000000000'):
   self.assertEqual(self.post('/entrada/revisar',dict(produto_id=p,quantidade=q)).status_code,400)
  result=self.post('/entrada/revisar',dict(produto_id=p,quantidade='30'));self.assertEqual(result.status_code,302)
  page=self.client.get(result.location);self.assertNotIn('rollo',page.get_data(as_text=True).lower());key=self.token(page,'chave')
  result=self.post('/entrada/confirmar',dict(chave=key));self.assertEqual(result.status_code,302);self.assertEqual(self.balance(p),30)
  self.assertEqual(self.post('/entrada/confirmar',dict(chave=key)).status_code,302);self.assertEqual(self.balance(p),30)
 def test_un_http_cut_review_back_errors_and_direct(self):
  p=self.product('un');self.entry(p,'un',50);t=self.ticket();url=f'/tickets/{t}/corte/{p}'
  page=self.client.get(url);prep=self.token(page,'preparo');self.assertNotIn(b'id="corte-sugerir"',page.data);self.assertNotIn(b'data-max-for',page.data)
  for sold,cut in [('1.5','1'),('1','1.5'),('1','51'),('','1')]:
   response=self.post(url+'/revisar',dict(preparo=prep,quantidade_vendida=sold,quantidade_cortada=cut));self.assertEqual(response.status_code,400)
  response=self.post(url+'/revisar',dict(preparo=prep,quantidade_vendida='5',quantidade_cortada='7',lote_id='1',retirar='7'));self.assertEqual(response.status_code,400)
  response=self.post(url+'/revisar',dict(preparo=prep,quantidade='7'));self.assertEqual(response.status_code,200);self.assertIn(b'Saldo despu',response.data);self.assertIn(b'Retirada realizada',response.data)
  envio=self.token(response,'envio');back=re.search(r'href="([^"]*volver=[^"]+)"',response.get_data(as_text=True))[1];page=self.client.get(back.replace('&amp;','&'));self.assertIn(b'value="7"',page.data)
  response=self.post(f'/tickets/{t}/corte/confirmar',dict(envio=envio,realizado='si'));self.assertEqual(response.status_code,302);self.assertEqual(self.balance(p),43)
 def test_un_forgery_fractions_direct_rejected(self):
  p=self.product('un');self.entry(p,'un',50);t=self.ticket();m=self.product('m');self.entry(m,'m',30);lot=self.lots(m)[0][0]
  for sold,cut,a in [(5,7,[]),('1.5','1',[]),('1','1.5',[]),('1','1',[self.alloc(lot,1)]),('NaN',1,[]),(1,'1.0001',[]),(1,51,[])]:
   with self.subTest(sold=sold,cut=cut),self.assertRaises(self.pg.Error):self.cut(t,p,sold,cut,a)
  for groups in ([{'produto_id':p,'quantidade':'1.5'}],[{'produto_id':p,'quantidade':'1','rolos':1}],[{'produto_id':p,'quantidade':'1','pecas':1}]):
   with self.assertRaises(self.pg.Error):self.db.confirmar_ingresso(str(uuid4()),groups,self.user)
  self.assertEqual(self.balance(p),50)
 def test_kg_http_entry_contract_and_review(self):
  p=self.product('kg');response=self.post('/entrada/revisar',dict(produto_id=p,pecas='30',quantidade='10'));self.assertEqual(response.status_code,302)
  page=self.client.get(response.location);self.assertIn(b'Piezas individuales',page.data);self.assertNotIn('rollo',page.get_data(as_text=True).lower())
  result=self.post('/entrada/confirmar',dict(chave=self.token(page,'chave')));self.assertEqual(result.status_code,302)
  self.assertEqual(self.balance(p),300)
  with self.assertRaises(self.pg.Error):self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':p,'rolos':1,'quantidade':10}],self.user)
 def test_distinct_quantities_all_units_both_orders_mixed_payment_prices(self):
  t=self.ticket();products=[];expected=Decimal(0)
  for unit in ('m','un','kg'):
   p=self.product(unit);products.append(p);self.entry(p,unit,30)
   for sold,cut in ([(2,2),(4,4)] if unit=='un' else [(2,3),(4,1)]):
    self.cut(t,p,sold,cut,[] if unit=='un' else [self.alloc(self.lots(p)[0][0],cut)]);expected+=Decimal(sold)*Decimal('12.50')
  before=[self.balance(p) for p in products]
  self.db.alterar_precos(dict(chave=str(uuid4()),alteracoes=[dict(produto_id=p,anterior='12.50',novo='20.00') for p in products]),self.user)
  ticket,items,_=self.db.conferir_ticket(t);self.assertEqual(ticket['total'],expected);self.assertTrue(all(i['preco_unitario']==Decimal('12.50') for i in items))
  self.db.receber_ticket(dict(ticket_id=t,conferencia=ticket['conferencia'],efectivo='10'),self.user)
  self.assertEqual(before,[self.balance(p) for p in products]);self.assertEqual(self.query('SELECT valor_total,valor_efectivo,valor_otro FROM vendas WHERE ticket_id=%s',(t,))[0],(expected,10,expected-10))
  for path in (f'/tickets/{t}',f'/caixa/tickets/{t}'):
   response=self.client.get(path);self.assertEqual(response.status_code,200)
   for unit in ('m','un','kg'):self.assertIn((' / '+unit).encode(),response.data)
  self.assertFalse(self.query('SELECT * FROM vw_reconciliacao_estoque WHERE diferenca<>0'))
 def test_idempotency_numeric_normalization_sorted_allocations_and_paid(self):
  p=self.product('un');key=str(uuid4());first=self.entry(p,'un','30',key=key);self.assertEqual(first,self.entry(p,'un','30.000',key=key))
  with self.assertRaises(self.pg.Error):self.entry(p,'un',31,key=key)
  t=self.ticket();key=str(uuid4());item=self.cut(t,p,7,7,key=key);ticket,_,_=self.db.conferir_ticket(t)
  self.db.receber_ticket(dict(ticket_id=t,conferencia=ticket['conferencia'],efectivo=0),self.user)
  self.assertEqual(item,self.cut(t,p,'7.000','7.000',key=key));self.assertEqual(self.balance(p),23)
  with self.assertRaises(self.pg.Error):self.cut(t,p,3,7,key=key)
  p=self.product('kg');self.entry(p,'kg',10,2);lots=self.lots(p);t=self.ticket();key=str(uuid4());a=[self.alloc(l[0],1) for l in lots]
  item=self.cut(t,p,1,2,a,key);self.assertEqual(item,self.cut(t,p,1,2,list(reversed(a)),key))
 def test_atomic_entry_bad_second_product_and_fail_after_writes(self):
  p=self.product('un');self.entry(p,'un',30);t=self.ticket()
  with self.assertRaises(self.pg.Error):self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':p,'quantidade':'20'},{'produto_id':99999999,'rolos':1,'quantidade':'1'}],self.user)
  self.assertEqual(self.balance(p),30)
  for unit in ('un','kg'):
   product=p if unit=='un' else self.product(unit)
   if unit!='un':self.entry(product,unit,30)
   before=self.balance(product);key=str(uuid4())
   with self.assertRaises(self.pg.Error):
    with self.pg.connect(**self.config) as conn,conn.cursor() as c:
     c.execute("CREATE FUNCTION public.fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'fixture'; END;$$")
     c.execute("CREATE TRIGGER fixture_fail AFTER INSERT ON public.movimentacoes FOR EACH ROW EXECUTE FUNCTION public.fixture_fail()")
     from psycopg2.extras import Json
     a=[] if unit=='un' else [self.alloc(self.lots(product)[0][0],1)]
     c.execute('SELECT fn_adicionar_item_corte(%s,%s,1,1,%s,%s,%s)',(t,product,Json(a),self.user,key))
   self.assertEqual(self.balance(product),before);self.assertEqual(self.query('SELECT count(*) FROM itens_ticket WHERE chave_corte=%s',(key,))[0][0],0)
 def test_concurrent_same_aggregate_and_same_piece(self):
  for unit in ('un','kg','m'):
   p=self.product(unit);self.entry(p,unit,10);tickets=[self.ticket(),self.ticket()];a=[] if unit=='un' else [self.alloc(self.lots(p)[0][0],7)]
   def attempt(t):
    try:self.cut(t,p,7,7,a);return True
    except self.pg.Error:return False
   with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,tickets))
   self.assertEqual(sorted(results),[False,True]);self.assertEqual(self.balance(p),3)
 def test_concurrent_same_keys_entry_and_cut(self):
  for unit in ('un','kg'):
   p=self.product(unit);key=str(uuid4())
   with ThreadPoolExecutor(2) as pool:ids=list(pool.map(lambda _:self.entry(p,unit,10,key=key),range(2)))
   self.assertEqual(ids[0],ids[1]);self.assertEqual(self.balance(p),10)
   t=self.ticket();key=str(uuid4());a=[] if unit=='un' else [self.alloc(self.lots(p)[0][0],2)]
   with ThreadPoolExecutor(2) as pool:ids=list(pool.map(lambda _:self.cut(t,p,2 if unit=='un' else 1,2,a,key),range(2)))
   self.assertEqual(ids[0],ids[1]);self.assertEqual(self.balance(p),8)
 def test_opposite_product_order_entries_and_price_cut(self):
  ps=[self.product('un'),self.product('kg')];groups=[{'produto_id':ps[0],'quantidade':10},{'produto_id':ps[1],'pecas':1,'quantidade':10}]
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda g:self.db.confirmar_ingresso(str(uuid4()),g,self.user),[groups,list(reversed(groups))]))
  self.assertEqual([self.balance(p) for p in ps],[20,20])
  t=self.ticket()
  with ThreadPoolExecutor(2) as pool:
   price=pool.submit(self.db.alterar_precos,dict(chave=str(uuid4()),alteracoes=[dict(produto_id=ps[0],anterior='12.50',novo='20.00')]),self.user)
   cut=pool.submit(self.cut,t,ps[0],1,1);price.result();item=cut.result()
  self.assertIn(self.query('SELECT preco_unitario FROM itens_ticket WHERE id=%s',(item,))[0][0],(Decimal('12.50'),Decimal(20)))
 def test_entry_waits_for_product_lock_then_withdrawal(self):
  p=self.product('un');self.entry(p,'un',10);t=self.ticket()
  with self.pg.connect(**self.config) as conn,conn.cursor() as c:
   c.execute('SELECT id FROM produtos WHERE id=%s FOR UPDATE',(p,))
   with ThreadPoolExecutor(2) as pool:
    entry=pool.submit(self.entry,p,'un',20);withdraw=pool.submit(self.cut,t,p,5,5)
    conn.commit();entry.result();withdraw.result()
  self.assertEqual(self.balance(p),25)
 def test_reconciliation_direct_tampering_and_unit_stability(self):
  p=self.product('un');self.entry(p,'un',30)
  for sql,args in [('UPDATE estoque_agregado SET quantidade_atual=31 WHERE produto_id=%s',(p,)),("UPDATE produtos SET unidade_medida='kg' WHERE id=%s",(p,))]:
   with self.assertRaises(self.pg.Error):self.query(sql,args)
  self.assertEqual(self.balance(p),30)
  with self.assertRaises(self.pg.Error):self.db.fetchone('UPDATE public.estoque_agregado SET quantidade_atual=0 WHERE produto_id=%s',(p,))
 def test_reinitialization_guard_preserves_structure(self):
  from pathlib import Path
  before=self.query('SELECT count(*) FROM produtos')[0][0]
  with self.pg.connect(**self.config) as conn,conn.cursor() as c:
   with self.assertRaises(self.pg.Error) as rejected:c.execute(Path('schema.sql').read_text(encoding='utf-8'))
   self.assertEqual(rejected.exception.pgcode,'P0001')
  self.assertEqual(self.query('SELECT count(*) FROM produtos')[0][0],before)
 def test_aggregate_total_exceeds_one_physical_capacity(self):
  p=self.product('un')
  for _ in range(3):self.entry(p,'un',500000000)
  self.assertEqual(self.balance(p),1500000000)
  self.assertEqual(self.query('SELECT saldo_reconstruido,diferenca FROM vw_reconciliacao_estoque WHERE produto_id=%s',(p,))[0],(1500000000,0))
 def test_install_empty_failure_rollback_destination_and_populated_guard(self):
  from app_loja.install_schema import initialize
  from pathlib import Path
  name='unidades_instalacion_'+uuid4().hex[:12]
  admin=self.pg.connect(**self.config);admin.autocommit=True
  try:
   with admin.cursor() as c:c.execute('CREATE DATABASE '+name)
  finally:admin.close()
  cfg={**self.config,'dbname':name}
  destination={'host':self.config['host']} if os.name=='nt' else {'socket':self.config['host']}
  with self.pg.connect(**cfg) as conn:
   with self.assertRaises(ValueError):initialize(conn,database='destino_incorrecto',port=self.config['port'],**destination)
   broken=Path('schema.sql').read_text(encoding='utf-8').replace('CREATE TABLE public.fotos_produto (',"DO $$BEGIN RAISE EXCEPTION 'fixture instalación'; END;$$;\nCREATE TABLE public.fotos_produto (")
   with self.assertRaises(self.pg.Error):initialize(conn,database=name,port=self.config['port'],**destination,source=broken)
   with conn.cursor() as c:
    c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'");self.assertEqual(c.fetchone()[0],0)
   conn.rollback()
   initialize(conn,database=name,port=self.config['port'],**destination)
   with self.assertRaises(ValueError):initialize(conn,database=name,port=self.config['port'],**destination)
  # A fixture de estrutura antiga incerta deve permanecer literalmente intacta.
  name2='unidades_guard_'+uuid4().hex[:12]
  admin=self.pg.connect(**self.config);admin.autocommit=True
  try:
   with admin.cursor() as c:c.execute('CREATE DATABASE '+name2)
  finally:admin.close()
  with self.pg.connect(**{**self.config,'dbname':name2}) as conn:
   with conn.cursor() as c:
    c.execute('CREATE TABLE legado(unidade text,quantidade numeric,origem text,saldo numeric)')
    c.execute("INSERT INTO legado VALUES('un',1.5,NULL,2),('kg',10,'desconocida',9)")
   conn.commit()
   with self.assertRaises(ValueError):initialize(conn,database=name2,port=self.config['port'],**destination)
   with conn.cursor() as c:
    c.execute('SELECT * FROM legado ORDER BY unidade');self.assertEqual(c.fetchall(),[('kg',Decimal(10),'desconocida',Decimal(9)),('un',Decimal('1.5'),None,Decimal(2))])
 def test_cut_payment_concurrency_mixed_no_second_withdrawal(self):
  p=self.product('un');self.entry(p,'un',10);t=self.ticket();self.cut(t,p,1,1);ticket,_,_=self.db.conferir_ticket(t)
  def payment():
   try:self.db.receber_ticket(dict(ticket_id=t,conferencia=ticket['conferencia'],efectivo=0),self.user);return True
   except self.pg.Error:return False
  def cut():
   try:self.cut(t,p,1,2);return True
   except self.pg.Error:return False
  with ThreadPoolExecutor(2) as pool:
   a=pool.submit(payment);b=pool.submit(cut);paid,withdrawn=a.result(),b.result()
  self.assertNotEqual(paid,withdrawn)
  self.assertEqual(self.balance(p),7 if withdrawn else 9)
 def test_replay_preserves_ingresso_key_after_back(self):
  p=self.product('un');result=self.post('/entrada/revisar',dict(produto_id=p,quantidade='30'));first=self.client.get(result.location);key=self.token(first,'chave')
  self.client.get(f'/entrada?produto_id={p}&editar=1')
  result=self.post('/entrada/revisar',dict(produto_id=p,quantidade='30'));second=self.client.get(result.location)
  self.assertEqual(self.token(second,'chave'),key)
 def test_new_ingresso_same_quantity_is_new_not_a_replay(self):
  p=self.product('un');result=self.post('/entrada/revisar',dict(produto_id=p,quantidade='30'));page=self.client.get(result.location);key=self.token(page,'chave')
  self.post('/entrada/confirmar',dict(chave=key))
  self.client.get(f'/entrada?produto_id={p}')
  result=self.post('/entrada/revisar',dict(produto_id=p,quantidade='30'));page=self.client.get(result.location);new=self.token(page,'chave')
  self.assertNotEqual(new,key);self.post('/entrada/confirmar',dict(chave=new));self.assertEqual(self.balance(p),60)
 def test_ingresso_injected_failure_after_writes_physical_and_aggregate(self):
  from psycopg2.extras import Json
  for unit in ('m','kg','un'):
   p=self.product(unit);key=str(uuid4());groups=[{'produto_id':p,'quantidade':'10'}]
   if unit!='un':groups[0]['rolos' if unit=='m' else 'pecas']=2
   with self.assertRaises(self.pg.Error):
    with self.pg.connect(**self.config) as conn,conn.cursor() as c:
     c.execute("CREATE FUNCTION public.fixture_fail_entry() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'fixture'; END;$$")
     c.execute('CREATE TRIGGER fixture_fail_entry AFTER INSERT ON movimentacoes FOR EACH ROW EXECUTE FUNCTION public.fixture_fail_entry()')
     c.execute('SELECT fn_confirmar_ingresso(%s,%s,%s)',(key,Json(groups),self.user))
   self.assertEqual(self.balance(p),0);self.assertEqual(self.lots(p),[])
   self.assertEqual(self.query('SELECT count(*) FROM ingressos WHERE chave_confirmacao=%s',(key,))[0][0],0)
   self.assertEqual(self.query('SELECT count(*) FROM itens_ingresso WHERE produto_id=%s',(p,))[0][0],0)
 def test_movement_reference_and_cardinality_tampering_rolled_back(self):
  p=self.product('un');self.entry(p,'un',30);t=self.ticket();item=self.cut(t,p,7,7)
  with self.assertRaises(self.pg.Error):
   self.query("UPDATE movimentacoes SET item_ingresso_id=(SELECT id FROM itens_ingresso WHERE produto_id=%s LIMIT 1) WHERE item_ticket_id=%s",(p,item))
  with self.assertRaises(self.pg.Error):
   self.query("INSERT INTO movimentacoes(produto_id,tipo,quantidade,referencia_tipo,referencia_id,usuario_id,item_ticket_id) VALUES(%s,'CORTE',7,'ticket',%s,%s,%s)",(p,t,self.user,item))
  self.assertEqual(self.balance(p),23);self.assertFalse(self.query('SELECT * FROM vw_reconciliacao_estoque WHERE diferenca<>0'))
 def test_precio_review_unit_and_filters_preserved(self):
  from unittest.mock import patch
  products=[self.product(u) for u in ('m','un','kg')]
  if True:  # Precios ya no pide PIN: el rol Administrador alcanza.
   page=self.client.get('/precios');envio=self.token(page,'envio')
   rows=self.db.fetchall('SELECT id,preco_unitario FROM produtos')
   fields={'envio':envio,**{'precio_'+str(r['id']):str(r['preco_unitario']).replace('.',',') for r in rows}}
   for p in products:fields['precio_'+str(p)]='15,00'
   review=self.post('/precios/revisar',fields);self.assertEqual(review.status_code,200)
   for unit in ('m','un','kg'):self.assertIn((' / '+unit).encode(),review.data)
 def test_invalidates_old_preparation_without_affecting_caja(self):
  from itsdangerous import URLSafeSerializer
  p=self.product('un');self.entry(p,'un',30);t=self.ticket()
  old=URLSafeSerializer(self.app.secret_key,salt='corte-ticket-1b-preparo').dumps({'chave':str(uuid4()),'usuario_id':self.user,'ticket_id':t,'produto_id':p})
  self.assertEqual(self.post(f'/tickets/{t}/corte/{p}/revisar',dict(preparo=old,quantidade_vendida='1',quantidade_cortada='1')).status_code,400)
  with self.client.session_transaction() as s:s['ingresso']={'chave':str(uuid4()),'produto_id':p,'grupos':[{'produto_id':p,'rolos':1,'quantidade':'30'}]}
  self.assertEqual(self.client.get('/entrada/conferir').status_code,302)
 def test_header_declaration_cannot_exist_without_effects(self):
  p=self.product('un')
  with self.assertRaises(self.pg.Error):
   self.query("INSERT INTO ingressos(chave_confirmacao,grupos_declarados,registrado_por) VALUES(%s,jsonb_build_array(jsonb_build_object('produto_id',%s,'unidade','un','quantidade',30)),%s)",(str(uuid4()),p,self.user))
  self.assertEqual(self.balance(p),0)
 def test_physical_declaration_matches_actual_allocations(self):
  p=self.product('kg');self.entry(p,'kg',10);t=self.ticket();lot=self.lots(p)[0][0];item=self.cut(t,p,1,2,[self.alloc(lot,2)])
  with self.assertRaises(self.pg.Error):self.query("UPDATE itens_ticket SET alocacoes_declaradas='[]' WHERE id=%s",(item,))
 def test_stock_views_expose_mode_without_fake_physical_attributes(self):
  for unit in ('m','un','kg'):
   p=self.product(unit);row=self.db.fetchone('SELECT * FROM vw_estoque_por_produto WHERE produto_id=%s',(p,))
   self.assertEqual(row['modo'],'agregado' if unit=='un' else 'fisico')
   if unit=='un':
    self.assertIsNone(row['maior_lote_disponivel']);self.assertIsNone(row['rolos_abertos']);self.assertIsNone(row['rolos_fechados'])
    self.assertEqual(self.db.fetchall('SELECT * FROM vw_lotes_disponiveis WHERE produto_id=%s',(p,)),[])

 def test_un_single_quantity_persistence_and_privileged_update(self):
  p=self.product('un');self.entry(p,'un',30);t=self.ticket();url=f'/tickets/{t}/corte/{p}'
  page=self.client.get(url);prep=self.token(page,'preparo')
  self.assertIn(b'name="quantidade"',page.data)
  for field in ('quantidade_vendida','quantidade_cortada'):
   self.assertNotIn(('name="'+field+'"').encode(),page.data)
   forged=self.post(url+'/revisar',dict(preparo=prep,quantidade='7',**{field:'7'}))
   self.assertEqual(forged.status_code,400);self.assertIn(b'solamente',forged.data)
  for q in ('','-1','0','1,5'):
   self.assertEqual(self.post(url+'/revisar',dict(preparo=prep,quantidade=q)).status_code,400)
  review=self.post(url+'/revisar',dict(preparo=prep,quantidade='7'))
  self.assertEqual(review.status_code,200);self.assertNotIn(b'Diferencia',review.data);self.assertNotIn(b'Cantidad vendida',review.data)
  self.assertIn(b'87,50',review.data)
  envio=self.token(review,'envio');self.assertEqual(self.post(f'/tickets/{t}/corte/confirmar',dict(envio=envio,realizado='si')).status_code,302)
  self.assertEqual(self.query('SELECT quantidade_vendida,quantidade_cortada,valor_total FROM itens_ticket WHERE ticket_id=%s',(t,))[0],(7,7,Decimal('87.50')))
  self.assertEqual(self.balance(p),23)
  with self.assertRaises(self.pg.Error):self.query('UPDATE itens_ticket SET quantidade_vendida=8 WHERE ticket_id=%s',(t,))
  with self.assertRaises(self.pg.Error):
   self.query('INSERT INTO itens_ticket(ticket_id,produto_id,quantidade_vendida,quantidade_cortada,preco_unitario,chave_corte,alocacoes_declaradas,cortado_por) VALUES(%s,%s,8,7,12.50,%s,%s,%s)',(t,p,str(uuid4()),'[]',self.user))
  self.assertEqual(self.query('SELECT quantidade_vendida FROM itens_ticket WHERE ticket_id=%s',(t,))[0][0],7)
  self.assertEqual(self.balance(p),23)
  for route in (f'/tickets/{t}',f'/tickets/{t}/productos',f'/caixa/tickets/{t}'):
   response=self.client.get(route);self.assertEqual(response.status_code,200)
   self.assertNotIn(b'Diferencia',response.data);self.assertNotIn(b'Cantidad vendida',response.data)
