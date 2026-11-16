from decimal import Decimal
from uuid import uuid4

import psycopg2
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import db
from ..corte import allocation_input, seal, suggestion, unseal
from ..validation import quantity_input
from ..search import ACCENTED, PLAIN, normalize_search
from .entrada_routes import categories, product
from .ticket_routes import get_items, get_ticket

corte_bp = Blueprint('corte',__name__)


def available_lots(produto_id, quantity):
    return db.fetchall('''SELECT * FROM public.vw_lotes_disponiveis
        WHERE produto_id=%s AND quantidade_atual>0 AND condicao_fisica='normal'
        ORDER BY (status_operacional='aberto') DESC,
            (quantidade_atual >= %s) DESC,quantidade_atual,lote_id''', (produto_id,quantity))


def pending(ticket_id):
    ticket = get_ticket(ticket_id)
    if ticket['status']!='pendente':
        abort(400)
    return ticket


def search_context(values):
    return {'q':values.get('q','').strip(),'categoria':values.get('categoria','')}


def quantities(values, unit):
    if unit == 'un':
        if 'quantidade_vendida' in values or 'quantidade_cortada' in values:
            raise ValueError('Unidades: informá solamente Cantidad (un).')
        quantity = quantity_input(values.get('quantidade'), 'Cantidad', unit)
        return quantity, quantity
    return (quantity_input(values.get('quantidade_vendida'), 'Cantidad vendida', unit),
            quantity_input(values.get('quantidade_cortada'), 'Cantidad retirada', unit))


def entered_allocations(values):
    result = {}
    for lot_id,amount in zip(values.getlist('lote_id'),values.getlist('retirar')):
        try:
            result[int(lot_id)] = amount
        except ValueError:
            continue
    return result


def selection_page(ticket,row,sold,cut,restored,preparation,search,*,error=None,partial=False):
    lots = [] if row['unidade_medida']=='un' else available_lots(row['produto_id'],cut or Decimal(0))
    selected = suggestion(lots,cut) if sold and cut and not error else None
    if restored:
        missing = sorted(set(restored)-{lot['lote_id'] for lot in lots})
        if missing:
            lots.extend(db.fetchall('''SELECT id AS lote_id,codigo_interno,quantidade_atual,status_operacional
                FROM public.estoque_lotes WHERE produto_id=%s AND id=ANY(%s) ORDER BY id''',
                (row['produto_id'],missing)))
            error = error or 'Un origen físico ya no está disponible. Revisá la distribución.'
    values = request.form if request.method=='POST' else request.args
    context = dict(ticket=ticket,produto=row,lotes=lots,sugerido=selected,restauradas=restored,
        quantidade=values.get('quantidade','') if sold is None else str(sold).replace('.',','),
        quantidade_vendida=values.get('quantidade_vendida','') if sold is None else str(sold).replace('.',','),
        quantidade_cortada=values.get('quantidade_cortada','') if cut is None else str(cut).replace('.',','),
        preparo=preparation,busca=search,erro=error,
        mostrar_lotes=bool(sold and cut) or restored is not None)
    if partial:
        return render_template('corte_lotes.html',**context),400 if error else 200
    return render_template('corte.html',**context,itens_registrados=get_items(ticket['id'])),400 if error else 200


@corte_bp.get('/tickets/<int:ticket_id>/productos')
def productos(ticket_id):
    ticket = pending(ticket_id)
    search = request.args.get('q','').strip()
    category = request.args.getlist('categoria')[-1] if 'categoria' in request.args else ''
    try:
        category_id = int(category) if category else None
    except ValueError:
        abort(400)
    products = db.fetchall('''SELECT v.*,EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=v.produto_id) AS tem_foto FROM public.vw_estoque_por_produto v
        JOIN public.produtos p ON p.id=v.produto_id
        WHERE p.ativo AND (translate(lower(p.nome),%s,%s) ILIKE %s
        OR translate(lower(v.tipo),%s,%s) ILIKE %s)
        AND (%s::bigint IS NULL OR p.tipo_id=%s) ORDER BY v.tipo,v.produto''',
        (ACCENTED,PLAIN,f'%{normalize_search(search)}%',
         ACCENTED,PLAIN,f'%{normalize_search(search)}%',category_id,category_id))
    return render_template('corte_productos.html',ticket=ticket,produtos=products,
                           categorias=categories(),q=search,categoria=category,
                           itens_registrados=get_items(ticket_id),busca={'q':search,'categoria':category})


