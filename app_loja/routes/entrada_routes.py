from decimal import Decimal
from uuid import uuid4

from flask import Response, Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from .. import db
from ..validation import groups_input, product_input
from ..photos import validate_photo
from ..search import ACCENTED, PLAIN, normalize_search

entrada_bp = Blueprint('entrada', __name__)


def categories():
    return db.fetchall('SELECT id,nome FROM public.tipos_tela ORDER BY nome')


def product(produto_id):
    row = db.fetchone('''SELECT v.*,p.quantidade_padrao_lote,EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=v.produto_id) AS tem_foto
        FROM public.vw_estoque_por_produto AS v
        JOIN public.produtos AS p ON p.id=v.produto_id WHERE v.produto_id=%s''', (produto_id,))
    if not row or not row['ativo']:
        abort(404)
    return row


@entrada_bp.get('/stock')
def stock():
    search = request.args.get('q', '').strip()
    category = request.args.getlist('categoria')[-1] if 'categoria' in request.args else ''
    try:
        category_id = int(category) if category else None
    except ValueError:
        abort(400)
    rows = db.fetchall('''
        SELECT v.*,EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=v.produto_id) AS tem_foto FROM public.vw_estoque_por_produto AS v
        JOIN public.produtos AS p ON p.id=v.produto_id
        WHERE p.ativo AND (translate(lower(p.nome),%s,%s) ILIKE %s
          OR translate(lower(v.tipo),%s,%s) ILIKE %s)
          AND (%s::bigint IS NULL OR p.tipo_id=%s)
        ORDER BY v.tipo,v.produto
    ''', (ACCENTED, PLAIN, f'%{normalize_search(search)}%',
          ACCENTED, PLAIN, f'%{normalize_search(search)}%', category_id, category_id))
    return render_template('stock.html', produtos=rows, categorias=categories(), q=search, categoria=category)


