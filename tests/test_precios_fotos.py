"""Precios protegidos y fotos: integridad real, reenvío y validación de contenido."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import os
import re
import unittest
from decimal import Decimal
from uuid import uuid4
from PIL import Image
from werkzeug.datastructures import FileStorage
from app_loja.photos import validate_photo


def image_bytes(color='blue',fmt='PNG',size=(360,180)):
    output=BytesIO()
    Image.new('RGB',size,color).save(output,format=fmt)
    return output.getvalue()


class PhotoValidationTests(unittest.TestCase):
    def test_content_not_filename_metadata_and_thumbnail(self):
        raw=image_bytes()
        foto=validate_photo(FileStorage(stream=BytesIO(raw),filename='../../wrong.svg',content_type='text/plain'))
        self.assertEqual((foto['largura'],foto['altura']),(360,180))
        for field,size in (('imagem',(360,180)),('miniatura',(240,120))):
            with Image.open(BytesIO(foto[field])) as image:
                self.assertEqual(image.size,size)
                self.assertEqual(image.info.get('exif'),None)
        self.assertIsNone(validate_photo(None))

    def test_exif_orientation_and_personal_metadata_are_discarded(self):
        source=Image.new('RGB',(360,180),'blue')
        exif=Image.Exif()
        exif[274]=6
        exif[270]='private fixture metadata'
        output=BytesIO()
        source.save(output,format='JPEG',exif=exif)
        foto=validate_photo(FileStorage(stream=BytesIO(output.getvalue()),filename='photo.jpg'))
        self.assertEqual((foto['largura'],foto['altura']),(180,360))
        for key in ('imagem','miniatura'):
            with Image.open(BytesIO(foto[key])) as image:
                self.assertFalse(image.getexif())
                self.assertNotIn(b'private fixture metadata',foto[key])

    def test_invalid_formats_dimensions_bytes_and_animation(self):
        for raw in (b'<svg>active</svg>',b'not image',image_bytes(fmt='GIF'),image_bytes(size=(4097,1)),
                    image_bytes(size=(4000,4000)),b'x'*(5*1024*1024+1)):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):
                validate_photo(FileStorage(stream=BytesIO(raw),filename='photo.png',content_type='image/png'))
        for fmt in ('JPEG','PNG','WEBP'):
            foto=validate_photo(FileStorage(stream=BytesIO(image_bytes(fmt=fmt)),filename='photo'))
            self.assertTrue(foto['imagem'])


@unittest.skipUnless(os.getenv('LOJA_TEST_DB')=='1','Requiere PostgreSQL descartable')
class PreciosFotosIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from app_loja import db
        from app_loja.run import create_app
        cls.pg=psycopg2
        cls.admin_config=dict(host=os.environ['PGHOST'],port=os.environ['PGPORT'],dbname=os.environ['PGDATABASE'],user=os.environ['PGUSER'])
        cls.operator_config={**cls.admin_config,'user':'loja_test_precios'}
        cls.db=db
        cls.original=db.DB_CONFIG
        conn=psycopg2.connect(**cls.admin_config)
        with conn,conn.cursor() as c:
            c.execute('CREATE ROLE loja_test_precios LOGIN')
            c.execute('GRANT loja_operador TO loja_test_precios')
            c.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES('Operación','precios_fixture',public.crypt('fixture-only',public.gen_salt('bf')),'admin') RETURNING id")
            cls.user=c.fetchone()[0]
            cls.roles={}
            for perfil in ('empleado','cajero'):
                c.execute("INSERT INTO public.usuarios(nome,login,senha_hash,perfil) VALUES(%s,%s,public.crypt('fixture-only',public.gen_salt('bf')),%s) RETURNING id",(perfil,'precios_'+perfil,perfil))
                cls.roles[perfil]=c.fetchone()[0]
        conn.close()
        db.DB_CONFIG=cls.operator_config
        cls.app=create_app({'TESTING':True,'SECRET_KEY':'fixture-precios'})

    @classmethod
    def tearDownClass(cls):
        cls.db.DB_CONFIG=cls.original

    def query(self,sql,args=()):
        conn=self.pg.connect(**self.admin_config)
        try:
            with conn,conn.cursor() as c:
                c.execute(sql,args)
                return c.fetchall() if c.description else None
        finally:
            conn.close()

    def post(self,path,data):
        with self.client.session_transaction() as s:
            data={**data,'csrf':s['csrf']}
        return self.client.post(path,data=data)

    def token(self,response):
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        return re.search('name="envio" value="([^"]+)"',response.get_data(as_text=True)).group(1)

    def setUp(self):
        self.client=self.app.test_client()
        self.client.get('/login')
        self.post('/login',{'login':'precios_fixture','senha':'fixture-only'})
        self.client.get('/stock')
        self.products=[self.db.cadastrar_produto({'tipo_id':1,'nome':'Foto '+str(uuid4()),'unidade':'m','preco':Decimal('12.50'),'largura':None,'padrao':None},self.user) for _ in range(2)]

    def unlock(self):
        pass  # Precios ya no pide PIN: alcanza con el rol Administrador.

    def changes(self):
        return [{'produto_id':p,'anterior':'12.50','novo':str(20+i)} for i,p in enumerate(self.products)]

    def test_categories_keep_all_inputs_and_hidden_price_changes_in_review(self):
        category=self.query('INSERT INTO tipos_tela(nome) VALUES(%s) RETURNING id',('Mercería '+str(uuid4()),))[0][0]
        self.query('UPDATE produtos SET tipo_id=%s WHERE id=%s',(category,self.products[1]))
        self.unlock()
        initial=self.client.get('/precios')
        text=initial.get_data(as_text=True)
        self.assertIn(f'data-category="{category}"',text)
        self.assertIn('data-category="" aria-pressed="true"',text)
        self.assertNotIn('<select',text)
        for pid in self.products:
            self.assertIn(f'name="precio_{pid}"',text)
        fields={'envio':self.token(initial),**{'precio_'+str(pid):str(price)
            for pid,price in self.query('SELECT id,preco_unitario FROM produtos')}}
        fields['precio_'+str(self.products[0])]='20'
        fields['precio_'+str(self.products[1])]='21'
        # El filtro solo oculta filas: ambos valores forman parte del envío/revisión.
        review=self.post('/precios/revisar',fields)
        self.assertEqual(review.get_data(as_text=True).count('<tr><td>'),2)
        self.assertEqual(self.post('/precios/confirmar',{'envio':self.token(review),'confirmado':'si'}).status_code,303)
        self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=ANY(%s) ORDER BY id',
            (self.products,)),[(Decimal(20),),(Decimal(21),)])

    def test_protected_price_edit_es_ar_thousands_review_and_persistence(self):
        self.unlock()
        for raw,expected,shown in (('12500','12500','12.500,00'),('12.500','12500','12.500,00'),
            ('12.500,50','12500.50','12.500,50'),('12500,50','12500.50','12.500,50')):
            with self.subTest(raw=raw):
                pid=self.db.cadastrar_produto({'tipo_id':1,'nome':'Precio QA '+str(uuid4()),'unidade':'m',
                    'preco':Decimal('10'),'largura':None,'padrao':None},self.user)
                initial=self.token(self.client.get('/precios'))
                fields={'envio':initial,**{'precio_'+str(product):str(price)
                    for product,price in self.query('SELECT id,preco_unitario FROM produtos')}}
                review=self.post('/precios/revisar',{**fields,'precio_'+str(pid):raw})
                self.assertIn(shown,review.get_data(as_text=True))
                self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=%s',(pid,))[0][0],Decimal('10'))
                self.assertEqual(self.post('/precios/confirmar',{'envio':self.token(review),'confirmado':'si'}).status_code,303)
                self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=%s',(pid,))[0][0],Decimal(expected))
                self.assertEqual(self.query('SELECT preco_anterior,preco_novo FROM historico_precos WHERE produto_id=%s',
                    (pid,)),[(Decimal('10'),Decimal(expected))])

    def test_batch_history_retry_concurrency_frozen_and_permissions(self):
        ticket=self.db.iniciar_ticket(str(uuid4()),self.user)
        self.db.confirmar_ingresso(str(uuid4()),[{'produto_id':self.products[0],'rolos':1,'quantidade':'30'}],self.user)
        lot=self.query('SELECT id FROM estoque_lotes WHERE produto_id=%s',(self.products[0],))[0][0]
        self.db.registrar_corte({'ticket_id':ticket,'produto_id':self.products[0],'quantidade_vendida':'1','quantidade_cortada':'2','chave':str(uuid4()),'alocacoes':[{'lote_id':lot,'quantidade':'2'}]},self.user)
        value={'chave':str(uuid4()),'alteracoes':self.changes()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.db.alterar_precos(value,self.user),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.query('SELECT preco_anterior,preco_novo FROM historico_precos WHERE lote_id=%s ORDER BY produto_id',(results[0],)),[(Decimal('12.50'),Decimal('20')),(Decimal('12.50'),Decimal('21'))])
        self.assertEqual(self.query('SELECT preco_unitario FROM itens_ticket WHERE ticket_id=%s',(ticket,))[0][0],Decimal('12.50'))
        with self.assertRaises(self.pg.Error):
            with self.db.transaction() as cursor:
                cursor.execute('UPDATE produtos SET preco_unitario=1 WHERE id=%s',(self.products[0],))
        with self.assertRaises(self.pg.Error):
            self.db.alterar_precos({**value,'alteracoes':[{'produto_id':self.products[0],'anterior':'20','novo':'30'}]},self.user)

    def test_stale_and_storage_failure_leave_no_partial_batch(self):
        changes=self.changes()
        changes[-1]['anterior']='99'
        with self.assertRaises(self.pg.Error):
            self.db.alterar_precos({'chave':str(uuid4()),'alteracoes':changes},self.user)
        self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=ANY(%s)',(self.products,)),[(Decimal('12.50'),)]*2)
        self.query("CREATE FUNCTION public.fixture_price_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture'; END $$")
        self.query('CREATE TRIGGER fixture_price_failure BEFORE INSERT ON historico_precos FOR EACH ROW EXECUTE FUNCTION public.fixture_price_failure()')
        key=str(uuid4())
        try:
            with self.assertRaises(self.pg.Error):
                self.db.alterar_precos({'chave':key,'alteracoes':self.changes()},self.user)
            self.assertEqual(self.query('SELECT count(*) FROM lotes_precos WHERE chave=%s',(key,))[0][0],0)
            self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=ANY(%s)',(self.products,)),[(Decimal('12.50'),)]*2)
        finally:
            self.query('DROP TRIGGER fixture_price_failure ON historico_precos')
            self.query('DROP FUNCTION fixture_price_failure()')
        self.db.alterar_precos({'chave':key,'alteracoes':self.changes()},self.user)

    def test_admin_review_only_modified_edit_and_resend(self):
        self.assertNotIn('name="pin"',self.client.get('/precios').get_data(as_text=True))
        initial=self.token(self.client.get('/precios'))
        data={'envio':initial}
        for pid,price in self.query('SELECT id,preco_unitario FROM produtos'):
            data['precio_'+str(pid)]=str(price)
        data['precio_'+str(self.products[0])]='25,75'
        reviewed=self.post('/precios/revisar',data)
        final=self.token(reviewed)
        self.assertEqual(reviewed.get_data(as_text=True).count('<tr><td>'),1)
        self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=%s',(self.products[0],))[0][0],Decimal('12.50'))
        corrected=self.post('/precios/editar',{'envio':final})
        self.assertIn('value="25,75"',corrected.get_data(as_text=True))
        for _ in range(2):
            self.assertEqual(self.post('/precios/confirmar',{'envio':final,'confirmado':'si'}).status_code,303)
        self.assertEqual(self.query('SELECT count(*) FROM historico_precos WHERE produto_id=%s',(self.products[0],))[0][0],1)
        # Salir y reenviar el mismo lote sigue siendo idempotente.
        self.client.get('/stock')
        self.assertEqual(self.post('/precios/confirmar',{'envio':final,'confirmado':'si'}).status_code,303)
        self.assertEqual(self.query('SELECT count(*) FROM historico_precos WHERE produto_id=%s',(self.products[0],))[0][0],1)

    def test_only_administrador_reaches_precios_by_url_form_or_database(self):
        valid=self.token(self.client.get('/precios'))
        for perfil in ('empleado','cajero'):
            client=self.app.test_client()
            client.get('/login')
            with client.session_transaction() as s:
                csrf=s['csrf']
            self.assertEqual(client.post('/login',data={'csrf':csrf,'login':'precios_'+perfil,'senha':'fixture-only'}).status_code,302)
            client.get('/tickets')
            with client.session_transaction() as s:
                csrf=s['csrf']
            self.assertEqual(client.get('/precios').status_code,403)
            self.assertNotIn('Precios',client.get('/tickets').get_data(as_text=True))
            for path in ('/precios/revisar','/precios/confirmar','/precios/editar'):
                self.assertEqual(client.post(path,data={'csrf':csrf,'envio':valid,'confirmado':'si'}).status_code,403)
            # Segunda barrera: el banco rechaza el rol.
            with self.assertRaises(self.pg.Error) as denied:
                self.db.alterar_precos({'chave':str(uuid4()),'alteracoes':self.changes()},self.roles[perfil])
            self.assertEqual(denied.exception.pgcode,'42501')
        self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=ANY(%s)',(self.products,)),[(Decimal('12.50'),)]*2)

    def test_migration_preserves_existing_products_and_tickets(self):
        root=Path(__file__).resolve().parents[1]
        name='loja_migration_'+uuid4().hex
        admin=self.pg.connect(**self.admin_config)
        admin.autocommit=True
        try:
            with admin.cursor() as c:
                c.execute('CREATE DATABASE '+name)
            conn=self.pg.connect(**{**self.admin_config,'dbname':name})
            conn.autocommit=True
            try:
                with conn.cursor() as c:
                    c.execute((root/'schema.sql').read_text(encoding='utf-8').split('-- Extensão Precios / foto principal.')[0])
                    c.execute("INSERT INTO tipos_tela(nome) VALUES('Fixture')")
                    c.execute("INSERT INTO usuarios(nome,login,senha_hash,perfil) VALUES('Fixture','fixture','unused-fixture','admin')")
                    c.execute("SELECT fn_cadastrar_produto(1,'Existing fixture','m',12.50,1,NULL,NULL)")
                    c.execute('SELECT fn_iniciar_ticket(%s,1)',(str(uuid4()),))
                    c.execute('SELECT id,nome,preco_unitario,criado_em FROM produtos')
                    products=c.fetchall()
                    c.execute('SELECT * FROM tickets')
                    tickets=c.fetchall()
                    c.execute((root/'migrations/001_precios_fotos.sql').read_text(encoding='utf-8'))
                    c.execute('SELECT id,nome,preco_unitario,criado_em FROM produtos')
                    self.assertEqual(c.fetchall(),products)
                    c.execute('SELECT * FROM tickets')
                    self.assertEqual(c.fetchall(),tickets)
                    c.execute('SELECT count(*) FROM fotos_produto')
                    self.assertEqual(c.fetchone()[0],0)
            finally:
                conn.close()
        finally:
            with admin.cursor() as c:
                c.execute('DROP DATABASE '+name)
            admin.close()

    def test_invalid_price_inputs_signature_csrf_and_history_timestamp(self):
        self.unlock()
        token=self.token(self.client.get('/precios'))
        fields={'envio':token,**{'precio_'+str(pid):str(price) for pid,price in self.query('SELECT id,preco_unitario FROM produtos')}}
        for invalid in ('','-1','NaN','1,123','10000000000'):
            response=self.post('/precios/revisar',{**fields,'precio_'+str(self.products[0]):invalid})
            self.assertEqual(response.status_code,400)
            self.assertIn('precio válido',response.get_data(as_text=True))
        self.assertEqual(self.post('/precios/revisar',{**fields,'envio':token+'x'}).status_code,400)
        self.assertEqual(self.client.post('/precios/revisar',data=fields).status_code,400)
        self.assertEqual(self.query('SELECT count(*) FROM historico_precos WHERE produto_id=ANY(%s)',(self.products,))[0][0],0)
        self.assertEqual(self.post('/precios/revisar',fields).status_code,400)
        value={'chave':str(uuid4()),'alteracoes':self.changes()[:1]}
        batch=self.db.alterar_precos(value,self.user)
        self.assertEqual(self.query('SELECT count(*) FROM historico_precos h JOIN lotes_precos l ON l.id=h.lote_id WHERE h.lote_id=%s AND h.registrado_em=l.registrado_em AND l.registrado_por=%s',(batch,self.user))[0][0],1)

    def upload(self,pid,raw,name='../../image.png'):
        return self.post(f'/productos/{pid}/foto',{'foto':(BytesIO(raw),name)})

    def test_upload_replace_invalid_missing_thumbnail_assets_and_no_photo(self):
        pid=self.products[0]
        self.assertEqual(self.client.get(f'/productos/{pid}/foto').status_code,404)
        self.assertNotIn('data-foto=',self.client.get(f'/productos/{pid}').get_data(as_text=True))
        self.assertEqual(self.upload(pid,image_bytes()).status_code,303)
        previous=self.query('SELECT imagem,atualizado_em FROM fotos_produto WHERE produto_id=%s',(pid,))[0]
        self.upload(pid,b'invalid','image.jpeg')
        self.assertEqual(self.query('SELECT imagem,atualizado_em FROM fotos_produto WHERE produto_id=%s',(pid,))[0],previous)
        self.upload(pid,image_bytes())
        self.assertEqual(self.query('SELECT imagem,atualizado_em FROM fotos_produto WHERE produto_id=%s',(pid,))[0],previous)
        self.unlock()
        principal=self.client.get(f'/productos/{pid}/foto')
        thumb=self.client.get(f'/productos/{pid}/foto/miniatura')
        self.assertEqual(principal.headers['X-Content-Type-Options'],'nosniff')
        with Image.open(BytesIO(thumb.data)) as image:
            self.assertEqual(image.size,(240,120))
        self.assertEqual(self.client.get('/precios').status_code,200)
        self.upload(pid,image_bytes('red'))
        self.assertNotEqual(self.query('SELECT imagem FROM fotos_produto WHERE produto_id=%s',(pid,))[0][0],previous[0])
        self.assertEqual(self.query('SELECT count(*) FROM fotos_produto WHERE produto_id=%s',(pid,))[0][0],1)
        self.assertIn('data-foto=',self.client.get('/stock').get_data(as_text=True))
        self.assertEqual(self.client.get('/precios').status_code,200)

    def test_new_product_photo_transaction_and_existing_price_untouched(self):
        fields={'nome':'Nuevo foto '+str(uuid4()),'tipo_id':'1','unidade':'m','preco':'22','largura':'','padrao':''}
        response=self.post('/productos/nuevo',{**fields,'foto':(BytesIO(image_bytes()),'clipboard.png')})
        self.assertEqual(response.status_code,302)
        pid=self.query('SELECT id FROM produtos WHERE nome=%s',(fields['nome'],))[0][0]
        self.assertEqual(self.query('SELECT count(*) FROM fotos_produto WHERE produto_id=%s',(pid,))[0][0],1)
        self.upload(pid,image_bytes('red'))
        self.assertEqual(self.query('SELECT preco_unitario FROM produtos WHERE id=%s',(pid,))[0][0],Decimal('22'))
        bad={**fields,'nome':'Invalid '+str(uuid4())}
        self.assertEqual(self.post('/productos/nuevo',{**bad,'foto':(BytesIO(b'invalid'),'image.png')}).status_code,200)
        self.assertEqual(self.query('SELECT count(*) FROM produtos WHERE nome=%s',(bad['nome'],))[0][0],0)
        invalid=validate_photo(FileStorage(stream=BytesIO(image_bytes()),filename='valid.png'))
        invalid['miniatura']=b''
        with self.assertRaises(self.pg.Error):
            self.db.cadastrar_produto({ 'nome':bad['nome'],'tipo_id':1,'unidade':'m','preco':Decimal('1'),'largura':None,'padrao':None},self.user,invalid)
        self.assertEqual(self.query('SELECT count(*) FROM produtos WHERE nome=%s',(bad['nome'],))[0][0],0)
        before=self.query('SELECT imagem FROM fotos_produto WHERE produto_id=%s',(pid,))[0][0]
        with self.assertRaises(self.pg.Error):
            self.db.guardar_foto(pid,invalid)
        self.assertEqual(self.query('SELECT imagem FROM fotos_produto WHERE produto_id=%s',(pid,))[0][0],before)


class ExtensionLayoutTests(unittest.TestCase):
    def test_initializer_and_additive_migration_are_identical(self):
        root=Path(__file__).resolve().parents[1]
        extension=(root/'schema.sql').read_text(encoding='utf-8').split('-- Extensão Precios / foto principal. Mesmo conteúdo da migração aditiva.\n')[1]
        migration=(root/'migrations/001_precios_fotos.sql').read_text(encoding='utf-8')
        # Mismo contrato, integrado ahora en una única instalación transaccional.
        self.assertEqual(extension[extension.index('CREATE TABLE'):],migration[migration.index('CREATE TABLE'):])
