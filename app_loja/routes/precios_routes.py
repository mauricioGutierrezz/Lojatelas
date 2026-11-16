"""Edición pendiente, revisión y confirmación atómica; solo Administrador."""
from decimal import Decimal
from uuid import uuid4
import psycopg2
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from .. import db
from ..corte import seal, unseal
from ..validation import money_input
from .entrada_routes import categories

precios_bp = Blueprint('precios',__name__)


def catalog():
    return db.fetchall('SELECT p.*,EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=p.id) AS tem_foto FROM public.produtos p ORDER BY p.nome,p.id')


def draft(purpose):
    return unseal(request.form.get('envio',''),purpose)


@precios_bp.get('/precios')
def index():
    rows = catalog()
    snapshot = {'usuario_id':g.usuario['id'],'chave':str(uuid4()),
        'precos':{str(p['id']):str(p['preco_unitario']) for p in rows}}
    return render_template('precios.html',produtos=rows,categorias=categories(),values={},envio=seal(snapshot,'precios-lista'))


@precios_bp.post('/precios/revisar')
def revisar():
    initial = draft('precios-lista')
    rows = catalog()
    changes = []
    try:
        for product in rows:
            pid = str(product['id'])
            if pid not in initial['precos']:
                continue
            raw = request.form.get('precio_'+pid,'')
            try:
                price = money_input(raw,'Precio')
            except ValueError:
                raise ValueError(f"{product['nome']}: ingresá un precio válido con hasta 2 decimales.") from None
            old = Decimal(initial['precos'][pid])
            if price!=old:
                if product['preco_unitario']!=old:
                    raise ValueError('Los precios cambiaron. Volvé a abrir Precios y revisá los cambios.')
                changes.append({'produto_id':product['id'],'anterior':str(old),'novo':str(price)})
        if not changes:
            raise ValueError('No hay cambios para revisar.')
    except ValueError as error:
        flash(str(error),'erro')
        return render_template('precios.html',produtos=rows,categorias=categories(),values=request.form,envio=request.form['envio']),400
    changes.sort(key=lambda change:change['produto_id'])
    prepared = {k:initial[k] for k in ('usuario_id','chave','precos')}
    prepared['alteracoes'] = changes
    names = {p['id']:p['nome'] for p in rows}
    return render_template('precios_revisar.html',alteracoes=changes,nomes=names,unidades={p['id']:p['unidade_medida'] for p in rows},envio=seal(prepared,'precios-lote'))


@precios_bp.post('/precios/confirmar')
def confirmar():
    value = draft('precios-lote')
    if request.form.get('confirmado')!='si':
        abort(400)
    try:
        db.alterar_precos(value,g.usuario['id'])
    except psycopg2.Error as error:
        return render_template('precios_error.html',envio=request.form['envio'],alterado=error.pgcode=='P0001'),409 if error.pgcode=='P0001' else 503
    flash('Precios actualizados.','sucesso')
    return redirect(url_for('precios.index'),303)


@precios_bp.post('/precios/editar')
def editar():
    value = draft('precios-lote')
    values = {'precio_'+str(a['produto_id']):a['novo'].replace('.',',') for a in value['alteracoes']}
    initial = {k:value[k] for k in ('usuario_id','chave','precos')}
    return render_template('precios.html',produtos=catalog(),categorias=categories(),values=values,envio=seal(initial,'precios-lista'))
