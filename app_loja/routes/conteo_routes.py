"""Consulta informativa, fondo versionado y Cierre definitivo diario."""
from datetime import date
from uuid import uuid4

import psycopg2
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from .. import db
from ..corte import seal, unseal
from ..validation import money_input

conteo_bp = Blueprint('conteo',__name__)


def screen(formal):
    state,closed,history = db.consultar_caixa()
    base = {'data':state['data'].isoformat(),'usuario_id':g.usuario['id'],'chave':str(uuid4())}
    return render_template('conteo.html',estado=state,cierre=closed,historico=history,formal=formal,
        registros=db.fetchall('SELECT data_referencia FROM public.fechamentos_caixa ORDER BY data_referencia DESC'),
        fundo=seal(base,'fundo'),envio=seal({**base,'conferencia':state['conferencia']},'cierre-preparo'))


def protected_draft(purpose):
    # El borrador firmado ya está ligado al usuario; el rol se comprueba en cada pedido.
    return unseal(request.form.get('envio',''),purpose)


@conteo_bp.get('/caixa/consulta')
def consulta():
    return screen(False)


@conteo_bp.get('/caixa/cierre')
def cierre():
    return screen(True)


@conteo_bp.post('/caixa/fondo')
def fondo():
    draft = protected_draft('fundo')
    try:
        valor = money_input(request.form.get('valor'),'Fondo inicial',precision=14)
        db.registrar_fundo(draft,valor,g.usuario['id'])
    except ValueError as error:
        flash(str(error),'erro')
    return redirect(url_for('conteo.cierre'))


@conteo_bp.post('/caixa/cierre/revisar')
def revisar():
    draft = protected_draft('cierre-preparo')
    try:
        contado = money_input(request.form.get('contado'),'Efectivo contado',
            optional=True,precision=14)
        state = db.preparar_cierre(draft,contado)
    except ValueError as error:
        flash(str(error),'erro')
        return redirect(url_for('conteo.cierre'))
    draft['contado'] = format(contado,'f') if contado is not None else None
    return render_template('cierre_revisar.html',estado=state,contado=contado,data=draft['data'],
        envio=seal(draft,'cierre'))


@conteo_bp.post('/caixa/cierre/confirmar')
def confirmar():
    draft = protected_draft('cierre')
    if request.form.get('definitivo')!='si' or 'contado' not in draft:
        abort(400)
    try:
        db.fechar_caixa(draft,g.usuario['id'])
    except psycopg2.Error as error:
        return render_template('cierre_error.html',envio=request.form['envio'],
            alterado=error.pgcode=='P0001'),409 if error.pgcode=='P0001' else 503
    # Aviso opcional del inicio en Windows (respaldo al cerrar); nunca afecta el Cierre ya confirmado.
    hook = current_app.config.get('AL_CERRAR')
    if hook:
        try:
            hook()
        except Exception:
            pass
    return redirect(url_for('conteo.registro',data=draft['data']))


@conteo_bp.get('/caixa/cierre/<data>')
def registro(data):
    try:
        day = date.fromisoformat(data)
    except ValueError:
        abort(404)
    state,closed,history = db.consultar_caixa(day)
    if closed is None:
        abort(404)
    return render_template('cierre_registro.html',cierre=closed)