@corte_bp.get('/tickets/<int:ticket_id>/corte/<int:produto_id>')
@db.read_snapshot
def seleccionar(ticket_id,produto_id):
    ticket = pending(ticket_id)
    row = product(produto_id)
    sold = cut = None
    restored = None
    key = str(uuid4())
    search = search_context(request.args)
    error = None
    if request.args.get('volver'):
        draft = unseal(request.args['volver'],'corte')
        if draft.get('ticket_id')!=ticket_id or draft.get('produto_id')!=produto_id:
            abort(400)
        sold = Decimal(draft['quantidade_vendida'])
        cut = Decimal(draft['quantidade_cortada'])
        restored = {a['lote_id']:a['quantidade'].replace('.',',') for a in draft['alocacoes']}
        key = draft['chave']
        search = draft.get('busca',search)
    elif any(k in request.args for k in ('quantidade','quantidade_vendida','quantidade_cortada')):
        if 'lote_id' in request.args:
            restored = entered_allocations(request.args)
        try:
            sold, cut = quantities(request.args, row['unidade_medida'])
        except ValueError as invalid:
            error = str(invalid)
    preparation = seal({'chave':key,'usuario_id':g.usuario['id'],'ticket_id':ticket_id,
        'produto_id':produto_id,'busca':search},'preparo')
    return selection_page(ticket,row,sold,cut,restored,preparation,search,
        error=error,partial=request.args.get('parcial')=='si')


@corte_bp.post('/tickets/<int:ticket_id>/corte/<int:produto_id>/revisar')
@db.read_snapshot
def revisar(ticket_id,produto_id):
    ticket = pending(ticket_id)
    row = product(produto_id)
    preparation = unseal(request.form.get('preparo',''),'preparo')
    if preparation.get('ticket_id')!=ticket_id or preparation.get('produto_id')!=produto_id:
        abort(400)
    sold = cut = None
    try:
        sold, cut = quantities(request.form, row['unidade_medida'])
        if row['unidade_medida']=='un':
            if request.form.getlist('lote_id') or request.form.getlist('retirar'):
                raise ValueError('Unidades no admiten asignaciones físicas.')
            if cut>row['estoque_total']:
                raise ValueError('La cantidad supera el stock disponible.')
            allocations=[]
        else:
            allocations = allocation_input(request.form.getlist('lote_id'),request.form.getlist('retirar'),cut,row['unidade_medida'])
        lots = {} if row['unidade_medida']=='un' else {lot['lote_id']:lot for lot in available_lots(produto_id,cut)}
        for a in allocations:
            if a['lote_id'] not in lots:
                raise ValueError('Un origen físico no está disponible para este producto.')
            if Decimal(a['quantidade'])>lots[a['lote_id']]['quantidade_atual']:
                raise ValueError('La cantidad supera el saldo de un origen físico. Revisá la selección.')
            lots[a['lote_id']]['saldo_depois'] = lots[a['lote_id']]['quantidade_atual'] - Decimal(a['quantidade'])
    except ValueError as error:
        return selection_page(ticket,row,sold,cut,entered_allocations(request.form),
            request.form['preparo'],preparation.get('busca',{}),error=str(error))
    draft = {'chave':preparation['chave'],'usuario_id':g.usuario['id'],'ticket_id':ticket_id,
             'produto_id':produto_id,'quantidade_vendida':format(sold,'f'),
             'quantidade_cortada':format(cut,'f'),'alocacoes':allocations,
             'busca':preparation.get('busca',{})}
    # Misma aritmética NUMERIC del item; solo consulta, todavía no congela precio.
    subtotal = db.fetchone('SELECT (%s::numeric * %s::numeric)::numeric(14,2) AS subtotal',
        (sold,row['preco_unitario']))['subtotal']
    return render_template('corte_conferir.html',ticket=ticket,produto=row,draft=draft,
                           envio=seal(draft,'corte'),lotes=lots,diferenca=cut-sold,subtotal=subtotal,
                           itens_registrados=get_items(ticket_id),busca=preparation.get('busca',{}),saldo_depois=row['estoque_total']-cut)


@corte_bp.post('/tickets/<int:ticket_id>/corte/confirmar')
def confirmar(ticket_id):
    draft = unseal(request.form.get('envio',''),'corte')
    if draft.get('ticket_id')!=ticket_id or request.form.get('realizado')!='si' \
        or 'quantidade_vendida' not in draft or 'quantidade_cortada' not in draft:
        abort(400)
    try:
        db.registrar_corte(draft,g.usuario['id'])
    except psycopg2.Error:
        return render_template('corte_error.html',ticket_id=ticket_id,
                               envio=request.form['envio']),409
    flash('Retirada registrada. El stock y el ticket ya están actualizados.','sucesso')
    return redirect(url_for('corte.productos',ticket_id=ticket_id,**draft.get('busca',{})))
