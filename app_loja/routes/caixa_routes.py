"""Recepción integral con Efectivo/Otro, sin nueva retirada física."""
import psycopg2
from flask import Blueprint, abort, g, jsonify, redirect, render_template, request, url_for

from .. import db
from ..corte import seal, unseal
from ..cobro import efectivo_entregado

caixa_bp = Blueprint('caixa', __name__)


@caixa_bp.get('/caixa')
def index():
    code = request.args.get('codigo','').strip().upper()
    if code:
        row = db.fetchone('SELECT id FROM public.tickets WHERE codigo=%s', (code,))
        if row:
            return redirect(url_for('caixa.conferir',ticket_id=row['id']))
    return render_template('caixa.html',codigo=code,nao_encontrado=bool(code))


@caixa_bp.get('/caixa/tickets/<int:ticket_id>')
def conferir(ticket_id):
    result = db.conferir_ticket(ticket_id)
    if not result:
        abort(404)
    ticket, items, sale = result
    token = seal({'ticket_id':ticket_id,'codigo':ticket['codigo'],'usuario_id':g.usuario['id'],
                  'conferencia':ticket['conferencia']},'composicao')
    return render_template('venta.html',ticket=ticket,itens=items,venda=sale,envio=token)


@caixa_bp.post('/caixa/tickets/<int:ticket_id>/composicion')
def composicion(ticket_id):
    draft = unseal(request.form.get('envio',''),'composicao')
    if draft.get('ticket_id')!=ticket_id or not isinstance(draft.get('conferencia'),str):
        abort(400)
    try:
        modo = request.form.get('modo','entregado')
        if modo not in ('entregado','efectivo','otro'):
            raise ValueError('Elegí Efectivo entregado, Todo en efectivo o Todo en Otro.')
        entregado = efectivo_entregado(request.form.get('entregado')) if modo=='entregado' else None
    except ValueError as error:
        return jsonify(error=str(error)),400
    try:
        composition = db.preparar_cobro(draft,entregado,modo)
    except psycopg2.Error as error:
        if error.pgcode=='P0001':
            return jsonify(error='El ticket cambió o no está disponible. Volvé a revisarlo.',revisar=True),409
        return jsonify(error='No se pudo revisar la composición. Reintentá la revisión.'),503
    draft['efectivo'] = format(composition['valor_efectivo'],'f')
    return jsonify(envio=seal(draft,'recebimento'),
        total=format(composition['valor_total'],'f'),
        efectivo=format(composition['valor_efectivo'],'f'),otro=format(composition['valor_otro'],'f'))


@caixa_bp.post('/caixa/tickets/<int:ticket_id>/recibir')
def recibir(ticket_id):
    draft = unseal(request.form.get('envio',''),'recebimento')
    if draft.get('ticket_id')!=ticket_id or not isinstance(draft.get('conferencia'),str) \
        or not isinstance(draft.get('efectivo'),str) or request.form.get('integral')!='si':
        abort(400)
    try:
        db.receber_ticket(draft,g.usuario['id'])
    except psycopg2.Error as error:
        changed = error.pgcode=='P0001'
        return render_template('venta_error.html',ticket_id=ticket_id,
            envio=request.form['envio'],alterado=changed),409 if changed else 503
    return redirect(url_for('caixa.conferir',ticket_id=ticket_id))