@entrada_bp.route('/productos/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if request.method == 'POST':
        try:
            data = product_input(request.form)
            foto = validate_photo(request.files.get('foto'))
            if data['tipo_id'] not in {row['id'] for row in categories()}:
                raise ValueError('Elegí una categoría válida.')
        except ValueError as error:
            flash(str(error), 'erro')
        else:
            produto_id = db.cadastrar_produto(data, g.usuario['id'],foto)
            flash('Producto creado. Ya podés ingresar stock.', 'sucesso')
            return redirect(url_for('entrada.index', produto_id=produto_id))
    return render_template('producto.html', categorias=categories(), values=request.form)


@entrada_bp.get('/productos/<int:produto_id>')
@db.read_snapshot
def detalle(produto_id):
    row = product(produto_id)
    lots = db.fetchall('''
        SELECT l.id,l.codigo_interno,l.quantidade_inicial,l.quantidade_atual,
               l.status_operacional,i.id AS ingresso_id,i.registrado_em,
               ii.quantidade AS declarada,u.nome AS registrado_por
        FROM public.estoque_lotes AS l
        JOIN public.itens_ingresso AS ii ON ii.id=l.item_ingresso_id
        JOIN public.ingressos AS i ON i.id=ii.ingresso_id
        JOIN public.vw_usuarios AS u ON u.id=i.registrado_por
        WHERE l.produto_id=%s ORDER BY l.id DESC
    ''', (produto_id,))
    history=db.fetchall('SELECT h.*,l.codigo_interno FROM public.vw_historico_produto h LEFT JOIN public.estoque_lotes l ON l.id=h.lote_id WHERE h.produto_id=%s ORDER BY h.id',(produto_id,))
    return render_template('detalle.html', produto=row, lotes=lots,historico=history)


@entrada_bp.get('/entrada')
def index():
    produto_id = request.args.get('produto_id', type=int)
    if not produto_id:
        return redirect(url_for('entrada.stock'))
    saved=session.get('ingresso',{})
    if saved:
        saved={**saved,'editando':bool(request.args.get('editar'))}
        session['ingresso']=saved
    draft = saved if request.args.get('editar') else {}
    groups = draft.get('grupos', []) if draft.get('produto_id') == produto_id else []
    return render_template('entrada.html', produto=product(produto_id), grupos=groups)


@entrada_bp.post('/entrada/revisar')
def revisar():
    try:
        produto_id = int(request.form.get('produto_id', ''))
        row = product(produto_id)
        groups = groups_input(produto_id, request.form.getlist('pecas' if row['unidade_medida']=='kg' else 'rolos'), request.form.getlist('quantidade'),row['unidade_medida'])
    except ValueError as error:
        raw_id = request.form.get('produto_id', '')
        # isdigit() acepta dígitos Unicode que int() rechaza; exigir ASCII.
        if not (raw_id.isascii() and raw_id.isdigit()):
            abort(400)
        flash(str(error), 'erro')
        row = product(int(raw_id))
        if row['unidade_medida'] == 'un':
            groups = [{'quantidade': request.form.get('quantidade', '')}]
        else:
            counts = request.form.getlist('pecas' if row['unidade_medida'] == 'kg' else 'rolos')
            groups = [{'rolos': r, 'pecas': r, 'quantidade': q}
                      for r, q in zip(counts, request.form.getlist('quantidade'))]
        return render_template('entrada.html', produto=row, grupos=groups), 400
    previous=session.get('ingresso',{})
    key=previous['chave'] if previous.get('editando') and previous.get('versao')==2 and previous.get('produto_id')==produto_id and previous.get('grupos')==groups else str(uuid4())
    session['ingresso'] = {'versao':2,'chave': key, 'produto_id': produto_id, 'grupos': groups}
    return redirect(url_for('entrada.conferir'))


@entrada_bp.get('/entrada/conferir')
@db.read_snapshot
def conferir():
    draft = session.get('ingresso')
    if not draft or draft.get('versao')!=2:
        return redirect(url_for('entrada.stock'))
    total = sum(Decimal(group['quantidade']) * group.get('rolos',group.get('pecas',1)) for group in draft['grupos'])
    count = sum(group.get('rolos',group.get('pecas',1)) for group in draft['grupos'])
    return render_template('conferir.html', draft=draft, produto=product(draft['produto_id']),
                           total=total, roll_count=count)


@entrada_bp.post('/entrada/confirmar')
def confirmar():
    draft = session.get('ingresso')
    if not draft or draft.get('versao')!=2 or request.form.get('chave') != draft['chave']:
        abort(400)
    ingresso_id = db.confirmar_ingresso(draft['chave'], draft['grupos'], g.usuario['id'])
    # Mantener la clave hasta otro borrador permite reintentar sin duplicar.
    return redirect(url_for('entrada.ingresso', ingresso_id=ingresso_id))


@entrada_bp.get('/ingresos/<int:ingresso_id>')
def ingresso(ingresso_id):
    lots = db.fetchall('''
        SELECT l.codigo_interno,ii.quantidade,p.id AS produto_id,p.nome,p.unidade_medida,
               EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=p.id) AS tem_foto,
               i.registrado_em,u.nome AS registrado_por
        FROM public.ingressos AS i
        JOIN public.itens_ingresso AS ii ON ii.ingresso_id=i.id
        LEFT JOIN public.estoque_lotes AS l ON l.item_ingresso_id=ii.id
        JOIN public.produtos AS p ON p.id=ii.produto_id
        JOIN public.vw_usuarios AS u ON u.id=i.registrado_por
        WHERE i.id=%s ORDER BY ii.id
    ''', (ingresso_id,))
    if not lots:
        abort(404)
    return render_template('ingreso.html', ingresso_id=ingresso_id, lotes=lots)


@entrada_bp.route('/productos/<int:produto_id>/foto',methods=['GET','POST'])
def foto(produto_id):
    if request.method=='POST':
        product(produto_id)
        try:
            image = validate_photo(request.files.get('foto'))
            if image is None:
                raise ValueError('Seleccioná o pegá una foto antes de guardar.')
            db.guardar_foto(produto_id,image)
            flash('Foto guardada.','sucesso')
        except ValueError as error:
            flash(str(error),'erro')
        return redirect(url_for('entrada.detalle',produto_id=produto_id),303)
    row = db.fetchone('SELECT imagem,mime FROM public.fotos_produto WHERE produto_id=%s',(produto_id,))
    if row is None:
        abort(404)
    return Response(bytes(row['imagem']),content_type=row['mime'],headers={'X-Content-Type-Options':'nosniff'})


@entrada_bp.get('/productos/<int:produto_id>/foto/miniatura')
def miniatura(produto_id):
    row = db.fetchone('SELECT miniatura,mime FROM public.fotos_produto WHERE produto_id=%s',(produto_id,))
    if row is None:
        abort(404)
    return Response(bytes(row['miniatura']),content_type=row['mime'],headers={'X-Content-Type-Options':'nosniff'})
